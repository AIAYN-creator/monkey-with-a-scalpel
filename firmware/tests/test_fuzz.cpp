// Randomised tests of the controller core: random command sequences, garbage lines, switch and power events, checked against
// invariants that must hold whatever the host sends. Deterministic (fixed seeds), so a failure is reproducible.
//   g++ -std=c++17 -Wall -Wextra -Werror -O2 -Ifirmware/core firmware/core/controller.cpp firmware/tests/test_fuzz.cpp -o test_fuzz
//   ./test_fuzz
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#include "controller.h"

using namespace fw;

namespace {

int g_checks = 0;
int g_failures = 0;
int g_reported = 0;
int g_visits[9] = {0};  // ticks spent in each State, to show the sequences really reach every state
int g_ok_replies = 0;
int g_error_replies = 0;

#define CHECK(condition, seed, what)                                                            \
  do {                                                                                          \
    ++g_checks;                                                                                 \
    if (!(condition)) {                                                                         \
      ++g_failures;                                                                             \
      if (g_reported++ < 20) std::printf("  FAIL seed %d: %s (%s)\n", static_cast<int>(seed), what, #condition); \
    }                                                                                           \
  } while (0)

// Tools of the randomised tests: a powered tool that is cut on abort (a drill) and two that keep their power.
const ToolInfo kFuzzTools[] = {
    {11, "inj", ToolClass::Injector, {0, 0, -30}, 12.0, 1 << 5, 1.0, false, false},
    {12, "drl", ToolClass::Drill, {0, 0, -25}, 8.0, 0, 2.0, true, true},
    {13, "grp", ToolClass::Gripper, {0, 0, -40}, 15.0, 0, 0.5, false, false},
};
const uint16_t kToolIds[] = {0, 11, 12, 13, 99};

struct Rng {
  uint64_t s;
  explicit Rng(uint64_t seed) : s(seed * 0x9E3779B97F4A7C15ull + 1) {}
  uint64_t next() {
    s ^= s << 13;
    s ^= s >> 7;
    s ^= s << 17;
    return s;
  }
  int below(int n) { return static_cast<int>(next() % static_cast<uint64_t>(n)); }
  double uniform(double lo, double hi) { return lo + (hi - lo) * static_cast<double>(next() % 1000001) / 1000000.0; }
  bool chance(int percent) { return below(100) < percent; }
};

// Simulated machine: the physical position of each axis, with the limit switches 2 units beyond the soft limits.
struct Plant {
  Config cfg;
  Controller ctl;
  std::array<double, kAxes> phys{};
  bool power = true;
  bool button = false;
  uint32_t ms = 0;
  Outputs last;
  bool crashed = false;  // the controller drove an axis into its mechanical hard stop
  bool tool_present = false;
  uint16_t tool_id = 0;

  explicit Plant(const Config& c, Rng& rng) : cfg(c), ctl(c) {
    for (int i = 0; i < kAxes; ++i) phys[i] = rng.uniform(c.axis[i].min_pos, c.axis[i].max_pos);
  }
  // mechanical hard stops 6 units beyond the soft limits (the limit switches sit 2 units beyond)
  double stop_min(int i) const { return cfg.axis[i].min_pos - 6.0; }
  double stop_max(int i) const { return cfg.axis[i].max_pos + 6.0; }
  double clamp(int i, double x) const { return x < stop_min(i) ? stop_min(i) : (x > stop_max(i) ? stop_max(i) : x); }
  void slip(int i, double amount) { phys[i] = clamp(i, phys[i] + amount); }
  Inputs inputs() const {
    Inputs in;
    for (int i = 0; i < kAxes; ++i) {
      in.limit_min[i] = phys[i] <= cfg.axis[i].min_pos - 2.0;
      in.limit_max[i] = phys[i] >= cfg.axis[i].max_pos + 2.0;
    }
    in.abort_button = button;
    in.motor_power_ok = power;
    in.tool_present = tool_present;
    in.tool_id = tool_id;
    return in;
  }
  Outputs tick() {
    last = ctl.tick(ms, inputs());
    for (int i = 0; i < kAxes; ++i) {
      phys[i] += last.step_delta[i] / cfg.axis[i].steps_per_unit;
      if (last.step_delta[i] != 0 && (phys[i] < stop_min(i) || phys[i] > stop_max(i))) crashed = true;
      phys[i] = clamp(i, phys[i]);
    }
    ++ms;
    return last;
  }
};

std::string random_command(Rng& rng, const Config& cfg) {
  static const char* const fixed[] = {"PING", "STATUS", "HOME", "PARK", "STOP", "ABORT", "CLEAR", "ping", "Status"};
  static const char* const tool_commands[] = {"TOOL", "TOOL ON", "TOOL OFF", "TOOL ON", "tool on", "TOOL X"};
  static const char* const garbage[] = {"", " ", "MOVE", "MOVE X", "MOVE Xabc", "MOVE X1e999", "MOVE X-nan", "MOVE F0 X1", "MOVE F-5 X1",
                                        "HOME HOME", "FOO", "\t\t", "MOVE X1 X2 X3 Y4", "MOVE Q5", "STATUS STATUS", "ABORT now",
                                        "MOVE X1 F", "move y2 z3 f10", "\xff\xfe", "MOVE X--1"};
  const int kind = rng.below(10);
  if (rng.chance(5)) return tool_commands[rng.below(6)];
  if (kind < 3) return fixed[rng.below(9)];
  if (kind < 4) return garbage[rng.below(20)];
  std::string line = "MOVE";
  const char letters[] = {'X', 'Y', 'Z', 'A', 'B', 'P'};
  const int n = 1 + rng.below(4);
  for (int k = 0; k < n; ++k) {
    const int axis = rng.below(6);
    const bool outside = rng.chance(8);
    const double span = cfg.axis[axis].max_pos - cfg.axis[axis].min_pos;
    const double beyond = rng.uniform(1, 30);
    const double value = outside ? (rng.chance(50) ? cfg.axis[axis].max_pos + beyond : cfg.axis[axis].min_pos - beyond)
                                : cfg.axis[axis].min_pos + rng.uniform(0, span);
    char buffer[40];
    std::snprintf(buffer, sizeof buffer, " %c%.3f", letters[axis], value);
    line += buffer;
  }
  if (rng.chance(60)) {
    char buffer[24];
    std::snprintf(buffer, sizeof buffer, " F%.1f", rng.uniform(1, 40));
    line += buffer;
  }
  return line;
}

bool well_formed(const std::string& reply) { return reply.rfind("ok", 0) == 0 || reply.rfind("error:", 0) == 0; }

bool in_range(const Plant& p, int axis, double eps) {
  const double x = p.ctl.position(static_cast<Axis>(axis));
  return std::isfinite(x) && x >= p.cfg.axis[axis].min_pos - eps && x <= p.cfg.axis[axis].max_pos + eps;
}

void run_sequence(int seed) {
  Rng rng(static_cast<uint64_t>(seed));
  Config cfg = default_config();
  cfg.watchdog_ms = rng.chance(30) ? 300 + rng.below(3000) : 3600000;
  cfg.tools = kFuzzTools;
  cfg.tool_count = 3;
  cfg.require_tool = rng.chance(50);
  Plant p(cfg, rng);
  if (rng.chance(70)) {
    p.tool_present = true;
    p.tool_id = kToolIds[1 + rng.below(4)];
  }
  const bool ping = rng.chance(50);
  uint32_t last_line_ms = 0;

  for (int i = 0; i < 3; ++i) p.tick();  // the controller reads the tool interface at boot, before any command

  // always start by homing, so that most sequences actually move
  const int commands = 8 + rng.below(30);
  for (int c = 0; c < commands; ++c) {
    const std::string line = c == 0 ? "HOME" : random_command(rng, cfg);
    const std::string reply = p.ctl.handle_line(line, p.ms);
    last_line_ms = p.ms;
    CHECK(well_formed(reply), seed, "every reply starts with ok or error:");
    (reply.rfind("ok", 0) == 0 ? g_ok_replies : g_error_replies)++;
    const int ticks = rng.below(c == 0 ? 60000 : 4000);
    for (int t = 0; t < ticks; ++t) {
      if (rng.chance(1) && t % 997 == 0) p.button = !p.button;  // rare ABORT button events
      if (rng.below(200000) == 0) p.power = !p.power;           // very rare motor power events
      if (rng.below(300000) == 0) {                              // the tool is removed, swapped or replaced by an unknown one
        p.tool_id = kToolIds[rng.below(5)];
        p.tool_present = p.tool_id != 0 || rng.chance(30);
      }
      if (rng.below(2500) == 0) p.slip(rng.below(kAxes), rng.uniform(-5.0, 5.0));  // lost steps: the axis slips under the controller
      if (ping && p.ms % 200 == 0) {
        p.ctl.handle_line("PING", p.ms);
        last_line_ms = p.ms;
      }
      const bool power_before = p.power;
      const bool homed_before = p.ctl.homed();
      const bool button_before = p.button;
      const Outputs out = p.tick();
      const State state = p.ctl.state();
      const bool stopped_for_safety = state == State::Aborting || state == State::Aborted || state == State::Fault ||
                                      state == State::PowerLoss || state == State::NotHomed;
      if (power_before && homed_before && button_before) CHECK(stopped_for_safety, seed, "the ABORT button aborts within one tick");
      if (power_before && homed_before && cfg.watchdog_ms < 100000 && p.ms - last_line_ms > cfg.watchdog_ms + 50) {
        CHECK(stopped_for_safety, seed, "silence from the host beyond the watchdog aborts");
      }
      ++g_visits[static_cast<int>(state)];
      for (int i = 0; i < kAxes; ++i) {
        const double per_tick = std::fabs(out.step_delta[i]) / p.cfg.axis[i].steps_per_unit;
        const double bound = 3.0 * std::max(p.cfg.axis[i].max_speed, p.cfg.abort_speed_mm_s) * p.cfg.tick_us * 1e-6 + 2.0 / p.cfg.axis[i].steps_per_unit;
        CHECK(per_tick <= bound, seed, "no axis moves faster than its limit in one tick");
      }
      if (state == State::Fault || state == State::PowerLoss) {
        bool still = true;
        for (int32_t d : out.step_delta) still = still && d == 0;
        CHECK(still, seed, "no steps while faulted or without power");
      }
      if (!power_before) CHECK(state == State::PowerLoss, seed, "a power loss is always noticed");
      if (p.ctl.homed() && state != State::Homing && state != State::NotHomed) {
        for (int i = 0; i < kAxes; ++i) CHECK(in_range(p, i, 0.01), seed, "the position stays inside the soft limits");
      }
      CHECK(!p.crashed, seed, "the controller never drives an axis into its hard stop");
      if (out.tool_power_enable) {
        CHECK(p.ctl.tool() != nullptr, seed, "the tool power is never on without a known tool");
        CHECK(p.power && state != State::Fault && state != State::PowerLoss, seed, "the tool power is off while faulted or without motor power");
        if (p.ctl.tool() != nullptr && p.ctl.tool()->cut_on_abort) {
          CHECK(state != State::Aborting && state != State::Aborted, seed, "a drill never has power during an abort");
        }
      }
      if (cfg.require_tool && p.ctl.tool() == nullptr) CHECK(state != State::Moving, seed, "nothing moves without a known tool");
    }
  }

  // an ABORT must always end the motion, wherever the sequence left the machine
  p.button = false;
  if (p.power) {
    p.ctl.handle_line("CLEAR", p.ms);
    p.ctl.handle_line("ABORT", p.ms);
    if (ping) p.ctl.handle_line("PING", p.ms);
    for (int t = 0; t < 300000; ++t) {
      if (ping && p.ms % 200 == 0) p.ctl.handle_line("PING", p.ms);
      p.tick();
      if (p.ctl.state() != State::Aborting && p.ctl.state() != State::Moving && p.ctl.state() != State::Homing) break;
    }
    const State end = p.ctl.state();
    CHECK(end != State::Moving && end != State::Aborting && end != State::Homing, seed, "after ABORT the machine ends up stopped");
  }
}

}  // namespace

int main() {
  const int sequences = 400;
  for (int seed = 1; seed <= sequences; ++seed) run_sequence(seed);
  // the fuzz is only worth something if it reaches the interesting states and produces both kinds of reply
  const char* const names[9] = {"not_homed", "idle", "moving", "homing", "hold", "aborting", "aborted", "fault", "power_loss"};
  for (int s = 0; s < 9; ++s) std::printf("  ticks in %-10s %d\n", names[s], g_visits[s]);
  std::printf("  replies: %d ok, %d error\n", g_ok_replies, g_error_replies);
  for (int s : {1, 2, 3, 5, 6, 7}) CHECK(g_visits[s] > 1000, 0, "the fuzz reaches idle, moving, homing, aborting, aborted and fault");
  CHECK(g_ok_replies > 1000 && g_error_replies > 1000, 0, "the fuzz produces both ok and error replies");
  std::printf("%d sequences, %d checks, %d failures\n%s\n", sequences, g_checks, g_failures,
              g_failures == 0 ? "ALL FUZZ TESTS PASSED" : "FUZZ TESTS FAILED");
  return g_failures == 0 ? 0 : 1;
}
