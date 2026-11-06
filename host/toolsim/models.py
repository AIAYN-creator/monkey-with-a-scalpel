"""Simulated models of the eight tools. Each one enforces the `limits` of its descriptor and has the safe state it declares.

These are models of behaviour for the software and the tests, not physics: they say what the tool must refuse, what it returns and
where it ends up after an abort. The numbers are provisional until measured (cards meas-tools, rev-tools and test-tools).
"""
import itertools
import math

from .base import Tool, ToolFault, load_descriptor


class Injector(Tool):
    """Hamilton syringe driven by a stepper on a lead screw. Volume is quantised to the micro-steps of the plunger."""

    def __init__(self, descriptor, seed=1):
        super().__init__(descriptor, seed)
        L = self.limits
        self.ul_per_step = (L["syringe_ul"] / L["stroke_mm"]) * L["lead_mm"] / (200 * L["microsteps"])
        self.loaded_ul = 0.0
        self.washed = True

    def _steps(self, volume_ul):
        return round(volume_ul / self.ul_per_step)

    def op_prime(self, volume_ul):
        if volume_ul <= 0 or self.loaded_ul + volume_ul > self.limits["syringe_ul"] + 1e-9:
            raise ToolFault("limit", f"cannot load {volume_ul} uL into a {self.limits['syringe_ul']} uL syringe holding {self.loaded_ul}")
        self.loaded_ul += self._steps(volume_ul) * self.ul_per_step
        self.washed = False
        return {"loaded_ul": self.loaded_ul}

    def op_inject(self, volume_ul, rate_ul_s):
        self._limit("max_dose_ul", volume_ul, "dose", minimum=self.ul_per_step)
        self._limit("max_rate_ul_s", rate_ul_s, "rate", minimum=1e-6)
        steps = self._steps(volume_ul)
        delivered = steps * self.ul_per_step
        if delivered > self.loaded_ul + 1e-9:
            raise ToolFault("empty", f"{delivered:.3f} uL asked, {self.loaded_ul:.3f} uL loaded")
        done = 0
        for i in range(1, self.STEPS + 1):
            self._step(i / self.STEPS)
            done = steps * i // self.STEPS
        self.loaded_ul -= done * self.ul_per_step
        return {"delivered_ul": done * self.ul_per_step, "steps": done, "duration_s": volume_ul / rate_ul_s}

    def op_wash(self, cycles=3):
        if cycles < 1:
            raise ToolFault("limit", "at least one cycle")
        self.loaded_ul = 0.0
        self.washed = True
        return {"cycles": cycles}

    def _safe(self):
        self.events.append("plunger_stopped")


class Probe(Tool):
    """Spring stylus with a trigger. It finds a surface by moving down slowly until the trigger closes."""

    STIFFNESS_N_PER_MM = 0.2
    LATENCY_S = 0.005

    def op_find_surface(self, surface_z, start_z, approach_mm_s=None):
        speed = approach_mm_s or self.limits["approach_mm_s"]
        self._limit("approach_mm_s", speed, "approach speed", minimum=1e-3)
        travel = start_z - surface_z
        if travel < 0:
            raise ToolFault("limit", "the surface is above the start point")
        if travel > self.limits["max_travel_mm"]:
            raise ToolFault("no_contact", f"no contact in {self.limits['max_travel_mm']} mm")
        sigma = self.limits["trigger_repeatability_um"] / 1000.0
        reading = surface_z + self.rng.gauss(0.0, sigma)
        overshoot = speed * self.LATENCY_S  # distance the stylus keeps moving after the trigger
        force = self.STIFFNESS_N_PER_MM * overshoot
        if force > self.limits["force_stop_n"]:
            raise ToolFault("force", f"{force:.3f} N above the {self.limits['force_stop_n']} N stop")
        for i in range(1, self.STEPS + 1):
            self._step(i / self.STEPS)
        return {"z": reading, "force_n": force}

    def op_touch(self, surface_z, start_z):
        return self.op_find_surface(surface_z, start_z)

    def op_find_landmark(self, surface_z_at, start_z, point_xy):
        """The height of the sample surface at a landmark; `surface_z_at(x, y)` is the simulated surface."""
        found = self.op_find_surface(surface_z_at(*point_xy), start_z)
        return {"xy": tuple(point_xy), "z": found["z"], "force_n": found["force_n"]}


class Scalpel(Tool):
    """Blade holder with a depth stop and a guard that a spring closes. The blade cuts only with the guard open and above the stop."""

    def __init__(self, descriptor, seed=1):
        super().__init__(descriptor, seed)
        self.depth_stop_mm = None
        self.guard_closed = True
        self.blade = False
        self.blade_cuts = 0

    def op_set_depth_stop(self, depth_mm):
        self._limit("max_depth_mm", depth_mm, "depth stop", minimum=0.05)
        self.depth_stop_mm = depth_mm
        return {"depth_stop_mm": depth_mm}

    def op_change_blade(self):
        if not self.guard_closed:
            raise ToolFault("guard_open", "close the guard before changing the blade")
        self.blade = True
        self.blade_cuts = 0
        self.depth_stop_mm = None  # a new blade needs a new depth stop: it is another length
        return {"blade": "new"}

    def _check_cut(self, depth_mm, feed_mm_s, length_mm):
        if not self.blade:
            raise ToolFault("no_blade", "fit a blade first")
        if self.depth_stop_mm is None:
            raise ToolFault("no_depth_stop", "set the depth stop first")
        if depth_mm <= 0 or depth_mm > self.depth_stop_mm + 1e-9:
            raise ToolFault("depth", f"{depth_mm} mm is deeper than the {self.depth_stop_mm} mm stop")
        self._limit("max_feed_mm_s", feed_mm_s, "feed", minimum=1e-3)
        self._limit("max_cut_length_mm", length_mm, "cut length", minimum=1e-3)

    def op_incise(self, length_mm, depth_mm, feed_mm_s):
        return self.op_cut_line([(0.0, 0.0), (length_mm, 0.0)], depth_mm, feed_mm_s)

    def op_cut_line(self, points, depth_mm, feed_mm_s):
        length = sum(math.dist(a, b) for a, b in itertools.pairwise(points))
        self._check_cut(depth_mm, feed_mm_s, length)
        self.guard_closed = False
        try:
            for i in range(1, self.STEPS + 1):
                self._step(i / self.STEPS)
        finally:
            self.guard_closed = True
        self.blade_cuts += 1
        return {"length_mm": length, "depth_mm": depth_mm, "duration_s": length / feed_mm_s}

    def _safe(self):
        self.guard_closed = True


class Drill(Tool):
    """Micro-drill with a depth stop. The power goes through the hardware cut-off and is cut as the abort starts."""

    def __init__(self, descriptor, seed=1):
        super().__init__(descriptor, seed)
        self.depth_stop_mm = None
        self.rpm = 0

    def op_set_depth_stop(self, depth_mm):
        self._limit("max_depth_mm", depth_mm, "depth stop", minimum=0.05)
        self.depth_stop_mm = depth_mm
        return {"depth_stop_mm": depth_mm}

    def op_drill(self, depth_mm, feed_mm_s, rpm):
        if self.depth_stop_mm is None:
            raise ToolFault("no_depth_stop", "set the depth stop first")
        if depth_mm <= 0 or depth_mm > self.depth_stop_mm + 1e-9:
            raise ToolFault("depth", f"{depth_mm} mm is deeper than the {self.depth_stop_mm} mm stop")
        self._limit("max_feed_mm_s", feed_mm_s, "feed", minimum=1e-3)
        self._limit("max_rpm", rpm, "speed", minimum=1000)
        if depth_mm / feed_mm_s > self.limits["max_run_s"]:
            raise ToolFault("run_time", f"longer than {self.limits['max_run_s']} s")
        self.rpm = rpm
        try:
            for i in range(1, self.STEPS + 1):
                self._step(i / self.STEPS)
                if not self.powered:
                    raise ToolFault("power_lost", "the power was cut during the cut")
        finally:
            self.rpm = 0
        return {"depth_mm": depth_mm, "duration_s": depth_mm / feed_mm_s}

    def _safe(self):
        self.rpm = 0


class Fluid(Tool):
    """Suction, irrigation and adhesive through a nozzle, with the pumps off the head. The model keeps the volumes of the reservoirs."""

    PRESSURE_KPA_PER_UL_S = 1.8
    SUPPLY_UL = 2000.0
    WASTE_UL = 2000.0

    def __init__(self, descriptor, seed=1):
        super().__init__(descriptor, seed)
        self.supply_ul = self.SUPPLY_UL
        self.waste_ul = 0.0
        self.adhesive_ul = 100.0
        self.valve_closed = True

    def _flow(self, volume_ul, rate_ul_s, limit):
        self._limit(limit, volume_ul, "volume", minimum=1e-3)
        self._limit("max_rate_ul_s", rate_ul_s, "rate", minimum=1e-3)
        pressure = rate_ul_s * self.PRESSURE_KPA_PER_UL_S
        if pressure > self.limits["max_pressure_kpa"]:
            raise ToolFault("pressure", f"{pressure:.1f} kPa above {self.limits['max_pressure_kpa']}")
        self.valve_closed = False
        moved = 0.0
        try:
            for i in range(1, self.STEPS + 1):
                self._step(i / self.STEPS)
                moved = volume_ul * i / self.STEPS
        finally:
            self.valve_closed = True
        return moved

    def op_aspirate(self, volume_ul, rate_ul_s):
        if self.waste_ul + volume_ul > self.WASTE_UL:
            raise ToolFault("waste_full", "empty the waste bottle")
        moved = self._flow(volume_ul, rate_ul_s, "max_volume_ul")
        self.waste_ul += moved
        return {"aspirated_ul": moved}

    def op_irrigate(self, volume_ul, rate_ul_s):
        if volume_ul > self.supply_ul:
            raise ToolFault("supply_empty", "refill the irrigation bottle")
        moved = self._flow(volume_ul, rate_ul_s, "max_volume_ul")
        self.supply_ul -= moved
        return {"irrigated_ul": moved}

    def op_dispense_adhesive(self, volume_ul, rate_ul_s):
        if volume_ul > self.adhesive_ul:
            raise ToolFault("supply_empty", "refill the adhesive")
        moved = self._flow(volume_ul, rate_ul_s, "max_adhesive_ul")
        self.adhesive_ul -= moved
        return {"dispensed_ul": moved}

    def op_purge(self, volume_ul=50.0):
        return self.op_irrigate(volume_ul, self.limits["max_rate_ul_s"] / 2)

    def _safe(self):
        self.valve_closed = True


class Gripper(Tool):
    """Jaws closed by a spring: with the power off or after an abort they keep holding. Force and opening are limited."""

    def __init__(self, descriptor, seed=1):
        super().__init__(descriptor, seed)
        self.holding = None
        self.opening_mm = 0.0

    def op_grip(self, item, width_mm, force_n):
        if self.holding is not None:
            raise ToolFault("busy", f"already holding {self.holding}")
        self._limit("max_open_mm", width_mm, "item width", minimum=self.limits["min_close_mm"])
        self._limit("max_force_n", force_n, "force", minimum=1e-3)
        self.holding = item
        self.opening_mm = width_mm
        for i in range(1, self.STEPS + 1):
            self._step(i / self.STEPS)
        return {"holding": item, "width_mm": width_mm, "force_n": force_n}

    def op_release(self):
        if self.holding is None:
            raise ToolFault("empty", "nothing to release")
        item, self.holding = self.holding, None
        self.opening_mm = self.limits["max_open_mm"]
        return {"released": item}

    def op_place_implant(self, target_xyz):
        if self.holding is None:
            raise ToolFault("empty", "there is nothing to place")
        for i in range(1, self.STEPS + 1):
            self._step(i / self.STEPS)
        item = self.holding
        self.holding = None
        return {"placed": item, "at": tuple(target_xyz)}


class Cautery(Tool):
    """Pulses with a power, a duration, an energy per pulse, a gap between pulses and a total per minute. The power is on only in a pulse."""

    def __init__(self, descriptor, seed=1):
        super().__init__(descriptor, seed)
        self.now_ms = 0.0
        self.last_end_ms = None
        self.history = []  # (end_ms, energy_mj)
        self.output_on = False

    def advance(self, ms):
        self.now_ms += ms

    def op_coagulate(self, power_w, pulse_ms):
        L = self.limits
        self._limit("max_power_w", power_w, "power", minimum=1e-3)
        self._limit("max_pulse_ms", pulse_ms, "pulse", minimum=1)
        energy = power_w * pulse_ms  # mJ
        if energy > L["max_energy_mj"]:
            raise ToolFault("energy", f"{energy:.0f} mJ above {L['max_energy_mj']} mJ per pulse")
        if self.last_end_ms is not None and self.now_ms - self.last_end_ms < L["min_gap_ms"]:
            raise ToolFault("gap", f"wait {L['min_gap_ms']} ms between pulses")
        recent = sum(e for t, e in self.history if self.now_ms - t < 60000.0)
        if recent + energy > L["max_energy_per_min_mj"]:
            raise ToolFault("budget", f"{recent + energy:.0f} mJ in the last minute, above {L['max_energy_per_min_mj']}")
        self.output_on = True
        delivered = 0.0
        try:
            for i in range(1, self.STEPS + 1):
                self._step(i / self.STEPS)
                if not self.powered:
                    raise ToolFault("power_lost", "the power was cut during the pulse")
                delivered = energy * i / self.STEPS
        finally:
            self.output_on = False
            self.now_ms += pulse_ms * (delivered / energy if energy else 1.0)
            self.last_end_ms = self.now_ms
            self.history.append((self.now_ms, delivered))
        return {"energy_mj": delivered}

    def _safe(self):
        self.output_on = False


class Sensor(Tool):
    """Optical sensor for fluorescence and photometry. A reading needs a dark reference, and a saturated reading is refused."""

    def __init__(self, descriptor, seed=1):
        super().__init__(descriptor, seed)
        self.dark = None
        self.light_on = False

    def _raw(self, integration_ms, rate_counts_s):
        self._limit("max_integration_ms", integration_ms, "integration time", minimum=1)
        counts = self.limits["dark_counts"] + rate_counts_s * integration_ms / 1000.0
        counts += self.rng.gauss(0.0, self.limits["noise_counts"])
        if counts >= self.limits["saturation_counts"]:
            raise ToolFault("saturated", "shorten the integration time or reduce the light")
        return counts

    def op_dark_reference(self, integration_ms=100, repeats=8):
        values = [self._raw(integration_ms, 0.0) for _ in range(repeats)]
        self.dark = sum(values) / len(values)
        return {"dark_counts": self.dark}

    def _reading(self, integration_ms, rate_counts_s):
        if self.dark is None:
            raise ToolFault("no_dark", "take a dark reference first")
        self.light_on = True
        try:
            for i in range(1, self.STEPS + 1):
                self._step(i / self.STEPS)
            return {"counts": self._raw(integration_ms, rate_counts_s) - self.dark}
        finally:
            self.light_on = False

    def op_read_fluorescence(self, integration_ms, rate_counts_s):
        return self._reading(integration_ms, rate_counts_s)

    def op_read_photometry(self, integration_ms, rate_counts_s):
        return self._reading(integration_ms, rate_counts_s)

    def _safe(self):
        self.light_on = False


MODELS = {
    "injector": Injector,
    "probe": Probe,
    "scalpel": Scalpel,
    "drill": Drill,
    "fluid": Fluid,
    "gripper": Gripper,
    "cautery": Cautery,
    "sensor": Sensor,
}


def build(name, seed=1):
    return MODELS[name](load_descriptor(name), seed)
