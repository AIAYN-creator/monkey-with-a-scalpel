"""The simulated world a plan runs on: the machine state and the tool models. The validator dry-runs a plan on a fresh copy of it and the
executor runs the approved plan on another, so a plan is checked with the same code that runs it.

Positions are tip positions in machine mm. `surface_z` is the height of the sample surface and `signal` the light the sensor would see,
both set by the test or the scenario. A real machine would replace this class with an adapter over `link.Session` and the camera loop.
"""
from toolsim import ToolFault, build

from .capabilities import MACHINE, STEP_MS, all_capabilities, tools


class PlanError(RuntimeError):
    """A step breaks a rule of the machine (not a limit of a tool: those are ToolFault). `rule` is a short name."""

    def __init__(self, rule, message):
        super().__init__(f"{rule}: {message}")
        self.rule = rule


class World:
    def __init__(self, surface_z=20.0, signal=500.0, seed=1):
        self.pos = [0.0, 0.0, MACHINE["z"][1]]
        self.homed = False
        self.parked = True
        self.tool = None
        self.models = {name: build(name, seed) for name in tools()}
        self.surface_z = surface_z
        self.signal = signal
        self.now_ms = 0.0
        self.aborted = False
        self.executed = []  # (capability, params, result)

    # ---- helpers ---------------------------------------------------------------------------------------------------------
    def surface_at(self, x, y):
        return self.surface_z

    @property
    def model(self):
        if self.tool is None:
            raise PlanError("no_tool", "no tool is mounted")
        return self.models[self.tool]

    def _tick(self):
        self.now_ms += STEP_MS
        for model in self.models.values():
            if hasattr(model, "advance"):
                model.advance(STEP_MS)

    # ---- machine capabilities --------------------------------------------------------------------------------------------
    def apply(self, capability, params, human=None):
        """Runs one step. Raises PlanError for a machine rule and ToolFault for a limit of a tool."""
        if self.aborted:
            raise PlanError("aborted", "the machine is in the abort state")
        if capability not in all_capabilities():
            raise PlanError("unknown_capability", capability)
        self._tick()
        if "." in capability:
            tool, cap = capability.split(".", 1)
            if self.tool != tool:
                raise PlanError("wrong_tool", f"{capability} needs {tool} mounted, the mounted tool is {self.tool}")
            result = self._tool_call(cap, params)
        else:
            result = getattr(self, "do_" + capability)(**params, **({"human": human} if capability == "mount_tool" else {}))
        self.executed.append((capability, dict(params), result))
        return result

    def do_home(self):
        self.homed = True
        self.pos = [0.0, 0.0, MACHINE["z"][1]]
        return {"homed": True}

    def do_park(self):
        self._require_homed()
        self.pos = [0.0, 0.0, MACHINE["z"][1]]
        self.parked = True
        return {"parked": True}

    def do_stop(self):
        self.abort("stop step")
        return {"stopped": True}

    def do_move_to(self, x, y, z, feed):
        self._require_homed()
        self.pos = [float(x), float(y), float(z)]
        self.parked = False
        return {"pos": tuple(self.pos)}

    def do_mount_tool(self, tool, human=None):
        self._require_homed()
        if tool not in self.models:
            raise PlanError("unknown_tool", tool)
        if not self.parked:
            raise PlanError("not_parked", "park the tool head before changing the tool")
        if self.tool is not None and self.models[self.tool].powered:
            raise PlanError("tool_powered", "TOOL OFF before changing the tool")
        if human is not None and not human.confirm(f"Mount the {tool} tool by hand, then confirm"):
            raise PlanError("not_confirmed", "the person did not confirm the tool change")
        self.tool = tool
        return {"tool": tool}

    def do_tool_on(self):
        self.model.power_on()
        return {"powered": True}

    def do_tool_off(self):
        self.model.power_off()
        return {"powered": False}

    def _require_homed(self):
        if not self.homed:
            raise PlanError("not_homed", "home the machine first")

    # ---- tool capabilities -----------------------------------------------------------------------------------------------
    def _tool_call(self, cap, p):
        self._require_homed()
        m, z = self.model, self.pos[2]
        run = m.run
        if cap == "find_surface":
            return run("find_surface", surface_z=self.surface_z, start_z=z, approach_mm_s=p["approach_mm_s"])
        if cap == "touch":
            return run("touch", surface_z=self.surface_z, start_z=z)
        if cap == "find_landmark":
            return run("find_landmark", surface_z_at=self.surface_at, start_z=z, point_xy=(p["x"], p["y"]))
        if cap == "cut_line":
            dx, dy = p["x2"] - self.pos[0], p["y2"] - self.pos[1]
            return run("cut_line", points=[(0.0, 0.0), (dx, dy)], depth_mm=p["depth_mm"], feed_mm_s=p["feed_mm_s"])
        if cap == "place_implant":
            return run("place_implant", target_xyz=tuple(self.pos))
        if cap in ("read_fluorescence", "read_photometry"):
            return run(cap, integration_ms=p["integration_ms"], rate_counts_s=self.signal)
        return run(cap, **p)

    # ---- abort ------------------------------------------------------------------------------------------------------------
    def abort(self, reason="abort"):
        self.aborted = True
        for model in self.models.values():
            model.abort(reason)


__all__ = ["PlanError", "ToolFault", "World"]
