"""A plan is a versioned list of steps. Its hash covers the goal, every step, the version and the hash of its parent, so a person who
approves a plan approves exactly that content: any change, however small, is a different plan that needs its own approval."""
import hashlib
import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    capability: str
    params: dict = field(default_factory=dict)
    note: str = ""  # why the model asked for it (shown to the person, never used by the validator)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class Plan:
    goal: str
    steps: tuple
    version: int = 1
    parent: str = ""  # hash of the plan this one revises

    @property
    def hash(self):
        body = {"goal": self.goal, "version": self.version, "parent": self.parent,
                "steps": [[s.capability, s.params, s.note] for s in self.steps]}
        return hashlib.sha256(canonical(body).encode("ascii")).hexdigest()

    def revise(self, steps):
        """The next version of this plan with other steps; it needs a new approval."""
        return Plan(self.goal, tuple(steps), self.version + 1, self.hash)

    @classmethod
    def from_dicts(cls, goal, steps, version=1, parent=""):
        """Builds a plan from what a model sends: a list of {"capability", "params", "note"}. Anything else raises ValueError."""
        built = []
        for i, raw in enumerate(steps):
            if not isinstance(raw, dict) or "capability" not in raw or not isinstance(raw.get("params", {}), dict):
                raise ValueError(f"step {i + 1} is not {{capability, params}}")
            extra = set(raw) - {"capability", "params", "note"}
            if extra:
                raise ValueError(f"step {i + 1} has unexpected fields {sorted(extra)}")
            built.append(Step(str(raw["capability"]), dict(raw.get("params", {})), str(raw.get("note", ""))))
        return cls(goal, tuple(built), version, parent)


@dataclass(frozen=True)
class Approval:
    plan_hash: str
    approver: str
    comment: str = ""
