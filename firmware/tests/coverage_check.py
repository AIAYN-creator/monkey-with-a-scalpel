"""Line coverage of the controller core by the unit tests and the fuzz test together; fails below a threshold.

Usage, from the repository root:
    python firmware/tests/coverage_check.py [minimum_percent]      (default 95)

The core is compiled once with coverage, linked into both test programs, and both run, so their counts merge in the same data
file. Needs g++ and gcov.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware" / "core"
TESTS = ROOT / "firmware" / "tests"
MINIMUM = float(sys.argv[1]) if len(sys.argv) > 1 else 95.0


def run(command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(" ".join(map(str, command)), "failed:", (result.stdout + result.stderr)[-600:])
        sys.exit(2)
    return result.stdout


def main():
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        flags = ["-std=c++17", "-O0", "--coverage", f"-I{CORE}"]
        run(["g++", *flags, "-c", str(CORE / "controller.cpp"), "-o", "ctl.o"], work)
        for name in ("test_controller", "test_fuzz", "test_tools"):
            run(["g++", *flags, "-c", str(TESTS / f"{name}.cpp"), "-o", f"{name}.o"], work)
            run(["g++", "--coverage", "ctl.o", f"{name}.o", "-o", f"{name}.exe"], work)
        for name in ("test_controller", "test_fuzz", "test_tools"):
            run([str(work / f"{name}.exe")], work)
        output = run(["gcov", "-b", "-n", "ctl.gcda"], work)
    match = re.search(r"File '[^']*controller\.cpp'\s*\nLines executed:([\d.]+)% of (\d+)", output)
    branches = re.search(r"File '[^']*controller\.cpp'.*?Branches executed:([\d.]+)%", output, re.DOTALL)
    if not match:
        print("could not read the coverage report:", output[-400:])
        return 2
    percent, lines = float(match.group(1)), int(match.group(2))
    print(f"controller.cpp: {percent:.2f}% of {lines} lines executed by the unit tests and the fuzz"
          + (f" ({branches.group(1)}% of branches executed)" if branches else ""))
    if percent < MINIMUM:
        print(f"COVERAGE TOO LOW: the minimum is {MINIMUM}%")
        return 1
    print("COVERAGE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
