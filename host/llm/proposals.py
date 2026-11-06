"""Open proposals: the model may propose anything and as much as it wants; the person decides.

A proposal has a free `kind` (a decision, a design change, a paper to read, a plan to run, a question, something nobody has named yet),
a title, a body and references to the library documents it rests on. It may carry a machine plan; then the validator's findings travel
with it as advice for the person, they never stop the proposal from being made. There is no list of allowed kinds, no cap on how many
proposals or how long they are, and no budget of attempts. The only gate is the person: nothing is acted on without an approval that
carries the exact hash of the proposal.
"""
import hashlib
from dataclasses import dataclass, field

from .plan import Approval, Plan, canonical
from .validator import validate


@dataclass(frozen=True)
class Proposal:
    kind: str
    title: str
    body: str
    refs: tuple = ()  # ids of library documents it cites
    plan: Plan = None  # optional machine plan that goes with it

    @property
    def hash(self):
        body = {"kind": self.kind, "title": self.title, "body": self.body, "refs": list(self.refs),
                "plan": self.plan.hash if self.plan else ""}
        return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


@dataclass
class Entry:
    proposal: Proposal
    advice: list = field(default_factory=list)  # validator findings, if it carries a plan
    status: str = "pending"  # pending, approved, rejected
    comment: str = ""
    approval: Approval = None


class ProposalBox:
    """Everything the model proposes lands here; the person approves or rejects each one."""

    def __init__(self, log=None, world_factory=None):
        self.entries, self.log, self.world_factory = {}, log, world_factory

    def submit(self, proposal):
        advice = []
        if proposal.plan is not None:
            report = validate(proposal.plan) if self.world_factory is None else validate(proposal.plan, self.world_factory)
            advice = report.messages()
        self.entries[proposal.hash] = Entry(proposal, advice)
        if self.log is not None:
            self.log.append(event="proposal_submitted", hash=proposal.hash, kind=proposal.kind, title=proposal.title,
                            refs=list(proposal.refs), advice=advice)
        return self.entries[proposal.hash]

    def pending(self):
        return [e for e in self.entries.values() if e.status == "pending"]

    def decide(self, proposal_hash, approved, approver, comment=""):
        entry = self.entries[proposal_hash]
        entry.status, entry.comment = ("approved" if approved else "rejected"), comment
        entry.approval = Approval(proposal_hash, approver, comment) if approved else None
        if self.log is not None:
            self.log.append(event="proposal_decided", hash=proposal_hash, status=entry.status, approver=approver, comment=comment)
        return entry
