"""The interface between a language model and the machine (card sw-llm): a closed list of capabilities, a deterministic validator,
human approval bound to the hash of the plan, narration and a hash-chained log."""
from .capabilities import all_capabilities, check_tables, describe
from .narrator import narrate, narrate_step
from .plan import Approval, Plan, Step
from .run import Result, ScriptedHuman, ScriptedLLM, Unapproved, execute, run_session
from .validator import Report, Violation, validate
from .world import PlanError, World

__all__ = ["Approval", "Plan", "PlanError", "Report", "Result", "ScriptedHuman", "ScriptedLLM", "Step", "Unapproved", "Violation", "World",
           "all_capabilities", "check_tables", "describe", "execute", "narrate", "narrate_step", "run_session", "validate"]
