"""The deterministic validator: it contains no AI and no randomness. It checks a plan in two passes and says exactly which step breaks which
rule, so the model can be told what to fix and the person can see why a plan was refused.

1. Static: every step names a known capability with exactly its parameters, numbers inside the range of the capability. There is no cap on the number of steps.
   The validator advises the person; it does not limit what the model may propose (see run_session and proposals).
2. Dry run: the plan runs on a fresh simulated world (the same code the executor uses). A machine rule (`PlanError`) or a limit of a
   tool (`ToolFault`, from the descriptor) stops the run at that step. The plan must also end safe: tool off and the head parked.
"""
from dataclasses import dataclass, field

from toolsim import ToolFault

from .capabilities import all_capabilities
from .world import PlanError, World


@dataclass
class Violation:
    step: int  # 1-based; 0 for the plan as a whole
    rule: str
    message: str

    def __str__(self):
        where = f"step {self.step}" if self.step else "plan"
        return f"{where}: {self.rule}: {self.message}"


@dataclass
class Report:
    violations: list = field(default_factory=list)
    end_state: dict = field(default_factory=dict)

    @property
    def ok(self):
        return not self.violations

    def messages(self):
        return [str(v) for v in self.violations]


def static_check(plan):
    found = []
    caps = all_capabilities()
    if not plan.steps:
        found.append(Violation(0, "empty", "the plan has no steps"))
    for i, step in enumerate(plan.steps, 1):
        schema = caps.get(step.capability)
        if schema is None:
            found.append(Violation(i, "unknown_capability", f"{step.capability!r} is not in the list"))
            continue
        missing, extra = set(schema) - set(step.params), set(step.params) - set(schema)
        if missing:
            found.append(Violation(i, "missing_parameter", f"{step.capability} needs {sorted(missing)}"))
        if extra:
            found.append(Violation(i, "unexpected_parameter", f"{step.capability} does not take {sorted(extra)}"))
        for name, rng in schema.items():
            if name not in step.params:
                continue
            value = step.params[name]
            if rng == "text":
                if not isinstance(value, str) or not value:
                    found.append(Violation(i, "type", f"{name} must be a non-empty text"))
            elif isinstance(value, bool) or not isinstance(value, (int, float)):
                found.append(Violation(i, "type", f"{name} must be a number, got {value!r}"))
            elif not rng[0] <= value <= rng[1]:
                found.append(Violation(i, "range", f"{name} = {value} is outside {rng[0]} to {rng[1]}"))
    return found


class _AutoConfirm:
    def confirm(self, _text):
        return True


def validate(plan, world_factory=World):
    """Checks a plan. `world_factory` gives a fresh world; the plan never touches the real one."""
    report = Report(violations=static_check(plan))
    if report.violations:
        return report
    world = world_factory()
    for i, step in enumerate(plan.steps, 1):
        try:
            world.apply(step.capability, step.params, human=_AutoConfirm())
        except (PlanError, ToolFault) as error:
            report.violations.append(Violation(i, getattr(error, "rule", None) or getattr(error, "code", "fault"), str(error)))
            return report
    if world.tool is not None and world.models[world.tool].powered:
        report.violations.append(Violation(0, "ends_unsafe", f"the plan ends with the {world.tool} tool powered: finish with tool_off"))
    if not world.parked:
        report.violations.append(Violation(0, "ends_unsafe", "the plan ends with the head away from the park position: finish with park"))
    report.end_state = {"tool": world.tool, "pos": tuple(world.pos), "parked": world.parked}
    return report
