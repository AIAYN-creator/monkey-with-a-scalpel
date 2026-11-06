"""The serial protocol of the controller: one ASCII line per command, answered with `ok ...` or `error:<code>`."""
from dataclasses import dataclass, field

AXES = ("x", "y", "z", "a", "b", "p")
ERROR_CODES = ("syntax", "unknown_command", "not_homed", "busy", "state", "limit", "power", "tool")


class ProtocolError(ValueError):
    """The controller answered with something that is not part of the protocol."""


@dataclass(frozen=True)
class Reply:
    ok: bool
    code: str = ""  # the error code, empty when ok
    fields: dict = field(default_factory=dict)  # key=value pairs of an ok reply
    words: tuple = ()  # the other words of an ok reply
    raw: str = ""


def parse_reply(line):
    """Parses one reply line. Raises ProtocolError for anything that does not start with `ok` or `error:`."""
    text = line.strip()
    if text == "ok" or text.startswith("ok "):
        fields, words = {}, []
        for token in text[2:].split():
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key] = value
            else:
                words.append(token)
        return Reply(True, "", fields, tuple(words), text)
    if text.startswith("error:"):
        return Reply(False, text[len("error:"):], {}, (), text)
    raise ProtocolError(f"not a reply of the controller: {line!r}")


def parse_status(reply):
    """The fields of a STATUS reply as numbers and names: state, homed, cause and the six positions."""
    if not reply.ok or "state" not in reply.fields:
        raise ProtocolError(f"not a STATUS reply: {reply.raw!r}")
    status = {"state": reply.fields["state"], "homed": reply.fields.get("homed") == "1", "cause": reply.fields.get("cause", "none")}
    for axis in AXES:
        if axis in reply.fields:
            status[axis] = float(reply.fields[axis])
    return status


def move_command(feed=None, **axes):
    """MOVE line for the given axis targets (mm for x, y, z and p; degrees for a and b) and an optional path speed in mm/s."""
    parts = ["MOVE"]
    for axis in AXES:
        if axis in axes and axes[axis] is not None:
            parts.append(f"{axis.upper()}{float(axes[axis]):.4f}")
    unknown = set(axes) - set(AXES)
    if unknown:
        raise ValueError(f"unknown axes: {sorted(unknown)}")
    if len(parts) == 1:
        raise ValueError("a MOVE needs at least one axis")
    if feed is not None:
        parts.append(f"F{float(feed):.4f}")
    return " ".join(parts)
