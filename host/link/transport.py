"""Transports to the controller: a real serial port, and the simulated controller (the real core on a simulated plant).

A transport sends one line and returns the one-line reply. Nothing here decides anything about safety.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TransportError(RuntimeError):
    """The connection failed or went silent."""


class SerialTransport:
    """The controller over a serial port (needs pyserial: `pip install pyserial`). Not tested without hardware."""

    def __init__(self, port, baud=115200, timeout=1.0):
        try:
            import serial  # imported late: the simulated transport does not need it
        except ImportError as error:
            raise TransportError("pyserial is not installed") from error
        self._serial = serial.Serial(port, baud, timeout=timeout)

    def request(self, line):
        self._serial.write((line + "\n").encode("ascii"))
        reply = self._serial.readline().decode("ascii", errors="replace").strip()
        if not reply:
            raise TransportError(f"no reply to {line!r} (timeout)")
        return reply

    def close(self):
        self._serial.close()


def build_simulator(output_dir):
    """Compiles the simulated controller with g++ and returns its path."""
    out = Path(output_dir) / ("sim_controller.exe" if Path(output_dir).drive else "sim_controller")
    sources = [ROOT / "firmware" / "core" / "controller.cpp", ROOT / "firmware" / "sim" / "sim_main.cpp"]
    result = subprocess.run(["g++", "-std=c++17", "-O2", f"-I{ROOT / 'firmware' / 'core'}", *map(str, sources), "-o", str(out)],
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise TransportError("could not build the simulated controller:\n" + result.stderr[-800:])
    return out


class SimTransport:
    """The simulated controller as a subprocess. Time only passes when `advance` is called, so tests are deterministic."""

    def __init__(self, executable):
        self._process = subprocess.Popen([str(executable)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def request(self, line):
        if self._process.poll() is not None:
            raise TransportError("the simulated controller has exited")
        self._process.stdin.write(line + "\n")
        self._process.stdin.flush()
        reply = self._process.stdout.readline().strip()
        if not reply:
            raise TransportError(f"no reply to {line!r}")
        return reply

    # simulation controls
    def advance(self, ms):
        return self.request(f"@advance {int(ms)}")

    def button(self, pressed):
        return self.request(f"@button {1 if pressed else 0}")

    def power(self, on):
        return self.request(f"@power {1 if on else 0}")

    def slip(self, axis, mm):
        return self.request(f"@slip {axis.upper()} {mm}")

    def physical(self):
        return {key: float(value) for key, value in (item.split("=") for item in self.request("@phys").split())}

    def time_ms(self):
        return int(self.request("@time"))

    def close(self):
        if self._process.poll() is None:
            try:
                self._process.stdin.write("@quit\n")
                self._process.stdin.flush()
            except OSError:
                pass
            self._process.wait(timeout=5)
