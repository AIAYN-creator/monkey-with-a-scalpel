"""A session with the controller: typed commands, every exchange in a chained log, and the safety heartbeat.

The controller aborts by itself if the host stays silent for longer than its watchdog (1000 ms by default), so a session has to
keep talking. With a real port, `start_heartbeat` does it in a thread. With the simulated controller, time only passes through
`run_for`, which sends the heartbeat as time goes by, and `silent_for`, which does not (to test the watchdog).
"""
import threading
import time

from .chainlog import ChainLog
from .protocol import ProtocolError, move_command, parse_reply, parse_status

SETTLED = ("idle", "hold", "aborted", "fault", "power_loss", "not_homed")


class CommandRejected(RuntimeError):
    """The controller answered with an error code."""

    def __init__(self, line, code):
        super().__init__(f"{line!r} rejected: error:{code}")
        self.line, self.code = line, code


class Session:
    def __init__(self, transport, log_path=None, heartbeat_ms=200):
        self.transport = transport
        self.heartbeat_ms = heartbeat_ms
        self.log = ChainLog(log_path) if log_path else None
        self._lock = threading.Lock()
        self.lost_beats = 0  # heartbeats that failed; the controller aborts by itself if they keep failing
        self._beat = None
        self._stop_beat = threading.Event()

    # ---- raw exchange
    def send(self, line, check=True):
        """Sends one line, logs it with its reply and returns the parsed reply. Raises CommandRejected on an error reply
        when `check` is true, and ProtocolError if the reply is not part of the protocol."""
        with self._lock:
            raw = self.transport.request(line)
        try:
            reply = parse_reply(raw)
        except ProtocolError:
            if self.log:
                self.log.append(kind="protocol_error", command=line, reply=raw)
            raise
        if self.log:
            self.log.append(kind="command", command=line, reply=raw)
        if check and not reply.ok:
            raise CommandRejected(line, reply.code)
        return reply

    # ---- commands
    def ping(self):
        return self.send("PING")

    def status(self):
        return parse_status(self.send("STATUS"))

    def home(self):
        return self.send("HOME")

    def move(self, feed=None, **axes):
        return self.send(move_command(feed=feed, **axes))

    def park(self):
        return self.send("PARK")

    def tool(self):
        """The tool interface: name (none, unknown or the tool), id, ready and power."""
        fields = self.send("TOOL").fields
        return {"tool": fields["tool"], "id": int(fields["id"]), "ready": fields["ready"] == "1", "power": fields["power"] == "1"}

    def tool_on(self):
        return self.send("TOOL ON")

    def tool_off(self):
        return self.send("TOOL OFF")

    def stop(self):
        return self.send("STOP")

    def abort(self):
        return self.send("ABORT")

    def clear(self):
        return self.send("CLEAR")

    # ---- time, for the simulated controller
    def run_for(self, ms):
        """Lets `ms` of simulated time pass, sending the heartbeat every `heartbeat_ms`."""
        remaining = int(ms)
        while remaining > 0:
            self.ping()
            step = min(self.heartbeat_ms, remaining)
            self.transport.advance(step)
            remaining -= step

    def silent_for(self, ms):
        """Lets `ms` of simulated time pass without any message (the controller's watchdog may fire)."""
        self.transport.advance(int(ms))

    def wait_settled(self, timeout_ms=600000):
        """Runs the simulated time until the controller is no longer moving, homing or aborting; returns the status."""
        waited = 0
        while waited <= timeout_ms:
            status = self.status()
            if status["state"] in SETTLED:
                return status
            self.run_for(self.heartbeat_ms)
            waited += self.heartbeat_ms
        raise TimeoutError(f"the controller did not settle within {timeout_ms} ms")

    # ---- heartbeat for a real port
    def start_heartbeat(self):
        """Sends PING every `heartbeat_ms` from a thread, until `close`."""
        def beat():
            while not self._stop_beat.wait(self.heartbeat_ms / 1000.0):
                try:
                    self.ping()
                except Exception:  # noqa: BLE001 - a lost heartbeat must not kill the thread; the controller aborts by itself
                    self.lost_beats += 1
        self._beat = threading.Thread(target=beat, name="heartbeat", daemon=True)
        self._beat.start()

    def close(self):
        self._stop_beat.set()
        if self._beat is not None:
            self._beat.join(timeout=2)
        time.sleep(0)
        self.transport.close()
