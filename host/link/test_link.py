"""Tests of the host link against the simulated controller (the real core on a simulated plant). Usage, from the repository root:

    python host/link/test_link.py

Needs g++ to build the simulated controller. Exit code 1 on a failure.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from link import (
    ChainLog,
    CommandRejected,
    ProtocolError,
    Session,
    SimTransport,
    build_simulator,
    move_command,
    parse_reply,
    parse_status,
)

FAILURES = []


def check(condition, message):
    if not condition:
        FAILURES.append(message)
        print("  FAIL:", message)


def test_protocol():
    print("protocol")
    check(parse_reply("ok pong").ok and parse_reply("ok pong").words == ("pong",), "ok pong")
    reply = parse_reply("ok state=idle homed=1 cause=none x=1.5000 y=-2.0000 z=3.0000 a=0.000 b=0.000 p=0.0000")
    status = parse_status(reply)
    check(status["state"] == "idle" and status["homed"] and status["x"] == 1.5 and status["y"] == -2.0, "a STATUS reply is parsed")
    check(not parse_reply("error:limit").ok and parse_reply("error:limit").code == "limit", "an error reply carries its code")
    for garbage in ("", "hello", "OK", "err:limit", "okay"):
        try:
            parse_reply(garbage)
            check(False, f"{garbage!r} must raise ProtocolError")
        except ProtocolError:
            pass
    check(move_command(x=1, z=-2.5, feed=10) == "MOVE X1.0000 Z-2.5000 F10.0000", "a MOVE line is built in axis order")
    for bad in ({}, {"q": 1}):
        try:
            move_command(**bad)
            check(False, f"move_command({bad}) must raise ValueError")
        except ValueError:
            pass


def test_chainlog(tmp):
    print("chained log")
    path = tmp / "log.jsonl"
    log = ChainLog(path)
    for i in range(5):
        log.append(kind="test", i=i)
    ok, count, last = ChainLog.verify(path)
    check(ok and count == 5 and last == log.last, "a clean log verifies")
    reopened = ChainLog(path)
    reopened.append(kind="more")
    check(ChainLog.verify(path)[0] and ChainLog.verify(path)[1] == 6, "a log can be reopened and extended")
    lines = path.read_text(encoding="utf-8").splitlines()
    cases = {
        "an edited entry": lines[:2] + [lines[2].replace('"i": 2', '"i": 9').replace('"i":2', '"i":9')] + lines[3:],
        "a deleted entry": lines[:2] + lines[3:],
        "swapped entries": [lines[0], lines[2], lines[1]] + lines[3:],
        "garbage": lines[:3] + ["not json"],
    }
    for name, content in cases.items():
        broken = tmp / "broken.jsonl"
        broken.write_text("\n".join(content) + "\n", encoding="utf-8")
        check(not ChainLog.verify(broken)[0], f"{name} is detected")
    broken.write_text(json.dumps({"body": {"n": 1}, "prev": "0" * 64, "hash": "f" * 64}) + "\n", encoding="utf-8")
    try:
        ChainLog(broken)
        check(False, "opening a broken log must raise")
    except ValueError:
        pass


def test_session(exe, tmp):
    print("session against the simulated controller")
    transport = SimTransport(exe)
    session = Session(transport, log_path=tmp / "session.jsonl")
    try:
        check(session.ping().words == ("pong",), "PING is answered")
        status = session.status()
        check(status["state"] == "not_homed" and not status["homed"], "the controller starts not homed")

        try:
            session.move(x=5)
            check(False, "MOVE before homing must be rejected")
        except CommandRejected as error:
            check(error.code == "not_homed", "MOVE before homing is rejected with not_homed")

        session.home()
        status = session.wait_settled()
        check(status["state"] == "idle" and status["homed"], "homing finishes idle and homed")

        session.move(x=10, y=-5, z=20, feed=30)
        status = session.wait_settled()
        physical = transport.physical()
        check(abs(status["x"] - 10) < 0.01 and abs(status["z"] - 20) < 0.01, "MOVE reaches its target (controller position)")
        check(abs(physical["x"] - status["x"]) < 0.01 and abs(physical["z"] - status["z"]) < 0.01,
              "and the simulated machine is where the controller says")

        try:
            session.move(x=500)
            check(False, "a target beyond the soft limit must be rejected")
        except CommandRejected as error:
            check(error.code == "limit", "a target beyond the limit is rejected with limit")
        check(session.status()["x"] == status["x"], "a rejected move does not move anything")

        session.run_for(5000)
        check(session.status()["state"] == "idle", "five seconds of heartbeat keep the controller alive")

        session.move(x=-20, feed=5)
        session.run_for(500)
        session.stop()
        status = session.wait_settled()
        check(status["state"] in ("idle", "hold") and -20 < status["x"] < 10, "STOP halts a move half way")

        # the watchdog: silence beyond 1000 ms aborts, with the cause recorded
        session.silent_for(1400)
        status = session.wait_settled()
        check(status["state"] == "aborted" and status["cause"] == "watchdog", "a silent host triggers the watchdog abort")
        session.clear()
        status = session.status()
        check(status["state"] == "idle" and status["homed"], "CLEAR after a watchdog abort leaves the controller idle")

        # the abort button, handled inside the controller
        transport.button(True)
        transport.advance(5)
        check(session.status()["state"] in ("aborting", "aborted"), "the ABORT button aborts within a few ticks")
        transport.button(False)
        status = session.wait_settled()
        check(status["state"] == "aborted" and status["cause"] == "button", "and the cause is the button")
        session.clear()

        # a command abort withdraws the tool and ends aborted
        session.move(z=0, feed=40)
        session.wait_settled()
        session.abort()
        status = session.wait_settled()
        check(status["state"] == "aborted" and status["cause"] == "command", "the ABORT command ends aborted")
        session.clear()

        # lost steps: the axis slips onto a limit switch, which latches a fault
        session.move(x=0, y=0, z=0, feed=40)
        session.wait_settled()
        transport.slip("X", 5.0)
        try:
            session.move(x=49, feed=30)
        except CommandRejected:
            pass
        status = session.wait_settled()
        check(status["state"] == "fault" and status["cause"] == "limit", "a limit switch hit while moving latches a fault")
        check(abs(transport.physical()["x"]) < 52.5, "and the axis stops at the switch")
        session.clear()
        check(session.status()["state"] == "not_homed", "after a fault the controller needs homing again")

        # motor power loss
        session.home()
        session.wait_settled()
        transport.power(False)
        transport.advance(5)
        check(session.status()["state"] == "power_loss", "motor power loss is noticed")
        try:
            session.clear()
            check(False, "CLEAR without power must be rejected")
        except CommandRejected as error:
            check(error.code == "power", "CLEAR without power is rejected with power")
        transport.power(True)
        transport.advance(2)  # the controller reads the power input on its next tick
        session.clear()
        check(session.status()["state"] == "not_homed", "after power returns, CLEAR leaves the controller to be homed again")
    finally:
        session.close()

    ok, count, _ = ChainLog.verify(tmp / "session.jsonl")
    check(ok and count > 40, f"every exchange of the session is in a log that verifies ({count} entries)")
    commands = [json.loads(line)["body"] for line in (tmp / "session.jsonl").read_text(encoding="utf-8").splitlines()]
    check(any(c.get("command") == "HOME" for c in commands) and any(c.get("reply", "").startswith("error:") for c in commands),
          "the log keeps the commands and the error replies")


def main():
    test_protocol()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        test_chainlog(tmp)
        try:
            exe = build_simulator(tmp)
        except Exception as error:  # noqa: BLE001 - report any build problem and stop
            print("cannot build the simulated controller:", error)
            return 2
        test_session(exe, tmp)
    print("LINK OK" if not FAILURES else f"LINK FAILED: {len(FAILURES)} checks")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
