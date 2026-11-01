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
CORE = ROOT / "firmware" / "core"
BOARD = ROOT / "firmware" / "board" / "controller_board"
TESTS = ROOT / "firmware" / "tests"

# target -> (file that is mutated, test sources to compile with it, directories on the include path)
TARGETS = {
    "controller": (CORE / "controller.cpp", [CORE / "controller.cpp", TESTS / "test_controller.cpp"], [CORE]),
    "step_queue": (CORE / "step_queue.h", [TESTS / "test_board.cpp"], [CORE, BOARD]),
    "board_config": (BOARD / "board_config.h", [TESTS / "test_board.cpp"], [CORE, BOARD]),
}

# (target, name, text that must occur exactly once in the target file, replacement)
MUTANTS = [
    ("controller", "soft limit minimum ignored", "target[i] < config_.axis[i].min_pos - 1e-9", "target[i] < config_.axis[i].min_pos - 1e3"),
    ("controller", "soft limit maximum ignored", "target[i] > config_.axis[i].max_pos + 1e-9", "target[i] > config_.axis[i].max_pos + 1e3"),
    ("controller", "move beyond limits accepted", 'if (!within_soft_limits(target)) return "error:limit";', ""),
    ("controller", "watchdog never fires", "now_ms - last_rx_ms_ > config_.watchdog_ms", "now_ms - last_rx_ms_ > config_.watchdog_ms * 1000"),
    ("controller", "abort button ignored", "if (in.abort_button) request_abort(Cause::Button);", ""),
    ("controller", "limit switch hit ignored (minimum side)", "if ((in.limit_min[i] && out.step_delta[i] < 0) ||", "if ((false && out.step_delta[i] < 0) ||"),
    ("controller", "limit switch hit ignored (maximum side)", "(in.limit_max[i] && out.step_delta[i] > 0)) {", "(false && out.step_delta[i] > 0)) {"),
    ("controller", "motor power loss ignored", "if (!in.motor_power_ok && state_ != State::PowerLoss) {", "if (false && state_ != State::PowerLoss) {"),
    ("controller", "homing kept after power loss", "homed_ = false;  // steps may have been lost with the power", ";"),
    ("controller", "withdrawal goes the wrong way", "retract[i] = p[i] + s * u[i];", "retract[i] = p[i] - s * u[i];"),
    ("controller", "park height ignored after withdrawal", "up[Z] = std::max(retract[Z], config_.park[Z]);", "up[Z] = std::min(retract[Z], config_.park[Z]);"),
    ("step_queue", "step queue counts steps the wrong way", "pending_[axis] += forward_[axis] ? -1 : 1;", "pending_[axis] += forward_[axis] ? 1 : -1;"),
    ("step_queue", "step queue has no low phase", "if (high_[axis]) {", "if (false) {"),
    ("step_queue", "step queue clear does nothing", "void clear() { pending_.fill(0); }", "void clear() {}"),
    ("step_queue", "step queue overflow not reported", "overflow_ = true;", ""),
    ("step_queue", "step queue backlog not clamped", "total = total > 0 ? kMaxPending : -kMaxPending;", ""),
    ("step_queue", "step queue direction inverted", "forward_[axis] = pending_[axis] > 0;", "forward_[axis] = pending_[axis] < 0;"),
    ("board_config", "forbidden pin 0 allowed", "pin == 0 || pin == 3", "pin == 3"),
    ("board_config", "microstepping changed without the tests noticing", "constexpr double kMicrosteps = 8.0;", "constexpr double kMicrosteps = 16.0;"),
    ("board_config", "duplicate pin allowed by the static check", "constexpr std::array<int, kAxes> kDirPin{17, 18, 8, 9, 10, 11};", "constexpr std::array<int, kAxes> kDirPin{4, 18, 8, 9, 10, 11};"),
]


def run(target, source_text, workdir, name):
    """Compiles the tests against a (possibly mutated) copy of the target file and runs them."""
    path, tests, includes = TARGETS[target]
    folder = workdir / name
    folder.mkdir()
    mutated = folder / path.name
    mutated.write_text(source_text, encoding="utf-8")
    sources = [str(mutated if t == path else t) for t in tests]
    flags = [f"-I{folder}"] + [f"-I{d}" for d in includes]
    exe = folder / "tests.exe"
    build = subprocess.run(["g++", "-std=c++17", "-O1", *flags, *sources, "-o", str(exe)],
                           check=False, capture_output=True, text=True)
    if build.returncode != 0:
        # a static_assert that rejects the mutant counts as detection; any other compile error is a bad mutant
        return ("fails" if "static assertion" in build.stderr else "does not compile"), build.stderr.strip().splitlines()[:3]
    result = subprocess.run([str(exe)], check=False, capture_output=True, text=True)
    return ("passes" if result.returncode == 0 else "fails"), result.stdout.strip().splitlines()[-1:]


def main():
    originals = {name: target[0].read_text(encoding="utf-8") for name, target in TARGETS.items()}
    survivors = []
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        for name, text in originals.items():
            status, detail = run(name, text, workdir, f"original_{name}")
            if status != "passes":
                print(f"The unmodified {name} does not pass its tests ({status}): {detail}")
                return 2
            print(f"original {name}: tests pass ({detail[0] if detail else ''})")
        for index, (target, name, old, new) in enumerate(MUTANTS):
            original = originals[target]
            if original.count(old) != 1:
                print(f"SKIPPED {name!r}: the target text occurs {original.count(old)} times (update the mutant list)")
                survivors.append(name)
                continue
            status, detail = run(target, original.replace(old, new), workdir, f"m{index}")
            killed = status == "fails"
            print(f"{'killed  ' if killed else 'SURVIVED'}  {name} ({status})")
            if not killed:
                survivors.append(name)
    print(f"\n{len(MUTANTS) - len(survivors)} of {len(MUTANTS)} mutants killed")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
