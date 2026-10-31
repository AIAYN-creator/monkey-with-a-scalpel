"""Mutation check of the host tests: injects one safety fault at a time into the controller and requires the tests to fail.

Usage, from the repository root:
    python firmware/tests/mutation_check.py

A mutant that the tests do not catch (a "survivor") means a safety rule has no test. Exit code 1 if any survives.
Repeat it whenever the controller or the tests change, and when the board layer is added.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "firmware" / "core" / "controller.cpp"
TEST = ROOT / "firmware" / "tests" / "test_controller.cpp"

# (name, text that must occur exactly once in controller.cpp, replacement)
MUTANTS = [
    ("soft limit minimum ignored", "target[i] < config_.axis[i].min_pos - 1e-9", "target[i] < config_.axis[i].min_pos - 1e3"),
    ("soft limit maximum ignored", "target[i] > config_.axis[i].max_pos + 1e-9", "target[i] > config_.axis[i].max_pos + 1e3"),
    ("move beyond limits accepted", 'if (!within_soft_limits(target)) return "error:limit";', ""),
    ("watchdog never fires", "now_ms - last_rx_ms_ > config_.watchdog_ms", "now_ms - last_rx_ms_ > config_.watchdog_ms * 1000"),
    ("abort button ignored", "if (in.abort_button) request_abort(Cause::Button);", ""),
    ("limit switch hit ignored (minimum side)", "if ((in.limit_min[i] && out.step_delta[i] < 0) ||", "if ((false && out.step_delta[i] < 0) ||"),
    ("limit switch hit ignored (maximum side)", "(in.limit_max[i] && out.step_delta[i] > 0)) {", "(false && out.step_delta[i] > 0)) {"),
    ("motor power loss ignored", "if (!in.motor_power_ok && state_ != State::PowerLoss) {", "if (false && state_ != State::PowerLoss) {"),
    ("homing kept after power loss", "homed_ = false;  // steps may have been lost with the power", ";"),
    ("withdrawal goes the wrong way", "retract[i] = p[i] + s * u[i];", "retract[i] = p[i] - s * u[i];"),
    ("park height ignored after withdrawal", "up[Z] = std::max(retract[Z], config_.park[Z]);", "up[Z] = std::min(retract[Z], config_.park[Z]);"),
]


def run(source_text, workdir, name):
    src = workdir / f"{name}.cpp"
    src.write_text(source_text, encoding="utf-8")
    exe = workdir / f"{name}.exe"
    build = subprocess.run(["g++", "-std=c++17", "-O1", f"-I{SOURCE.parent}", str(src), str(TEST), "-o", str(exe)],
                           check=False, capture_output=True, text=True)
    if build.returncode != 0:
        return "does not compile", build.stderr.strip().splitlines()[:3]
    result = subprocess.run([str(exe)], check=False, capture_output=True, text=True)
    return ("passes" if result.returncode == 0 else "fails"), result.stdout.strip().splitlines()[-1:]


def main():
    original = SOURCE.read_text(encoding="utf-8")
    survivors = []
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        status, detail = run(original, workdir, "original")
        if status != "passes":
            print(f"The unmodified controller does not pass its tests ({status}): {detail}")
            return 2
        print(f"original: tests pass ({detail[0] if detail else ''})")
        for index, (name, old, new) in enumerate(MUTANTS):
            if original.count(old) != 1:
                print(f"SKIPPED {name!r}: the target text occurs {original.count(old)} times (update the mutant list)")
                survivors.append(name)
                continue
            status, detail = run(original.replace(old, new), workdir, f"m{index}")
            killed = status == "fails"
            print(f"{'killed  ' if killed else 'SURVIVED'}  {name} ({status})")
            if not killed:
                survivors.append(name)
    print(f"\n{len(MUTANTS) - len(survivors)} of {len(MUTANTS)} mutants killed")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
