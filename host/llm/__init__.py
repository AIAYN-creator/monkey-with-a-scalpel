"""The interface between a language model and the machine (card sw-llm). The model is free: it fetches documents, proposes anything and
as much as it wants, with no quota. The person decides. Machine plans use a list of capabilities, an advisory validator, approval bound
to the hash and a hash-chained log."""
from .proposals import Entry, Proposal, ProposalBox
from .research import Document, Library
from .capabilities import all_capabilities, check_tables, describe
from .narrator import narrate, narrate_step
from .plan import Approval, Plan, Step
from .run import Result, ScriptedHuman, ScriptedLLM, Unapproved, execute, run_session
from .validator import Report, Violation, validate
from .world import PlanError, World

__all__ = ["Document", "Entry", "Library", "Proposal", "ProposalBox", "Approval", "Plan", "PlanError", "Report", "Result", "ScriptedHuman", "ScriptedLLM", "Step", "Unapproved", "Violation", "World",
           "all_capabilities", "check_tables", "describe", "execute", "narrate", "narrate_step", "run_session", "validate"]
