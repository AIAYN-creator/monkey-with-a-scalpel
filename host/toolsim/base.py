"""Common base of the simulated tools: what every tool does with power, abort and its descriptor.

A model is built from a tool descriptor (tools/<name>/descriptor.yaml) and enforces its `limits`. An operation is a method called
`op_<capability>`, and the capabilities of the descriptor and the methods of the model must be the same set (checked in the tests).
Every number is provisional until it is measured.
"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import gen_tool_table as gen


class ToolFault(RuntimeError):
    """An operation was refused or interrupted. `code` is a short name the log and the tests can match."""

    def __init__(self, code, message=""):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


def load_descriptor(name):
    path = ROOT / "tools" / name / "descriptor.yaml"
    return gen.validate(gen.parse(path.read_text(encoding="utf-8")), str(path.relative_to(ROOT)))


class Tool:
    STEPS = 10  # an operation is simulated in this many steps so that an abort can arrive in the middle of it

    def __init__(self, descriptor, seed=1):
        self.d = descriptor
        self.name = descriptor["name"]
        self.limits = dict(descriptor.get("limits", {}))
        self.powered = False
        self.aborted = False
        self.interrupt = None  # test hook: called with (tool, fraction) in every step; it may call tool.abort()
        self.rng = random.Random(seed)
        self.events = []

    # ---- power and abort -------------------------------------------------------------------------------------------------
    def power_on(self):
        if self.aborted:
            raise ToolFault("aborted", "clear the abort before powering the tool")
        self.powered = True
        self.events.append("power_on")

    def power_off(self):
        self.powered = False
        self.events.append("power_off")

    def abort(self, reason="abort"):
        """The controller aborted: a tool that cuts its power on abort loses it at once, then the tool goes to its safe state."""
        self.aborted = True
        if self.d["power"]["cut_on_abort"]:
            self.powered = False
        self._safe()
        self.events.append(f"abort:{reason}")

    def clear(self):
        self.aborted = False
        self.events.append("clear")

    def _safe(self):
        """Safe state of the tool (see the safe_state of the descriptor). Overridden by the tools that have one beyond power."""

    # ---- operations ------------------------------------------------------------------------------------------------------
    def run(self, capability, **args):
        if capability not in self.d["capabilities"]:
            raise ToolFault("unknown_capability", f"{self.name} has no {capability}")
        if self.aborted:
            raise ToolFault("aborted", f"{self.name} is in the abort state")
        if self.d["power"]["max_current_a"] > 0 and not self.powered:
            raise ToolFault("not_powered", f"{capability} needs TOOL ON")
        result = getattr(self, "op_" + capability)(**args)
        self.events.append(f"done:{capability}")
        return result

    def _step(self, fraction):
        """Called inside an operation, once per step: the hook of the tests may abort here and the operation stops."""
        if self.interrupt is not None:
            self.interrupt(self, fraction)
        if self.aborted:
            raise ToolFault("aborted", f"interrupted at {fraction:.0%}")

    def _limit(self, key, value, name=None, minimum=0.0):
        if not minimum <= value <= self.limits[key]:
            raise ToolFault("limit", f"{name or key} {value} outside {minimum} to {self.limits[key]}")

    def operations(self):
        return sorted(n[3:] for n in dir(self) if n.startswith("op_"))
