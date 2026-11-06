"""Tests of the LLM interface: the validator, the approval bound to the hash of the plan, the narration, the log and a complete
simulated session with the model replaced by a script. Usage, from the repository root:

    python host/llm/test_llm.py

Exit code 1 on a failure.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from link import ChainLog

from llm import (
    Approval,
    Library,
    Plan,
    Proposal,
    ProposalBox,
    ScriptedHuman,
    ScriptedLLM,
    Step,
    Unapproved,
    World,
    all_capabilities,
    check_tables,
    describe,
    execute,
    narrate,
    run_session,
    validate,
)

FAILURES = []


def check(condition, message):
    if not condition:
        FAILURES.append(message)
        print("  FAIL:", message)


def s(capability, note="", **params):
    return {"capability": capability, "params": params, "note": note}


GOOD = [
    s("home"),
    s("mount_tool", "the syringe", tool="injector"),
    s("tool_on"),
    s("injector.prime", volume_ul=2.0),
    s("move_to", x=0.0, y=0.0, z=30.0, feed=10.0),
    s("move_to", "approach the target", x=5.0, y=5.0, z=8.0, feed=2.0),
    s("injector.inject", "the dose", volume_ul=1.0, rate_ul_s=0.5),
    s("move_to", x=5.0, y=5.0, z=30.0, feed=5.0),
    s("tool_off"),
    s("park"),
]


def plan_of(steps, goal="inject 1 uL"):
    return Plan.from_dicts(goal, steps)


def rule_of(steps):
    report = validate(plan_of(steps))
    return [(v.step, v.rule) for v in report.violations]


def test_tables():
    print("capabilities")
    check(check_tables() == [], f"the capability table and the descriptors agree ({check_tables()})")
    text = describe()
    check("injector.inject" in text and "max_dose_ul=5.0" in text and "move_to" in text, "the description lists the capabilities and the limits of the descriptors")
    check("never ask for anything not listed" in text.lower() or "never ask for anything not listed" in text, "the description says the list is closed")
    check(len(all_capabilities()) >= 30, "the list has the machine and every tool capability")


def test_valid_plan():
    print("a valid plan")
    report = validate(plan_of(GOOD))
    check(report.ok and report.end_state["tool"] == "injector" and report.end_state["parked"], f"the plan passes ({report.messages()})")
    p1 = plan_of(GOOD)
    p2 = plan_of(GOOD)
    check(p1.hash == p2.hash and len(p1.hash) == 64, "the same plan has the same hash")


def test_static_rules():
    print("static rules")
    check(rule_of([s("shell.run", cmd="rm -rf /")]) == [(1, "unknown_capability")], "an unknown capability is refused")
    check(rule_of([s("move_to", x=0.0, y=0.0, z=10.0)]) == [(1, "missing_parameter")], "a missing parameter is refused")
    check(rule_of([s("home", speed=3)]) == [(1, "unexpected_parameter")], "an extra parameter is refused")
    check(rule_of([s("move_to", x=900.0, y=0.0, z=10.0, feed=5.0)]) == [(1, "range")], "a position outside the travel is refused")
    check(rule_of([s("move_to", x="5", y=0.0, z=10.0, feed=5.0)]) == [(1, "type")], "a text where a number goes is refused")
    check(rule_of([s("move_to", x=True, y=0.0, z=10.0, feed=5.0)]) == [(1, "type")], "a boolean is not a number")
    check(rule_of([s("mount_tool", tool="")]) == [(1, "type")], "an empty text is refused")
    check(rule_of([]) == [(0, "empty")], "an empty plan is refused")
    check(rule_of([s("home")] * 500) == [], "there is no cap on the number of steps")
    p = Plan("x", (Step("home", {"speed": 1}),))
    check(not validate(p).ok, "a step built directly is checked too")


def test_dry_run_rules():
    print("dry-run rules")
    check(rule_of([s("move_to", x=0.0, y=0.0, z=10.0, feed=5.0)])[0] == (1, "not_homed"), "a move before homing is refused")
    check(rule_of([s("home"), s("injector.prime", volume_ul=1.0)])[0] == (2, "wrong_tool"), "a tool operation without the tool is refused")
    check(rule_of([s("home"), s("mount_tool", tool="injector"), s("injector.prime", volume_ul=1.0)])[0] == (3, "not_powered"), "a tool operation without TOOL ON is refused")
    check(rule_of([s("home"), s("move_to", x=1.0, y=1.0, z=50.0, feed=5.0), s("mount_tool", tool="probe")])[0] == (3, "not_parked"), "a tool change away from the park position is refused")
    check(rule_of([s("home"), s("mount_tool", tool="injector"), s("tool_on"), s("mount_tool", tool="probe")])[0][1] == "tool_powered", "a tool change with the tool powered is refused")
    check(rule_of([s("home"), s("mount_tool", tool="laser")])[0] == (2, "unknown_tool"), "an unknown tool is refused")
    over = GOOD[:6] + [s("injector.inject", volume_ul=6.0, rate_ul_s=0.5)] + GOOD[7:]
    check(rule_of(over)[0] == (7, "limit"), "a dose over the descriptor's limit is refused at its step")
    check(rule_of(GOOD[:7] + [s("injector.inject", volume_ul=3.0, rate_ul_s=0.5)] + GOOD[7:])[0] == (8, "empty"), "more than the loaded volume is refused")
    drill = [s("home"), s("mount_tool", tool="drill"), s("tool_on"), s("drill.drill", depth_mm=0.5, feed_mm_s=0.2, rpm=10000)]
    check(rule_of(drill)[0] == (4, "no_depth_stop"), "drilling without a depth stop is refused")
    cut = [s("home"), s("mount_tool", tool="scalpel"), s("tool_on"), s("scalpel.change_blade"), s("scalpel.set_depth_stop", depth_mm=1.0),
           s("scalpel.incise", length_mm=5.0, depth_mm=2.0, feed_mm_s=2.0)]
    check(rule_of(cut)[0] == (6, "depth"), "a cut deeper than the depth stop is refused")
    burn = [s("home"), s("mount_tool", tool="cautery"), s("tool_on"), s("cautery.coagulate", power_w=3.0, pulse_ms=200)]
    check(rule_of(burn)[0] == (4, "energy"), "a cautery pulse over the energy limit is refused")
    check(rule_of(GOOD[:8])[-1] == (0, "ends_unsafe"), "a plan that ends with the tool powered is refused")
    check(rule_of(GOOD[:8] + [s("tool_off")])[-1] == (0, "ends_unsafe"), "a plan that ends away from the park position is refused")
    check(rule_of([s("home"), s("stop"), s("move_to", x=0.0, y=0.0, z=10.0, feed=5.0)])[0] == (3, "aborted"), "nothing runs after a stop")


def test_approval_bound_to_hash():
    print("approval is bound to the exact plan")
    plan = plan_of(GOOD)
    log_dir = tempfile.mkdtemp()
    log = ChainLog(Path(log_dir) / "a.log")
    approval = Approval(plan.hash, "ana")
    changed = plan.revise(list(plan.steps))
    check(changed.hash != plan.hash and changed.version == 2 and changed.parent == plan.hash, "a revision is another plan, with the parent hash")
    try:
        execute(changed, approval, World(), ScriptedHuman(), log)
        check(False, "a revised plan runs with the old approval")
    except Unapproved:
        check(True, "a revised plan does not run with the old approval")
    edited = Plan(plan.goal, plan.steps[:6] + (Step("injector.inject", {"volume_ul": 4.0, "rate_ul_s": 0.5}),) + plan.steps[7:], plan.version, plan.parent)
    try:
        execute(edited, approval, World(), ScriptedHuman(), log)
        check(False, "a plan with one edited number runs with the old approval")
    except Unapproved:
        check(True, "a plan with one edited number does not run with the old approval")
    try:
        execute(plan, None, World(), ScriptedHuman(), log)
        check(False, "a plan runs without approval")
    except Unapproved:
        check(True, "a plan does not run without approval")
    result = execute(plan, approval, World(), ScriptedHuman(), log)
    check(result.status == "done", f"the approved plan runs ({result.status} {result.reason})")


def test_narration():
    print("narration")
    lines = narrate(plan_of(GOOD))
    check(lines[0].startswith("Goal: inject 1 uL") and len(lines) == len(GOOD) + 1, "one line per step and a header")
    check("Inject 1 uL at 0.5 uL/s." in lines[7] and "[reason: the dose]" in lines[7], "the sentence says the numbers and the reason")
    check("Ask the person to mount the injector tool" in lines[2], "a tool change is described as a request to the person")


def test_session():
    print("a complete session with the model replaced by a script")
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "session.log"
        worlds = []

        def factory():
            worlds.append(World())
            return worlds[-1]

        bad = GOOD[:6] + [s("injector.inject", volume_ul=6.0, rate_ul_s=0.5)] + GOOD[7:]
        llm = ScriptedLLM([bad, GOOD])
        human = ScriptedHuman()
        result = run_session("inject 1 uL at the target", llm, human, log_path, factory, strict=True)
        check(result.status == "done", f"the session ends done ({result.status}, {result.reason})")
        check(len(llm.calls) == 2 and llm.calls[0]["feedback"] is None, "the model is called twice, the first time without feedback")
        check(any("step 7" in line and "limit" in line for line in llm.calls[1]["feedback"]), f"the refusal reaches the model as feedback ({llm.calls[1]['feedback']})")
        check("injector.inject" in llm.calls[0]["description"], "the model is told the capabilities")
        check(len(human.reviewed) == 1, "the person only sees the plan that passed the validator")
        check(len(human.confirmed) == 1 and "injector" in human.confirmed[0], "the person is asked to confirm the tool change")
        executed = worlds[-1].executed
        check([c for c, _p, _r in executed][-3:] == ["tool_off", "park", "park"][-3:] or executed[-1][0] == "park", "the last executed step is park")
        delivered = [r["delivered_ul"] for c, _p, r in executed if c == "injector.inject"]
        check(len(delivered) == 1 and abs(delivered[0] - 1.0) < 0.001, f"1 uL was delivered ({delivered})")
        ok, count, _last = ChainLog.verify(log_path)
        text = log_path.read_text(encoding="utf-8")
        check(ok and count > 20, f"the log verifies ({count} entries)")
        check(text.count("plan_proposed") == 2, "both plans are in the log")
        check("session_end" in text and "execution_end" in text and "step_done" in text, "the log has the end of the session and every step")
        lines = text.splitlines()
        i = next(k for k, line in enumerate(lines) if '"event": "validation"' in line)
        lines[i] = lines[i].replace("validation", "validatiom", 1)
        Path(log_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        check(not ChainLog.verify(log_path)[0], "an edited entry breaks the chain")


def test_rejection_and_giving_up():
    print("rejection, malformed output and giving up")
    with tempfile.TemporaryDirectory() as tmp:
        llm = ScriptedLLM([GOOD, GOOD])
        human = ScriptedHuman(approve=[False, True], comments=["do it more slowly"])
        result = run_session("g", llm, human, Path(tmp) / "a.log")
        check(result.status == "done" and "do it more slowly" in llm.calls[1]["feedback"][0], "a rejection and its comment go back to the model, then the next plan runs")
        check(result.plan.version == 2 and result.plan.parent != "", "the second plan is version 2 and names its parent")
        llm = ScriptedLLM(["not a list", [{"capability": "home", "params": {}, "evil": 1}], [["home"]]])
        result = run_session("g", llm, ScriptedHuman(), Path(tmp) / "b.log")
        check(result.status == "gave_up" and "malformed" in llm.calls[1]["feedback"][0], "malformed output is not run; the session ends when the model has nothing more")
        result = run_session("g", ScriptedLLM([]), ScriptedHuman(), Path(tmp) / "c.log")
        check(result.status == "gave_up", "a model that proposes nothing leads to giving up")
        check(ChainLog.verify(Path(tmp) / "c.log")[0], "the log of a failed session verifies too")


def test_abort_paths():
    print("abort paths")
    with tempfile.TemporaryDirectory() as tmp:
        log = ChainLog(Path(tmp) / "x.log")
        plan = plan_of(GOOD)
        approval = Approval(plan.hash, "ana")
        world = World()
        result = execute(plan, approval, world, ScriptedHuman(stop_at=7), log)
        check(result.status == "aborted" and world.aborted and "stop" in result.reason, "the person pressing stop aborts at that step")
        check(world.models["injector"].aborted and len(world.executed) == 6, "the steps after it did not run and the tool is in the abort state")
        probe = [s("home"), s("mount_tool", tool="probe"), s("tool_on"), s("move_to", x=0.0, y=0.0, z=30.0, feed=5.0), s("probe.find_surface", approach_mm_s=1.0),
                 s("tool_off"), s("park")]
        p = plan_of(probe)
        check(validate(p).ok, "the probe plan is valid on the world the validator knows")
        world = World(surface_z=-40.0)  # the real surface is not where the model thought it was
        result = execute(p, Approval(p.hash, "ana"), world, ScriptedHuman(), log)
        check(result.status == "aborted" and "no_contact" in result.reason and world.aborted, "a fault while running aborts the machine")
        check(ChainLog.verify(Path(tmp) / "x.log")[0] and "fault" in (Path(tmp) / "x.log").read_text(encoding="utf-8"), "the fault is in the log")
        world = World()
        result = execute(plan, Approval(plan.hash, "ana"), world, ScriptedHuman(confirm=False), log)
        check(result.status == "aborted" and "not_confirmed" in result.reason, "a tool change the person does not confirm stops the plan")
        drill = plan_of([s("home"), s("mount_tool", tool="drill"), s("tool_on"), s("drill.set_depth_stop", depth_mm=1.0)])
        world = World()
        execute(drill, Approval(drill.hash, "ana"), world, ScriptedHuman(stop_at=4), log)
        check(not world.models["drill"].powered, "a stop cuts the power of the drill at once (cut on abort)")


def test_freedom():
    print("the model is free: any proposal, any source, no quota")
    with tempfile.TemporaryDirectory() as tmp:
        log = ChainLog(Path(tmp) / "free.log")
        pages = {"https://example.org/paper-a": "Paper A: a method for sub-micron stages", "/local/datasheet.pdf": b"%PDF datasheet"}
        lib = Library(Path(tmp) / "lib", lambda src: pages.get(src, f"content of {src}"), log)
        docs = [lib.fetch(src) for src in pages] + [lib.fetch(f"https://example.org/p{i}") for i in range(300)]
        check(len(lib.documents) == 302, "300 more documents are fetched without a limit or a list of allowed sources")
        check("sub-micron" in lib.text(docs[0].id) and lib.read(docs[1].id).startswith(b"%PDF"), "what was fetched can be read again")
        check(lib.fetch("https://example.org/paper-a").id == docs[0].id, "the same content is the same document")
        box = ProposalBox(log)
        kinds = ["decision", "design change", "paper to read", "a question", "something nobody has named", "x" * 5000]
        for i, kind in enumerate(kinds):
            box.submit(Proposal(kind, f"proposal {i}", "body " * 2000, (docs[0].id,)))
        check(len(box.pending()) == len(kinds), "every kind of proposal is accepted, whatever its name or length")
        bad = plan_of([s("move_to", x=900.0, y=0.0, z=10.0, feed=5.0)])
        entry = box.submit(Proposal("plan", "a plan that breaks a limit", "why", (), bad))
        check(entry.status == "pending" and any("range" in a for a in entry.advice), "a plan with findings is still proposed; the findings are advice")
        approved = box.decide(entry.proposal.hash, True, "ana", "I want to see it")
        check(approved.approval.plan_hash == entry.proposal.hash, "the approval carries the hash of the proposal")
        other = Proposal("plan", "a plan that breaks a limit", "why, but changed", (), bad)
        check(other.hash != entry.proposal.hash, "any change to a proposal is a different proposal")
        for _ in range(60):
            box.submit(Proposal("more", f"n{_}", "b"))
        check(len(box.entries) == len(kinds) + 61, "there is no cap on how many proposals the model makes")
        # advisory session: a plan with findings reaches the person, who decides
        bad_session = GOOD[:6] + [s("injector.inject", volume_ul=6.0, rate_ul_s=0.5)] + GOOD[7:]
        human = ScriptedHuman(approve=False, comments=["no"])
        llm = ScriptedLLM([bad_session] + [GOOD] * 10)
        result = run_session("g", llm, human, Path(tmp) / "adv.log", max_rounds=2)
        check(len(human.reviewed) == 2 and result.status == "gave_up", "by default the person sees a plan even with findings and decides")
        text = (Path(tmp) / "free.log").read_text(encoding="utf-8")
        check("document_fetched" in text and "proposal_submitted" in text and "proposal_decided" in text, "fetches, proposals and decisions are logged")
        check(ChainLog.verify(Path(tmp) / "free.log")[0], "the log of the free session verifies")


def main():
    for test in (test_tables, test_valid_plan, test_static_rules, test_dry_run_rules, test_approval_bound_to_hash, test_narration,
                 test_session, test_rejection_and_giving_up, test_abort_paths, test_freedom):
        test()
    print("LLM OK" if not FAILURES else f"LLM FAILED: {len(FAILURES)} checks")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
