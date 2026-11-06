"""Wash station (card stn-wash): the sequence that cleans a tool between two uses, simulated with a simple carry-over model.

Each flush or dip leaves a fraction of what was on the tool (`residual`), so after n of them the carry-over is residual ** n. The
sequence does as many as it takes to get under `target`. The numbers are assumptions until the first wash is measured (a dye on the
tool and a photometric reading of the rinse). The geometry of the station is in cad/modules/stn_wash.py.
"""
import math

from .base import ToolFault

FLUID_CLASSES = ("injector", "fluid")


class WashStation:
    def __init__(self, target=1e-4, residual_flush=0.02, residual_dip=0.10, bath_uses_max=20):
        self.target = target
        self.residual_flush = residual_flush
        self.residual_dip = residual_dip
        self.bath_uses_max = bath_uses_max
        self.bath_uses = 0

    def cycles_needed(self, residual):
        return max(1, math.ceil(math.log(self.target) / math.log(residual)))

    def plan(self, tool):
        """The steps for this tool, as a list of (action, detail). Nothing moves: the host turns each step into moves and tool calls."""
        steps = [("move_to_station", "above the bath")]
        if tool.d["class"] in FLUID_CLASSES:
            n = self.cycles_needed(self.residual_flush)
            steps += [("flush", f"{n} cycles of solvent through the tool, to the waste")]
        else:
            n = self.cycles_needed(self.residual_dip)
            steps += [("dip", f"{n} dips in the bath"), ("wipe", "once across the wiper")]
        steps += [("dry", "above the air nozzle"), ("retract", "to the safe height")]
        return steps

    def wash(self, tool, carryover=1.0):
        """Runs the sequence on the model of a tool and returns the report. The tool must be unpowered, in no abort, and the bath fresh."""
        if tool.powered:
            raise ToolFault("powered", "never wash a powered tool: TOOL OFF first")
        if tool.aborted:
            raise ToolFault("aborted", "clear the abort first")
        if self.bath_uses >= self.bath_uses_max:
            raise ToolFault("bath_used", f"the bath has been used {self.bath_uses} times: change it")
        plan = self.plan(tool)
        fluid = tool.d["class"] in FLUID_CLASSES
        n = self.cycles_needed(self.residual_flush if fluid else self.residual_dip)
        if fluid:
            tool.power_on()
            try:
                if "wash" in tool.d["capabilities"]:
                    tool.run("wash", cycles=n)
                else:
                    for _ in range(n):
                        tool.run("irrigate", volume_ul=20.0, rate_ul_s=5.0)
                        tool.run("aspirate", volume_ul=20.0, rate_ul_s=5.0)
            finally:
                tool.power_off()
        residual = self.residual_flush if fluid else self.residual_dip
        self.bath_uses += 1
        remaining = carryover * residual**n
        return {"tool": tool.name, "steps": plan, "cycles": n, "carryover": remaining, "clean": remaining <= self.target * (1 + 1e-9)}

    def change_bath(self):
        self.bath_uses = 0
