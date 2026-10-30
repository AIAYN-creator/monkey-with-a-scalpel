"""Monte Carlo sweep of the self-correction loop under errors (card p0-04).

For each error level the loop runs many times with different noise seeds, and the final TRUE
distance to the target is recorded (not the measured one, which is what the loop believes).
A run counts as a success if the true distance ends below 0.05 mm (50 µm) or 0.1 mm (100 µm), the
two ends of the working benchmark in PROJECT.md.

Every error value is an assumption to see where the loop breaks; real values come from Phase 1.

Usage, from the repository root:
    python simulation/sweep_errores.py                 full sweep, 200 runs per point
    python simulation/sweep_errores.py --runs 10       quick run
    python simulation/sweep_errores.py --check         self-check of the error model
"""
import argparse
import csv
import sys
from pathlib import Path

import error_model as em
import loop_autocorreccion as loop
import numpy as np
import sim_brazo

STRICT_MM, LOOSE_MM = 0.05, 0.1
RELIABLE = 0.95  # fraction of runs that must succeed for a level to count as tolerated
ACTIVE = list(sim_brazo.LINEAR_JOINTS)

NOISE_UM = (0, 5, 10, 20, 50, 100)
BACKLASH_UM = (0, 10, 25, 50, 100, 200)
BIAS_UM = (0, 10, 20, 50, 100)
STEP_UM = (0, 0.625, 2.5, 12.5, 50)
GAINS = (0.1, 0.2, 0.3, 0.5, 0.8)
SCENARIOS = {  # (noise, backlash, bias) in µm; assumptions
    "optimistic": (10, 25, 10),
    "central": (30, 50, 20),
    "pessimistic": (60, 100, 50),
}


def run_once(model, data, error, seed):
    sim_brazo.set_pose(model, data, **loop.START_POSE)
    rng = np.random.default_rng(seed)
    rows = loop.autocorrect(model, data, ACTIVE, measure=em.make_measure(error, rng), actuate=em.make_actuator(error))
    return rows[-1]["true_distance_mm"], rows[-1]["iteration"]


def point(model, data, error, runs, seed):
    results = [run_once(model, data, error, seed + k) for k in range(runs)]
    final = np.array([r[0] for r in results])
    iterations = np.array([r[1] for r in results])
    return {
        "median_mm": float(np.median(final)),
        "p95_mm": float(np.percentile(final, 95)),
        "success_50um": float(np.mean(final < STRICT_MM)),
        "success_100um": float(np.mean(final < LOOSE_MM)),
        "median_iterations": float(np.median(iterations)),
    }


def sweep(runs, seed):
    model, data = sim_brazo.build_model(wrist_dof=2)
    records = []

    def add(experiment, label, error, **extra):
        metrics = point(model, data, error, runs, seed)
        records.append({"experiment": experiment, "level": label, **extra, **metrics})

    for um in NOISE_UM:
        add("noise", um, em.ErrorModel(noise_mm=um / 1000))
    for um in BACKLASH_UM:
        add("backlash", um, em.ErrorModel(backlash_mm=um / 1000))
    for um in BIAS_UM:
        add("bias", um, em.ErrorModel(bias_mm=um / 1000))
    for um in STEP_UM:
        add("step", um, em.ErrorModel(step_mm=um / 1000))
    for name, (noise, backlash, bias) in SCENARIOS.items():
        add("scenario", name, em.ErrorModel(noise_mm=noise / 1000, backlash_mm=backlash / 1000, bias_mm=bias / 1000),
            noise_um=noise, backlash_um=backlash, bias_um=bias)
    original_gain = loop.GAIN
    try:
        for gain in GAINS:
            loop.GAIN = gain
            add("gain", gain, em.ErrorModel(noise_mm=0.05, backlash_mm=0.05), noise_um=50, backlash_um=50)
    finally:
        loop.GAIN = original_gain
    return records


def tolerated(records, experiment):
    levels = [r["level"] for r in records if r["experiment"] == experiment and r["success_50um"] >= RELIABLE]
    return max(levels) if levels else None


def print_tables(records, runs):
    names = {"noise": "Ruido de cámara (µm, por coordenada)", "backlash": "Holgura de los ejes (µm)",
             "bias": "Sesgo de calibración (µm)", "step": "Paso mínimo del eje (µm)",
             "scenario": "Escenarios combinados", "gain": "Ganancia del bucle (ruido 50 µm y holgura 50 µm)"}
    for experiment, title in names.items():
        print(f"\n### {title}  ({runs} ejecuciones por punto)\n")
        print("| Nivel | Mediana final (mm) | P95 final (mm) | Éxito < 50 µm | Éxito < 100 µm | Iteraciones (mediana) |")
        print("|---|---|---|---|---|---|")
        for r in (x for x in records if x["experiment"] == experiment):
            print(f"| {r['level']} | {r['median_mm']:.4f} | {r['p95_mm']:.4f} | {r['success_50um']:.0%} | "
                  f"{r['success_100um']:.0%} | {r['median_iterations']:.0f} |")
    print(f"\n### Margen (éxito < 50 µm en al menos el {RELIABLE:.0%} de las ejecuciones)\n")
    for experiment, unit in (("noise", "µm de ruido"), ("backlash", "µm de holgura"), ("bias", "µm de sesgo"),
                             ("step", "µm de paso")):
        limit = tolerated(records, experiment)
        top = max(r["level"] for r in records if r["experiment"] == experiment)
        note = " (todo el rango probado: no se encontró el límite)" if limit == top else ""
        print(f"- {experiment}: hasta {limit} {unit}{note}")


def write_csv(records, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for r in records for key in r}, key=lambda k: (k not in ("experiment", "level"), k))
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def self_check():
    """Check the error model against hand-computed behaviour. Raises AssertionError on a mismatch."""
    model, data = sim_brazo.build_model(wrist_dof=2)

    final, _ = run_once(model, data, em.ErrorModel(), seed=0)
    assert final < loop.TOLERANCE_MM, "without errors the loop must reach the ideal tolerance"

    joint = model.joint("x").id
    address = model.jnt_qposadr[joint]
    play = 0.001
    sim_brazo.set_pose(model, data)
    actuate = em.make_actuator(em.ErrorModel(backlash_mm=play * 1000))
    for expected in (0.0, 0.0, play / 4):  # +play/4 three times: dead band absorbs the first two
        actuate(model, data, [joint], [play / 4])
        assert abs(data.qpos[address] - expected) < 1e-12, "backlash dead band is wrong"
    actuate(model, data, [joint], [-play / 4])
    assert abs(data.qpos[address] - play / 4) < 1e-12, "a reversal must first take up the slack"

    sim_brazo.set_pose(model, data)
    actuate = em.make_actuator(em.ErrorModel(step_mm=0.01))
    actuate(model, data, [joint], [2e-6])  # 2 µm, below half of a 10 µm step
    assert abs(data.qpos[address]) < 1e-12, "a move below half a step must not move the axis"

    final, _ = run_once(model, data, em.ErrorModel(bias_mm=0.1), seed=0)
    assert abs(final - 0.1) < 0.002, "with only a calibration bias the true error must end at the bias"
    print("SELF-CHECK OK")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--out", default="logs/barrido_errores.csv")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--example", metavar="CSV", help="write one run of the central scenario to this CSV and exit")
    args = parser.parse_args(argv)
    if args.check:
        self_check()
        return 0
    if args.example:
        noise, backlash, bias = SCENARIOS["central"]
        error = em.ErrorModel(noise_mm=noise / 1000, backlash_mm=backlash / 1000, bias_mm=bias / 1000)
        model, data = sim_brazo.build_model(wrist_dof=2)
        sim_brazo.set_pose(model, data, **loop.START_POSE)
        rng = np.random.default_rng(args.seed)
        rows = loop.autocorrect(model, data, ACTIVE, measure=em.make_measure(error, rng),
                                actuate=em.make_actuator(error))
        loop.write_log(rows, args.example)
        print(f"central scenario: {len(rows)} rows, final measured {rows[-1]['distance_mm']:.4f} mm, "
              f"final true {rows[-1]['true_distance_mm']:.4f} mm, log: {args.example}")
        return 0
    records = sweep(args.runs, args.seed)
    write_csv(records, args.out)
    print_tables(records, args.runs)
    print(f"\nCSV: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
