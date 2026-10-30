// Motion and safety core of the controller firmware (card p1-06).
//
// Hardware independent on purpose: no Arduino or ESP32 headers. The board code (not written yet)
// feeds it the switch states and the clock, and turns the step counts it returns into pulses.
// That keeps every safety rule testable on a PC.
//
// Safety summary:
//   - ABORT (serial command, button input or watchdog) stops the motion, withdraws the tool along its
//     own axis and parks it. It runs here, so it works with the host computer hung.
//   - The emergency stop that cuts motor power is wired outside this code. If power disappears the
//     core only notices it (motor_power_ok) and refuses to move.
//   - Limit switches are inputs. A switch hit while moving towards it latches a fault.
#pragma once

#include <array>
#include <cstdint>
#include <deque>
#include <string>

namespace fw {

constexpr int kAxes = 6;
enum Axis { X = 0, Y = 1, Z = 2, A = 3, B = 4, P = 5 };  // A: wrist tilt about Y, B: about X, P: plunger

struct AxisConfig {
  double steps_per_unit;  // steps per mm (X, Y, Z, P) or per degree (A, B)
  double min_pos;         // soft limits, in units
  double max_pos;
  double max_speed;       // units per second
  double max_accel;       // units per second squared
  double home_speed;      // units per second
  double home_ref;        // position of the homing switch, in units
  double home_backoff;    // distance to back off after the switch, in units
  bool home_to_min;       // which end the homing switch is at
};

struct Config {
  std::array<AxisConfig, kAxes> axis;
  std::array<double, 5> park;   // X, Y, Z, A, B of the park pose
  double retract_mm;            // withdrawal length along the tool axis on abort
  double abort_speed_mm_s;      // path speed of the withdrawal and of PARK
  double stop_decel_factor;     // stop and abort decelerate this many times faster than normal moves
  uint32_t watchdog_ms;         // silence from the host that triggers an abort
  uint32_t tick_us;             // period of tick()
};

Config default_config();

struct Inputs {
  std::array<bool, kAxes> limit_min{};  // true when the switch is triggered (wired normally closed)
  std::array<bool, kAxes> limit_max{};
  bool abort_button = false;
  bool motor_power_ok = true;
};

struct Outputs {
  std::array<int32_t, kAxes> step_delta{};  // steps to emit during this tick
  bool drivers_enabled = false;
};

enum class State { NotHomed, Idle, Moving, Homing, Hold, Aborting, Aborted, Fault, PowerLoss };
enum class Cause { None, Button, Watchdog, Command, Limit, Power };

const char* state_name(State state);
const char* cause_name(Cause cause);

class Controller {
 public:
  explicit Controller(const Config& config);

  // Handles one command line (without the newline) and returns the reply (without the newline).
  std::string handle_line(const std::string& line, uint32_t now_ms);

  // Advances the controller by one tick of `config.tick_us`.
  Outputs tick(uint32_t now_ms, const Inputs& inputs);

  State state() const { return state_; }
  Cause cause() const { return cause_; }
  bool homed() const { return homed_; }
  double position(Axis axis) const { return steps_[axis] / config_.axis[axis].steps_per_unit; }

 private:
  struct Waypoint {
    std::array<double, kAxes> target;
    double feed;
  };
  struct Segment {
    bool active = false;
    bool stopping = false;
    std::array<double, kAxes> start{};
    std::array<double, kAxes> delta{};
    std::array<int32_t, kAxes> target_steps{};
    double sigma = 0.0;      // normalised progress along the segment, 0 to 1
    double sigma_dot = 0.0;  // and its rate
    double v_peak = 0.0;
    double accel = 0.0;
  };
  enum class HomePhase { Approach, Backoff };

  void plan_move(const std::array<double, kAxes>& target, double feed);
  void advance_segment(Outputs& out);
  void request_stop();
  void request_abort(Cause cause);
  void plan_abort_sequence();
  void enter_fault(Cause cause);
  void begin_homing();
  void tick_homing(const Inputs& in, Outputs& out);
  std::array<double, kAxes> current_units() const;
  bool within_soft_limits(const std::array<double, kAxes>& target) const;

  Config config_;
  State state_ = State::NotHomed;
  Cause cause_ = Cause::None;
  std::array<int32_t, kAxes> steps_{};
  bool homed_ = false;
  Segment seg_;
  std::deque<Waypoint> queue_;
  bool abort_planned_ = false;
  bool abort_sequence_ = false;
  bool rehome_ = false;    // the position can no longer be trusted: homing is required before moving again
  bool power_ok_ = true;   // last reading of the motor power input
  bool armed_ = false;
  uint32_t last_rx_ms_ = 0;
  int homing_pos_ = 0;
  HomePhase home_phase_ = HomePhase::Approach;
  double home_travel_ = 0.0;
  std::array<double, kAxes> accum_{};
};

}  // namespace fw
