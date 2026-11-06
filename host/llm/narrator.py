"""Narration: each step of a plan as one plain sentence, made by templates (no model), so what the person reads is what will run."""

TEMPLATES = {
    "home": "Home the machine.",
    "park": "Take the head to the park position.",
    "stop": "Stop (abort) the machine.",
    "move_to": "Move the tool tip to x={x:g}, y={y:g}, z={z:g} mm at {feed:g} mm/s.",
    "mount_tool": "Ask the person to mount the {tool} tool by hand and confirm.",
    "tool_on": "Switch the tool power on.",
    "tool_off": "Switch the tool power off.",
    "injector.prime": "Load {volume_ul:g} uL into the syringe.",
    "injector.inject": "Inject {volume_ul:g} uL at {rate_ul_s:g} uL/s.",
    "injector.wash": "Wash the syringe, {cycles:g} cycles.",
    "probe.touch": "Touch down with the probe from here.",
    "probe.find_surface": "Lower the probe at {approach_mm_s:g} mm/s until it touches the surface.",
    "probe.find_landmark": "Find the surface height at x={x:g}, y={y:g}.",
    "scalpel.set_depth_stop": "Set the blade depth stop to {depth_mm:g} mm.",
    "scalpel.change_blade": "Fit a new blade (guard closed).",
    "scalpel.incise": "Cut {length_mm:g} mm along the line at {depth_mm:g} mm deep, {feed_mm_s:g} mm/s.",
    "scalpel.cut_line": "Cut to x={x2:g}, y={y2:g} at {depth_mm:g} mm deep, {feed_mm_s:g} mm/s.",
    "drill.set_depth_stop": "Set the drill depth stop to {depth_mm:g} mm.",
    "drill.drill": "Drill {depth_mm:g} mm deep at {feed_mm_s:g} mm/s and {rpm:g} rpm.",
    "fluid.aspirate": "Aspirate {volume_ul:g} uL at {rate_ul_s:g} uL/s.",
    "fluid.irrigate": "Irrigate {volume_ul:g} uL at {rate_ul_s:g} uL/s.",
    "fluid.dispense_adhesive": "Dispense {volume_ul:g} uL of adhesive at {rate_ul_s:g} uL/s.",
    "fluid.purge": "Purge {volume_ul:g} uL through the lines.",
    "gripper.grip": "Grip the {item} ({width_mm:g} mm wide) with {force_n:g} N.",
    "gripper.release": "Open the jaws.",
    "gripper.place_implant": "Place the held item here.",
    "cautery.coagulate": "Coagulate with {power_w:g} W for {pulse_ms:g} ms.",
    "sensor.dark_reference": "Take a dark reference.",
    "sensor.read_fluorescence": "Read fluorescence for {integration_ms:g} ms.",
    "sensor.read_photometry": "Read photometry for {integration_ms:g} ms.",
}


def narrate_step(step):
    template = TEMPLATES.get(step.capability)
    if template is None:
        return f"(unknown step {step.capability})"
    try:
        sentence = template.format(**step.params)
    except (KeyError, ValueError):
        sentence = f"{step.capability} with {step.params} (the parameters do not fit the template)"
    return sentence


def narrate(plan):
    """The whole plan as numbered sentences, each with the reason the model gave, if any."""
    lines = [f"Goal: {plan.goal}  (version {plan.version}, hash {plan.hash[:12]})"]
    for i, step in enumerate(plan.steps, 1):
        lines.append(f"{i}. {narrate_step(step)}" + (f"  [reason: {step.note}]" if step.note else ""))
    return lines
