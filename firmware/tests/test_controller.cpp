// Host tests for the controller core (card p1-06). Build and run from the repository root:
//   g++ -std=c++17 -Wall -Wextra -Werror -O2 -Ifirmware/core firmware/core/controller.cpp
//       firmware/tests/test_controller.cpp -o test_controller   (all on one line)
//   ./test_controller
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <functional>
#include <string>
#include <vector>

#include "controller.h"

using namespace fw;

namespace {

int g_checks = 0;
int g_failures = 0;

#define CHECK(condition)                                                          \
  do {                                                                            \
    ++g_checks;                                                                   \
    if (!(condition)) {                                                           \
      ++g_failures;                                                               \
      std::printf("  FAIL line %d: %s\n", __LINE__, #condition);                  \
    }                                                                             \
  } while (0)

#define CHECK_NEAR(a, b, tol)                                                     \
  do {                                                                            \
    ++g_checks;                                                                   \
    if (!(std::fabs((a) - (b)) <= (tol))) {                                       \
      ++g_failures;                                                               \
      std::printf("  FAIL line %d: %s = %.6f, expected %.6f +- %g\n", __LINE__, #a, \
                  static_cast<double>(a), static_cast<double>(b), static_cast<double>(tol)); \
    }                                                                             \
  } while (0)

bool no_steps(const Outputs& outputs) {
  for (int32_t delta : outputs.step_delta) {
    if (delta != 0) return false;
  }
  return true;
}

// A simulated machine. `phys` is the physical position of each axis in the frame the controller adopts
// after homing. The switches sit 2 units beyond the soft limits.
struct Rig {
  Config cfg;
  Controller ctl;
  std::array<double, kAxes> phys{17.3, -40.0, 50.0, 10.0, -5.0, 30.0};
  std::array<bool, kAxes> switch_works{{true, true, true, true, true, true}};
  uint32_t ms = 0;
  bool button = false;
  bool power = true;
  uint32_t auto_ping_ms = 0;  // when non-zero, the simulated host sends PING this often
  Outputs last;

  static Config make_config(uint32_t watchdog_ms) {
    Config c = default_config();
    c.watchdog_ms = watchdog_ms;
    return c;
  }
  // A long watchdog by default: tests that are not about the watchdog should not be interrupted by it.
  explicit Rig(uint32_t watchdog_ms = 3600000) : cfg(make_config(watchdog_ms)), ctl(cfg) {}

  Inputs inputs() const {
    Inputs in;
    for (int i = 0; i < kAxes; ++i) {
      in.limit_min[i] = switch_works[i] && phys[i] <= cfg.axis[i].min_pos - 2.0;
      in.limit_max[i] = switch_works[i] && phys[i] >= cfg.axis[i].max_pos + 2.0;
    }
    in.abort_button = button;
    in.motor_power_ok = power;
    return in;
  }
  Outputs tick() {
    if (auto_ping_ms != 0 && ms % auto_ping_ms == 0) send("PING");
    last = ctl.tick(ms, inputs());
    for (int i = 0; i < kAxes; ++i) phys[i] += last.step_delta[i] / cfg.axis[i].steps_per_unit;
    ++ms;
    return last;
  }
  std::string send(const std::string& line) { return ctl.handle_line(line, ms); }
  void run(int ticks) {
    for (int i = 0; i < ticks; ++i) tick();
  }
  bool run_until(const std::function<bool()>& done, int max_ticks) {
    for (int i = 0; i < max_ticks; ++i) {
      if (done()) return true;
      tick();
    }
    return done();
  }
  void home() {
    send("HOME");
    run_until([&] { return ctl.state() == State::Idle; }, 400000);
  }
};

// After homing the controller sets the position when it sees the switch, one tick after it closed, so the
// physical axis is up to home_speed * tick beyond what the controller believes. Tolerance used for every
// comparison between the physical axis and a controller target.
double home_tol(const Rig& rig, int axis) {
  return rig.cfg.axis[axis].home_speed * rig.cfg.tick_us * 1e-6 + 1.5 / rig.cfg.axis[axis].steps_per_unit;
}

void test_parser() {
  std::printf("parser and state checks\n");
  Rig r;
  CHECK(r.send("ping") == "ok pong");
  CHECK(r.send("") == "error:syntax");
  CHECK(r.send("FLY") == "error:unknown_command");
  CHECK(r.send("MOVE X10") == "error:not_homed");
  CHECK(r.send("ABORT") == "error:not_homed");
  CHECK(r.send("STATUS").rfind("ok state=not_homed homed=0", 0) == 0);
  CHECK(r.send("HOME") == "ok homing");
  CHECK(r.send("MOVE X10") == "error:not_homed");
}

void test_homing() {
  std::printf("homing\n");
  Rig r;
  r.home();
  CHECK(r.ctl.state() == State::Idle);
  CHECK(r.ctl.homed());
  for (int i = 0; i < kAxes; ++i) CHECK_NEAR(r.ctl.position(static_cast<Axis>(i)), r.phys[i], 0.02);
  CHECK_NEAR(r.ctl.position(X), -48.0, 0.02);
  CHECK_NEAR(r.ctl.position(Z), 48.0, 0.02);
  CHECK_NEAR(r.ctl.position(P), 2.0, 0.02);
  r.run(1000);
  CHECK(no_steps(r.last));
}

void test_homing_failure() {
  std::printf("homing with a dead switch\n");
  Rig r;
  r.switch_works[X] = false;
  r.send("HOME");
  r.run_until([&] { return r.ctl.state() == State::Fault; }, 600000);
  CHECK(r.ctl.state() == State::Fault);
  CHECK(!r.ctl.homed());
}

void test_move_and_soft_limits() {
  std::printf("moves and soft limits\n");
  Rig r;
  r.home();
  CHECK(r.send("MOVE X50.001") == "error:limit");
  CHECK(r.send("MOVE Z-50.001") == "error:limit");
  CHECK(r.send("MOVE P61") == "error:limit");
  CHECK(r.send("MOVE X10 Q5") == "error:syntax");
  CHECK(r.send("MOVE") == "error:syntax");
  CHECK(r.send("MOVE F5") == "error:syntax");
  CHECK(r.send("MOVE X1e400") == "error:syntax");
  CHECK(r.send("MOVE X50 Y-30 Z40 A10 B-5 P20 F15") == "ok");
  CHECK(r.send("MOVE X0") == "error:busy");
  CHECK(r.run_until([&] { return r.ctl.state() == State::Idle; }, 100000));
  const double target[kAxes] = {50, -30, 40, 10, -5, 20};
  for (int i = 0; i < kAxes; ++i) {
    CHECK_NEAR(r.ctl.position(static_cast<Axis>(i)), target[i], 0.001);
    CHECK_NEAR(r.phys[i], target[i], home_tol(r, i));
  }
}

void test_dynamic_limits() {
  std::printf("speed and acceleration limits\n");
  Rig r;
  r.home();
  CHECK(r.send("MOVE X40 Y30 Z-40 A30 B-30 P50") == "ok");
  const int window = 50;  // ms
  std::vector<std::array<double, kAxes>> samples;
  while (r.ctl.state() == State::Moving) {
    r.tick();
    if (r.ms % window == 0) samples.push_back(r.phys);
  }
  double worst_speed_ratio = 0.0;
  double worst_accel_ratio = 0.0;
  for (int i = 0; i < kAxes; ++i) {
    double previous_v = 0.0;
    for (size_t k = 1; k < samples.size(); ++k) {
      const double v = (samples[k][i] - samples[k - 1][i]) / (window / 1000.0);
      worst_speed_ratio = std::max(worst_speed_ratio, std::fabs(v) / r.cfg.axis[i].max_speed);
      if (k > 1) {
        worst_accel_ratio =
            std::max(worst_accel_ratio, std::fabs(v - previous_v) / (window / 1000.0) / r.cfg.axis[i].max_accel);
      }
      previous_v = v;
    }
  }
  std::printf("  worst speed %.1f%% and acceleration %.1f%% of the limits\n", worst_speed_ratio * 100,
              worst_accel_ratio * 100);
  CHECK(worst_speed_ratio <= 1.01);
  CHECK(worst_accel_ratio <= 1.05);
  CHECK(worst_speed_ratio > 0.5);  // the test must actually exercise the limits
}

void test_stop() {
  std::printf("stop\n");
  Rig r;
  r.home();
  r.send("MOVE X40 F20");
  r.run(1500);
  const double at_stop = r.phys[X];
  CHECK(r.send("STOP") == "ok");
  r.run_until([&] { return r.ctl.state() == State::Hold; }, 5000);
  CHECK(r.ctl.state() == State::Hold);
  CHECK(r.phys[X] > at_stop - 1e-9);
  CHECK(r.phys[X] - at_stop < 3.0);  // v^2 / (2 a k) = 400 / 1600 = 0.25 mm, with margin
  CHECK(r.phys[X] < 79.0);
  const double held = r.phys[X];
  r.run(2000);
  CHECK_NEAR(r.phys[X], held, 1e-9);
  CHECK(r.send("MOVE X0") == "ok");
  CHECK(r.run_until([&] { return r.ctl.state() == State::Idle; }, 100000));
  CHECK_NEAR(r.phys[X], 0.0, home_tol(r, X));
}

// Independent derivation of the needle's withdrawal direction: R = Ry(a) * Rx(b) applied to (0, 0, 1).
std::array<double, 3> withdrawal_direction(double a_deg, double b_deg) {
  const double pi = 3.14159265358979323846;
  const double a = a_deg * pi / 180.0, b = b_deg * pi / 180.0;
  const double rx[3][3] = {{1, 0, 0}, {0, std::cos(b), -std::sin(b)}, {0, std::sin(b), std::cos(b)}};
  const double ry[3][3] = {{std::cos(a), 0, std::sin(a)}, {0, 1, 0}, {-std::sin(a), 0, std::cos(a)}};
  double m[3][3] = {};
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j)
      for (int k = 0; k < 3; ++k) m[i][j] += ry[i][k] * rx[k][j];
  return {m[0][2], m[1][2], m[2][2]};
}

void test_abort_withdraws_along_the_axis() {
  std::printf("abort withdraws along the tool axis and parks\n");
  Rig r;
  r.home();
  r.send("MOVE X10 Y5 Z30 A20 B-10 F20");
  r.run_until([&] { return r.ctl.state() == State::Idle; }, 100000);
  const std::array<double, 3> start{r.phys[X], r.phys[Y], r.phys[Z]};
  const std::array<double, 3> u = withdrawal_direction(20.0, -10.0);
  r.button = true;
  double travelled = 0.0;
  std::array<double, 3> displacement{};
  while (travelled < 19.9 && r.ms < 200000) {
    r.tick();
    for (int i = 0; i < 3; ++i) displacement[i] = r.phys[i] - start[i];
    travelled = std::sqrt(displacement[0] * displacement[0] + displacement[1] * displacement[1] +
                          displacement[2] * displacement[2]);
  }
  const double cosine = (displacement[0] * u[0] + displacement[1] * u[1] + displacement[2] * u[2]) / travelled;
  std::printf("  angle between the first 20 mm and the tool axis: %.4f degrees\n",
              std::acos(std::min(1.0, cosine)) * 180.0 / 3.14159265358979323846);
  CHECK(cosine > 0.99999);
  CHECK(r.ctl.cause() == Cause::Button);
  r.button = false;
  CHECK(r.run_until([&] { return r.ctl.state() == State::Aborted; }, 100000));
  CHECK_NEAR(r.phys[X], r.cfg.park[X], home_tol(r, X));
  CHECK_NEAR(r.phys[Y], r.cfg.park[Y], home_tol(r, Y));
  CHECK(r.phys[Z] >= r.cfg.park[Z] - 0.001);
  CHECK_NEAR(r.phys[A], 0.0, 0.01);
  CHECK_NEAR(r.phys[B], 0.0, 0.01);
  CHECK(r.send("MOVE X1") == "error:state");
  CHECK(r.send("CLEAR") == "ok");
  CHECK(r.ctl.state() == State::Idle);
  CHECK(r.ctl.homed());
  CHECK(r.send("MOVE X1") == "ok");
}

void test_abort_mid_move() {
  std::printf("abort in the middle of a move\n");
  Rig r;
  r.home();
  r.send("MOVE X45 Y-45 Z-45 F20");
  r.run(800);
  const double before = r.phys[X];
  CHECK(r.send("ABORT") == "ok");
  r.run(300);  // decelerating
  CHECK(r.phys[X] - before < 3.0);
  CHECK(r.run_until([&] { return r.ctl.state() == State::Aborted; }, 200000));
  CHECK(r.ctl.cause() == Cause::Command);
  CHECK_NEAR(r.phys[X], r.cfg.park[X], home_tol(r, X));
}

void test_retract_is_clamped_by_limits() {
  std::printf("withdrawal never leaves the soft limits\n");
  Rig r;
  r.home();
  r.send("MOVE Z45 F20");
  r.run_until([&] { return r.ctl.state() == State::Idle; }, 100000);
  r.button = true;
  double highest = r.phys[Z];
  for (int i = 0; i < 200000 && r.ctl.state() != State::Aborted; ++i) {
    r.tick();
    highest = std::max(highest, r.phys[Z]);
    for (int a = 0; a < kAxes; ++a) {
      const double tol = home_tol(r, a);
      CHECK(r.phys[a] >= r.cfg.axis[a].min_pos - tol && r.phys[a] <= r.cfg.axis[a].max_pos + tol);
    }
  }
  CHECK(r.ctl.state() == State::Aborted);
  CHECK(highest <= 50.0 + home_tol(r, Z));
  CHECK(r.ctl.state() != State::Fault);
}

void test_watchdog() {
  std::printf("watchdog\n");
  {
    Rig r(1000);
    r.run(5000);  // never armed: a controller nobody has spoken to does not move
    CHECK(r.ctl.state() == State::NotHomed);
  }
  {
    Rig r(1000);
    r.auto_ping_ms = 200;  // the host keeps pinging, even through a long move
    r.home();
    r.send("MOVE X20 Z10 A10 F5");
    CHECK(r.run_until([&] { return r.ctl.state() == State::Idle; }, 100000));
    r.run(20000);  // twenty seconds idle, still pinged
    CHECK(r.ctl.state() == State::Idle);
  }
  {
    Rig r(1000);
    r.auto_ping_ms = 200;
    r.home();
    r.send("MOVE X20 Z10 A10 F20");
    r.run_until([&] { return r.ctl.state() == State::Idle; }, 100000);
    r.auto_ping_ms = 0;  // the host goes silent
    r.run(r.cfg.watchdog_ms - 250);
    CHECK(r.ctl.state() == State::Idle);
    r.run(300);
    CHECK(r.ctl.state() == State::Aborting);
    CHECK(r.ctl.cause() == Cause::Watchdog);
    CHECK(r.run_until([&] { return r.ctl.state() == State::Aborted; }, 100000));
    CHECK_NEAR(r.phys[X], r.cfg.park[X], home_tol(r, X));
  }
}

void test_limit_switch_fault() {
  std::printf("limit switch hit while moving\n");
  Rig r;
  r.home();
  r.phys[X] += 5.0;  // the axis slipped: the controller does not know
  r.send("MOVE X49 F20");  // physically 54: the switch at 52 closes at a controller position of 47
  r.run_until([&] { return r.ctl.state() == State::Fault; }, 100000);
  CHECK(r.ctl.state() == State::Fault);
  CHECK(r.ctl.cause() == Cause::Limit);
  r.run(10);
  CHECK(no_steps(r.last));
  CHECK(!r.last.drivers_enabled);
  CHECK(r.phys[X] <= 52.01);
  CHECK(r.send("MOVE X0") == "error:state");
  CHECK(r.send("ABORT") == "ok");  // the tool can still be withdrawn
  CHECK(r.run_until([&] { return r.ctl.state() == State::Aborted; }, 200000));
  CHECK(r.send("CLEAR") == "ok");
  CHECK(r.ctl.state() == State::NotHomed);  // the position is no longer trusted
  CHECK(!r.ctl.homed());
  CHECK(r.send("MOVE X0") == "error:not_homed");
}

void test_limit_switch_fault_minimum_side() {
  std::printf("limit switch hit on the minimum side\n");
  Rig r;
  r.home();
  r.send("MOVE X0 F20");
  r.run_until([&] { return r.ctl.state() == State::Idle; }, 100000);
  r.phys[X] -= 5.0;  // the axis slipped the other way: physically -54 when the controller reads -49
  r.send("MOVE X-49 F20");
  r.run_until([&] { return r.ctl.state() == State::Fault; }, 100000);
  CHECK(r.ctl.state() == State::Fault);
  CHECK(r.ctl.cause() == Cause::Limit);
  r.run(10);
  CHECK(no_steps(r.last));
  CHECK(!r.last.drivers_enabled);
  CHECK(r.phys[X] >= -52.02);
}

void test_abort_raises_before_moving_sideways() {
  std::printf("abort raises the tool to the park height before moving in X and Y\n");
  Rig r;
  r.home();
  r.send("MOVE X30 Y20 Z-20 F20");
  r.run_until([&] { return r.ctl.state() == State::Idle; }, 100000);
  const double x0 = r.phys[X];
  const double y0 = r.phys[Y];
  r.button = true;
  r.tick();
  r.button = false;
  // The withdrawal itself may move X and Y (the tool is tilted), but never more than retract_mm. When Z first
  // reaches the park height the tool must not have started its sideways trip to the park position yet.
  double sideways_at_park_height = -1.0;
  while (r.ctl.state() == State::Aborting && r.ms < 400000) {
    r.tick();
    if (sideways_at_park_height < 0.0 && r.phys[Z] >= r.cfg.park[Z] - 0.01) {
      sideways_at_park_height = std::hypot(r.phys[X] - x0, r.phys[Y] - y0);
    }
  }
  CHECK(r.ctl.state() == State::Aborted);
  CHECK(sideways_at_park_height >= 0.0);
  CHECK(sideways_at_park_height <= r.cfg.retract_mm + 0.1);
}

void test_power_loss() {
  std::printf("loss of motor power\n");
  Rig r;
  r.home();
  r.send("MOVE X50 F20");
  r.run(500);
  r.power = false;
  r.run(2);
  CHECK(r.ctl.state() == State::PowerLoss);
  r.run(100);
  CHECK(no_steps(r.last));
  CHECK(!r.last.drivers_enabled);
  CHECK(r.send("MOVE X0") == "error:not_homed");
  CHECK(r.send("ABORT") == "error:power");
  CHECK(r.send("CLEAR") == "error:power");
  r.power = true;
  r.run(2);
  CHECK(r.ctl.state() == State::PowerLoss);  // power is back but nothing resumes by itself
  CHECK(r.send("CLEAR") == "ok");
  CHECK(r.ctl.state() == State::NotHomed);
}

void test_abort_during_homing() {
  std::printf("abort while homing\n");
  Rig r;
  r.send("HOME");
  r.run(2000);
  CHECK(r.ctl.state() == State::Homing);
  r.button = true;
  r.run(5);
  r.button = false;
  CHECK(r.ctl.state() == State::NotHomed);
  CHECK(!r.ctl.homed());
}

}  // namespace

int main() {
  test_parser();
  test_homing();
  test_homing_failure();
  test_move_and_soft_limits();
  test_dynamic_limits();
  test_stop();
  test_abort_withdraws_along_the_axis();
  test_abort_mid_move();
  test_retract_is_clamped_by_limits();
  test_watchdog();
  test_limit_switch_fault();
  test_limit_switch_fault_minimum_side();
  test_abort_raises_before_moving_sideways();
  test_power_loss();
  test_abort_during_homing();
  std::printf("\n%d checks, %d failures\n", g_checks, g_failures);
  std::printf(g_failures == 0 ? "ALL TESTS PASSED\n" : "TESTS FAILED\n");
  return g_failures == 0 ? 0 : 1;
}
