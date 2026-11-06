// Host tests of the tool interface of the controller core: identification, switched power, safe state and tool changes.
//   g++ -std=c++17 -Wall -Wextra -Werror -O2 -Ifirmware/core firmware/core/controller.cpp firmware/tests/test_tools.cpp -o test_tools
//   ./test_tools
#include <cmath>
#include <cstdio>
#include <functional>
#include <string>

#include "controller.h"
#include "tool_table.h"

using namespace fw;

namespace {

int g_checks = 0;
int g_failures = 0;

#define CHECK(condition)                                                \
  do {                                                                  \
    ++g_checks;                                                         \
    if (!(condition)) {                                                 \
      ++g_failures;                                                     \
      std::printf("  FAIL line %d: %s\n", __LINE__, #condition);        \
    }                                                                   \
  } while (0)

// Three tools with different safety behaviour, independent of the real table.
const ToolInfo kTestTools[] = {
    {11, "inj", ToolClass::Injector, {0, 0, -30}, 12.0, 1 << 5, 1.0, false, false},
    {12, "drl", ToolClass::Drill, {0, 0, -25}, 8.0, 0, 2.0, true, true},
    {13, "grp", ToolClass::Gripper, {0, 0, -40}, 15.0, 0, 0.5, false, false},
};

bool contains(const std::string& text, const char* part) { return text.find(part) != std::string::npos; }

struct Rig {
  Config cfg;
  Controller ctl;
  std::array<double, kAxes> phys{17.3, -40.0, 30.0, 10.0, -5.0, 30.0};
  bool power = true;
  bool tool_present = false;
  uint16_t tool_id = 0;
  uint32_t ms = 0;
  Outputs last;

  static Config make_config() {
    Config c = default_config();
    c.require_tool = true;
    c.tools = kTestTools;
    c.tool_count = 3;
    c.watchdog_ms = 3600000;
    return c;
  }
  Rig() : cfg(make_config()), ctl(cfg) {}

  Inputs inputs() const {
    Inputs in;
    for (int i = 0; i < kAxes; ++i) {
      in.limit_min[i] = phys[i] <= cfg.axis[i].min_pos - 2.0;
      in.limit_max[i] = phys[i] >= cfg.axis[i].max_pos + 2.0;
    }
    in.motor_power_ok = power;
    in.tool_present = tool_present;
    in.tool_id = tool_id;
    return in;
  }
  Outputs tick() {
    last = ctl.tick(ms, inputs());
    for (int i = 0; i < kAxes; ++i) phys[i] += last.step_delta[i] / cfg.axis[i].steps_per_unit;
    ++ms;
    return last;
  }
  void run(int ticks) {
    for (int i = 0; i < ticks; ++i) tick();
  }
  std::string send(const std::string& line) { return ctl.handle_line(line, ms); }
  void mount(uint16_t id) {
    tool_present = true;
    tool_id = id;
  }
  void unmount() {
    tool_present = false;
    tool_id = 0;
  }
  void settle(int max_ticks = 500000) {
    for (int i = 0; i < max_ticks; ++i) {
      tick();
      const State s = ctl.state();
      if (s == State::Idle || s == State::Aborted || s == State::Fault || s == State::Hold) return;
    }
  }
  // mount, power the tool, home, and leave the machine idle
  void ready(uint16_t id) {
    mount(id);
    run(3);
    send("TOOL ON");
    run(3);
    send("HOME");
    settle();
  }
};

void test_table() {
  std::printf("the generated table holds the injector\n");
  CHECK(kToolTableSize >= 1);
  bool found = false;
  for (unsigned i = 0; i < kToolTableSize; ++i) {
    if (kToolTable[i].id == 1 && std::string(kToolTable[i].name) == "injector") found = true;
    CHECK(kToolTable[i].id != 0);
    CHECK(kToolTable[i].retract_mm > 0.0);
  }
  CHECK(found);
  CHECK(default_config().tool_count == kToolTableSize);
  CHECK(!default_config().require_tool);
}

void test_no_tool() {
  std::printf("without a tool nothing moves\n");
  Rig r;
  r.run(5);
  CHECK(r.send("HOME") == "error:tool");
  CHECK(r.send("MOVE X1") == "error:tool");
  CHECK(r.send("PARK") == "error:tool");
  CHECK(r.send("PING") == "ok pong");
  CHECK(contains(r.send("STATUS"), "tool=none"));
  CHECK(contains(r.send("TOOL"), "tool=none id=0 ready=0 power=0"));
  CHECK(r.send("TOOL ON") == "error:tool");
  CHECK(!r.last.tool_power_enable);
}

void test_unknown_tool() {
  std::printf("an unknown tool is refused and never powered\n");
  Rig r;
  r.mount(99);
  r.run(5);
  CHECK(contains(r.send("TOOL"), "tool=unknown id=99 ready=0 power=0"));
  CHECK(contains(r.send("STATUS"), "tool=unknown"));
  CHECK(r.send("HOME") == "error:tool");
  CHECK(r.send("TOOL ON") == "error:tool");
  r.run(50);
  CHECK(!r.last.tool_power_enable);
  r.mount(0);  // id 0 is never valid
  r.run(3);
  CHECK(contains(r.send("TOOL"), "tool=unknown"));
}

void test_known_tool_and_power() {
  std::printf("a known tool is powered only after TOOL ON\n");
  Rig r;
  r.mount(11);
  r.run(5);
  CHECK(contains(r.send("TOOL"), "tool=inj id=11 ready=1 power=0"));
  CHECK(!r.last.tool_power_enable);
  CHECK(r.send("TOOL ON").rfind("ok", 0) == 0);
  r.run(3);
  CHECK(r.last.tool_power_enable);
  CHECK(r.send("TOOL BANANA") == "error:syntax");
  CHECK(contains(r.send("TOOL OFF"), "tool=inj"));
  r.run(3);
  CHECK(!r.last.tool_power_enable);
  r.send("TOOL ON");
  r.run(3);
  CHECK(r.send("HOME") == "ok homing");
  CHECK(r.send("TOOL ON") == "error:state");
  r.settle();
  CHECK(r.ctl.state() == State::Idle);
  CHECK(r.last.tool_power_enable);
  CHECK(r.send("MOVE X5 F20") == "ok");
}

void test_motor_power_loss_cuts_tool_power() {
  std::printf("losing the motor supply cuts the tool power and it needs a new TOOL ON\n");
  Rig r;
  r.ready(11);
  CHECK(r.last.tool_power_enable);
  r.power = false;
  r.run(3);
  CHECK(r.ctl.state() == State::PowerLoss);
  CHECK(!r.last.tool_power_enable);
  r.power = true;
  r.run(3);
  CHECK(r.send("CLEAR") == "ok");
  r.run(3);
  CHECK(!r.last.tool_power_enable);
  CHECK(r.send("TOOL ON") == "ok tool=inj id=11 ready=1 power=0");
  r.run(3);
  CHECK(r.last.tool_power_enable);
}

void test_abort_safe_state() {
  std::printf("abort: a drill loses its power at once, an injector and a gripper keep it\n");
  {
    Rig r;
    r.ready(12);
    CHECK(r.last.tool_power_enable);
    r.send("MOVE X10 Y5 Z0 F20");
    r.run(2000);
    r.send("ABORT");
    r.tick();
    CHECK(r.ctl.state() == State::Aborting);
    CHECK(!r.last.tool_power_enable);  // cut in the very tick the abort starts
    r.settle();
    CHECK(r.ctl.state() == State::Aborted);
    CHECK(!r.last.tool_power_enable);
    r.send("CLEAR");
    r.run(5);
    CHECK(!r.last.tool_power_enable);  // not back by itself
    r.send("TOOL ON");
    r.run(3);
    CHECK(r.last.tool_power_enable);
  }
  for (uint16_t id : {11, 13}) {
    Rig r;
    r.ready(id);
    r.send("MOVE X10 Y5 Z0 F20");
    r.run(2000);
    r.send("ABORT");
    r.tick();
    CHECK(r.last.tool_power_enable);
    r.settle();
    CHECK(r.ctl.state() == State::Aborted);
    CHECK(r.last.tool_power_enable);  // holds what it holds
  }
}

double first_stop_height(uint16_t id, double start_z) {
  Rig r;
  r.ready(id);
  r.send("MOVE A0 B0 Z" + std::to_string(start_z) + " F40");
  r.settle();
  const double z0 = r.phys[Z];
  r.send("ABORT");
  bool moved = false;
  double previous = z0;
  for (int i = 0; i < 200000; ++i) {
    r.tick();
    const double z = r.phys[Z];
    if (std::fabs(z - previous) > 1e-9) moved = true;
    if (moved && std::fabs(z - previous) < 1e-12) return z - z0;  // the first stop: the end of the withdrawal
    previous = z;
  }
  return -1.0;
}

void test_retract_length() {
  std::printf("the withdrawal length is the tool's\n");
  CHECK(std::fabs(first_stop_height(11, 0.0) - 12.0) < 0.05);
  CHECK(std::fabs(first_stop_height(13, 0.0) - 15.0) < 0.05);
  CHECK(std::fabs(first_stop_height(12, 0.0) - 8.0) < 0.05);
}

void test_tool_change() {
  std::printf("a tool change is a fault unless it is done at rest with the power off\n");
  {
    Rig r;
    r.ready(11);
    r.unmount();  // removed while powered
    r.run(2);
    CHECK(r.ctl.state() == State::Fault && r.ctl.cause() == Cause::Tool);
    CHECK(!r.last.tool_power_enable && !r.last.drivers_enabled);
    CHECK(r.send("CLEAR") == "ok");
    CHECK(r.ctl.state() == State::NotHomed);
  }
  {
    Rig r;
    r.ready(11);
    r.mount(13);  // swapped while powered
    r.run(2);
    CHECK(r.ctl.state() == State::Fault && r.ctl.cause() == Cause::Tool);
  }
  {
    Rig r;
    r.ready(11);
    r.send("MOVE X30 F5");
    r.run(100);
    r.send("TOOL OFF");
    r.run(2);
    r.unmount();  // removed while moving, even without power
    r.run(2);
    CHECK(r.ctl.state() == State::Fault && r.ctl.cause() == Cause::Tool);
  }
  {
    Rig r;
    r.ready(11);
    CHECK(r.send("TOOL OFF").rfind("ok", 0) == 0);
    r.run(3);
    CHECK(!r.last.tool_power_enable);
    r.unmount();  // at rest, power off: allowed
    r.run(3);
    CHECK(r.ctl.state() == State::Idle);
    CHECK(r.send("MOVE X1") == "error:tool");
    r.mount(12);
    r.run(3);
    CHECK(r.ctl.state() == State::Idle && contains(r.send("TOOL"), "tool=drl"));
    CHECK(!r.last.tool_power_enable);  // the new tool is not powered until TOOL ON
    CHECK(r.send("TOOL ON").rfind("ok", 0) == 0);
    r.run(3);
    CHECK(r.last.tool_power_enable);
    CHECK(r.send("MOVE X1 F10") == "ok");
  }
}

}  // namespace

int main() {
  test_table();
  test_no_tool();
  test_unknown_tool();
  test_known_tool_and_power();
  test_motor_power_loss_cuts_tool_power();
  test_abort_safe_state();
  test_retract_length();
  test_tool_change();
  std::printf("\n%d checks, %d failures\n%s\n", g_checks, g_failures, g_failures == 0 ? "ALL TESTS PASSED" : "TESTS FAILED");
  return g_failures == 0 ? 0 : 1;
}
