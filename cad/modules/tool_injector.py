"""Injector tool (card t-inject): the Hamilton syringe and the plunger actuator, which is the tool head the rest of the CAD is built with.

Its parts are the ones in cad/parts.py (clamp, backplate, motor mount, coupler); this module only gives the head the same description as
the other tools (`TOOL` and `assembly()`), so that cad/tool_check.py treats every tool in the same way. The descriptor is
tools/injector/descriptor.yaml and the model host/toolsim (volume quantised to the micro-steps of the plunger).
"""
PARTS = {}

TOOL = {
    "name": "injector",
    "tip_z": -30.0,
    "tip_item": "syringe_needle",
    "dummy_mass_g": {"syringe_barrel": 8.0, "syringe_plunger": 1.0, "syringe_needle": 0.5, "actuator_body": 80.0, "actuator_shaft": 5.0},
}
TOOL_ALLOWED = {
    frozenset(("syringe_barrel", "hamilton_clamp")),
    frozenset(("actuator_body", "actuator_shaft")),
    frozenset(("syringe_barrel", "syringe_plunger")),
    frozenset(("syringe_barrel", "syringe_needle")),
    frozenset(("syringe_barrel", "plunger_coupler")),
    frozenset(("syringe_plunger", "plunger_coupler")),
    frozenset(("actuator_shaft", "plunger_coupler")),
    frozenset(("hamilton_clamp", "syringe_needle")),
}


def assembly():
    import system  # imported here: system imports the modules, so a top-level import would be circular

    head = system.tool_head()
    return {name: (shape, "dummy" if name.startswith(("syringe", "actuator")) else "printed") for name, shape in head.items() if name != "tool_backplate"}
