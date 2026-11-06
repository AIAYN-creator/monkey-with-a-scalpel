"""The loop between a language model and the machine: propose, validate, narrate, approve, execute, log.

The model is any object with `propose(goal, description, feedback) -> list of step dicts`; `ScriptedLLM` answers from a script, which is
what the tests and the simulations use, so the whole loop runs without a model. The person is any object with `review(plan, narration,
report) -> (bool, comment)`, `confirm(text) -> bool` and `stop_requested(step) -> bool`. Nothing runs without an `Approval` that carries the
exact hash of the plan, and every event goes to a hash-chained log (link.ChainLog).
"""
from dataclasses import dataclass, field

from link import ChainLog
from toolsim import ToolFault

from .capabilities import describe
from .narrator import narrate, narrate_step
from .plan import Approval, Plan
from .validator import validate
from .world import PlanError, World


class Unapproved(RuntimeError):
    """The plan to run is not the one that was approved."""


class ScriptedLLM:
    """Answers from a list: each call to `propose` returns the next list of steps. It keeps what it was asked, so a test can check the feedback."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def propose(self, goal, description, feedback):
        self.calls.append({"goal": goal, "description": description, "feedback": feedback})
        if not self.script:
            return []
        return self.script.pop(0)


class ScriptedHuman:
    """A person who answers from fixed rules: approves unless told otherwise, confirms tool changes, presses stop at a chosen step."""

    def __init__(self, approve=True, confirm=True, stop_at=None, approver="tester", comments=()):
        self.approve, self.confirm_all, self.stop_at, self.approver = approve, confirm, stop_at, approver
        self.reviewed, self.confirmed, self.comments = [], [], list(comments)

    def review(self, plan, narration, report):
        self.reviewed.append((plan.hash, list(narration)))
        approve = self.approve.pop(0) if isinstance(self.approve, list) else self.approve
        return (Approval(plan.hash, self.approver), "") if approve else (None, self.comments.pop(0) if self.comments else "not approved")

    def confirm(self, text):
        self.confirmed.append(text)
        return self.confirm_all

    def stop_requested(self, step):
        return self.stop_at is not None and step >= self.stop_at


@dataclass
class Result:
    status: str  # done, aborted, gave_up
    plan: Plan = None
    reason: str = ""
    executed: list = field(default_factory=list)
    narration: list = field(default_factory=list)


def execute(plan, approval, world, human, log):
    """Runs an approved plan on a world. Stops at the first fault or when the person presses stop, with an abort of the tools."""
    if approval is None or approval.plan_hash != plan.hash:
        raise Unapproved("the approval is not for this exact plan")
    log.append(event="execution_start", plan=plan.hash, approver=approval.approver)
    for i, step in enumerate(plan.steps, 1):
        if human.stop_requested(i):
            world.abort("person pressed stop")
            log.append(event="aborted", step=i, reason="person pressed stop")
            return Result("aborted", plan, "the person pressed stop", list(world.executed))
        log.append(event="step_start", step=i, capability=step.capability, params=step.params, narration=narrate_step(step))
        try:
            result = world.apply(step.capability, step.params, human=human)
        except (PlanError, ToolFault) as error:
            world.abort(str(error))
            log.append(event="fault", step=i, error=str(error))
            return Result("aborted", plan, str(error), list(world.executed))
        log.append(event="step_done", step=i, result=repr(result))
    log.append(event="execution_end", plan=plan.hash)
    return Result("done", plan, "", list(world.executed))


def run_session(goal, llm, human, log_path, world_factory=World, max_rounds=3):
    """Asks the model for a plan until one passes the validator and the person, then executes it. Returns a Result."""
    log = ChainLog(log_path)
    log.append(event="session_start", goal=goal)
    feedback, previous = None, None
    for round_number in range(1, max_rounds + 1):
        raw = llm.propose(goal, describe(), feedback)
        try:
            plan = Plan.from_dicts(goal, raw, round_number, previous.hash if previous else "")
        except ValueError as error:
            feedback = [f"plan: malformed: {error}"]
            log.append(event="malformed", round=round_number, error=str(error))
            continue
        previous = plan
        log.append(event="plan_proposed", version=plan.version, plan=plan.hash, steps=len(plan.steps))
        report = validate(plan, world_factory)
        log.append(event="validation", plan=plan.hash, ok=report.ok, violations=report.messages())
        if not report.ok:
            feedback = report.messages()
            continue
        narration = narrate(plan)
        approval, comment = human.review(plan, narration, report)
        log.append(event="review", plan=plan.hash, approved=approval is not None, comment=comment)
        if approval is None:
            feedback = [f"the person did not approve: {comment}"]
            continue
        result = execute(plan, approval, world_factory(), human, log)
        result.narration = narration
        log.append(event="session_end", status=result.status, reason=result.reason)
        return result
    log.append(event="session_end", status="gave_up", reason=f"no approved plan in {max_rounds} rounds")
    return Result("gave_up", previous, f"no approved plan in {max_rounds} rounds")
