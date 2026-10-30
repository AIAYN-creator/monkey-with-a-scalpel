#include "controller.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace fw {

namespace {

constexpr double kPi = 3.14159265358979323846;
constexpr int kHomingOrder[kAxes] = {Z, X, Y, A, B, P};  // Z first, towards its top switch, to clear the work area
constexpr char kAxisLetters[kAxes] = {'X', 'Y', 'Z', 'A', 'B', 'P'};

int axis_from_letter(char letter) {
  for (int i = 0; i < kAxes; ++i) {
    if (kAxisLetters[i] == letter) return i;
  }
  return -1;
}

std::string upper(std::string text) {
  for (char& c : text) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
  return text;
}

bool parse_number(const std::string& text, double& value) {
  if (text.empty()) return false;
  char* end = nullptr;
  value = std::strtod(text.c_str(), &end);
  return end != nullptr && *end == '\0' && std::isfinite(value);
}

}  // namespace

Config default_config() {
  Config c{};
  const AxisConfig linear_min = {1600.0, -100.0, 100.0, 20.0, 200.0, 5.0, -102.0, 4.0, true};
  const AxisConfig linear_max = {1600.0, -100.0, 100.0, 20.0, 200.0, 5.0, 102.0, 4.0, false};
  const AxisConfig wrist_min = {100.0, -45.0, 45.0, 30.0, 300.0, 10.0, -47.0, 4.0, true};
  const AxisConfig plunger = {1600.0, 0.0, 60.0, 5.0, 50.0, 2.0, -2.0, 4.0, true};
  c.axis = {linear_min, linear_min, linear_max, wrist_min, wrist_min, plunger};
  c.park = {0.0, 0.0, 90.0, 0.0, 0.0};
  c.retract_mm = 20.0;
  c.abort_speed_mm_s = 10.0;
  c.stop_decel_factor = 4.0;
  c.watchdog_ms = 1000;
  c.tick_us = 1000;
  return c;
}

const char* state_name(State state) {
  switch (state) {
    case State::NotHomed: return "not_homed";
    case State::Idle: return "idle";
    case State::Moving: return "moving";
    case State::Homing: return "homing";
    case State::Hold: return "hold";
    case State::Aborting: return "aborting";
    case State::Aborted: return "aborted";
    case State::Fault: return "fault";
    case State::PowerLoss: return "power_loss";
  }
  return "unknown";
}

const char* cause_name(Cause cause) {
  switch (cause) {
    case Cause::None: return "none";
    case Cause::Button: return "button";
    case Cause::Watchdog: return "watchdog";
    case Cause::Command: return "command";
    case Cause::Limit: return "limit";
    case Cause::Power: return "power";
  }
  return "unknown";
}

Controller::Controller(const Config& config) : config_(config) {}

std::array<double, kAxes> Controller::current_units() const {
  std::array<double, kAxes> units{};
  for (int i = 0; i < kAxes; ++i) units[i] = steps_[i] / config_.axis[i].steps_per_unit;
  return units;
}

bool Controller::within_soft_limits(const std::array<double, kAxes>& target) const {
  for (int i = 0; i < kAxes; ++i) {
    if (target[i] < config_.axis[i].min_pos - 1e-9 || target[i] > config_.axis[i].max_pos + 1e-9) return false;
  }
  return true;
}

// Plans a straight move in which every axis follows the same trapezoidal profile, scaled so that no axis
// exceeds its own speed or acceleration limit. With c the cruise time and ta the acceleration time:
// c >= D/vmax and ta*c >= D/amax for every axis, and c >= ta so that the profile is valid.
void Controller::plan_move(const std::array<double, kAxes>& target, double feed) {
  const std::array<double, kAxes> start = current_units();
  double u = 0.0;
  double w = 0.0;
  double path = 0.0;
  double path_accel = 1e30;
  for (int i = 0; i < kAxes; ++i) {
    const double d = std::fabs(target[i] - start[i]);
    u = std::max(u, d / config_.axis[i].max_speed);
    w = std::max(w, d / config_.axis[i].max_accel);
    if (i <= Z) {
      path += d * d;
      path_accel = std::min(path_accel, config_.axis[i].max_accel);
    }
  }
  path = std::sqrt(path);
  if (feed > 0.0 && path > 0.0) {
    u = std::max(u, path / feed);
    w = std::max(w, path / path_accel);
  }
  seg_ = Segment{};
  seg_.start = start;
  for (int i = 0; i < kAxes; ++i) {
    seg_.delta[i] = target[i] - start[i];
    seg_.target_steps[i] = static_cast<int32_t>(std::llround(target[i] * config_.axis[i].steps_per_unit));
  }
  if (w <= 1e-12 || u <= 1e-12) {
    // Nothing to move beyond rounding: snap to the target steps with no profile.
    seg_.active = false;
    return;
  }
  const double c = std::max(u, std::sqrt(w));
  const double ta = w / c;
  seg_.v_peak = 1.0 / c;
  seg_.accel = seg_.v_peak / ta;
  seg_.active = true;
}

void Controller::advance_segment(Outputs& out) {
  const double dt = config_.tick_us * 1e-6;
  Segment& s = seg_;
  const double remaining = 1.0 - s.sigma;
  if (s.stopping) {
    s.sigma_dot = std::max(0.0, s.sigma_dot - s.accel * config_.stop_decel_factor * dt);
  } else if (s.sigma_dot * s.sigma_dot / (2.0 * s.accel) >= remaining) {
    s.sigma_dot = std::max(s.sigma_dot - s.accel * dt, 0.01 * s.v_peak);
  } else {
    s.sigma_dot = std::min(s.sigma_dot + s.accel * dt, s.v_peak);
  }
  s.sigma += s.sigma_dot * dt;
  const bool arrived = s.sigma >= 1.0;
  const bool stopped = s.stopping && s.sigma_dot <= 0.0;
  if (arrived) s.sigma = 1.0;
  for (int i = 0; i < kAxes; ++i) {
    int32_t next = arrived ? s.target_steps[i]
                           : static_cast<int32_t>(std::llround((s.start[i] + s.sigma * s.delta[i]) *
                                                               config_.axis[i].steps_per_unit));
    out.step_delta[i] += next - steps_[i];
    steps_[i] = next;
  }
  if (arrived || stopped) s.active = false;
}

void Controller::request_stop() {
  if (state_ == State::Moving || state_ == State::Homing) {
    queue_.clear();
    if (state_ == State::Homing) {
      state_ = State::NotHomed;
      seg_.active = false;
    } else if (seg_.active) {
      seg_.stopping = true;
    }
  }
}

void Controller::request_abort(Cause cause) {
  if (state_ == State::Aborting || state_ == State::Aborted || state_ == State::PowerLoss) return;
  if (!homed_) {
    // Without a known position there is nothing to retract to: just stop.
    seg_.active = false;
    queue_.clear();
    if (state_ == State::Homing) state_ = State::NotHomed;
    cause_ = cause;
    return;
  }
  cause_ = cause;
  state_ = State::Aborting;
  abort_sequence_ = true;
  abort_planned_ = false;
  queue_.clear();
  if (seg_.active) seg_.stopping = true;
}

// Withdraw along the tool axis, then raise to the park height, then go to the park pose.
void Controller::plan_abort_sequence() {
  const std::array<double, kAxes> p = current_units();
  const double a = p[A] * kPi / 180.0;
  const double b = p[B] * kPi / 180.0;
  // Needle direction is R*(0,0,-1) with R = Ry(a)*Rx(b); the withdrawal is the opposite.
  const double u[3] = {std::cos(b) * std::sin(a), -std::sin(b), std::cos(b) * std::cos(a)};
  double s = config_.retract_mm;
  for (int i = 0; i <= Z; ++i) {
    if (std::fabs(u[i]) < 1e-9) continue;
    const double room = (u[i] > 0 ? config_.axis[i].max_pos - p[i] : config_.axis[i].min_pos - p[i]) / u[i];
    s = std::min(s, std::max(0.0, room));
  }
  std::array<double, kAxes> retract = p;
  for (int i = 0; i <= Z; ++i) retract[i] = p[i] + s * u[i];
  queue_.push_back({retract, config_.abort_speed_mm_s});
  std::array<double, kAxes> up = retract;
  up[Z] = std::max(retract[Z], config_.park[Z]);
  if (up[Z] > retract[Z] + 1e-9) queue_.push_back({up, config_.abort_speed_mm_s});
  std::array<double, kAxes> park = up;
  for (int i = 0; i < 5; ++i) park[i] = config_.park[i];
  park[Z] = up[Z];
  queue_.push_back({park, config_.abort_speed_mm_s});
}

void Controller::enter_fault(Cause cause) {
  seg_.active = false;
  queue_.clear();
  abort_sequence_ = false;
  rehome_ = true;
  cause_ = cause;
  state_ = State::Fault;
}

void Controller::begin_homing() {
  state_ = State::Homing;
  homed_ = false;
  homing_pos_ = 0;
  home_phase_ = HomePhase::Approach;
  home_travel_ = 0.0;
  accum_.fill(0.0);
  seg_.active = false;
  queue_.clear();
}

void Controller::tick_homing(const Inputs& in, Outputs& out) {
  const int axis = kHomingOrder[homing_pos_];
  const AxisConfig& ac = config_.axis[axis];
  const double dir = ac.home_to_min ? -1.0 : 1.0;
  if (home_phase_ == HomePhase::Approach) {
    const bool tripped = ac.home_to_min ? in.limit_min[axis] : in.limit_max[axis];
    if (tripped) {
      steps_[axis] = static_cast<int32_t>(std::llround(ac.home_ref * ac.steps_per_unit));
      std::array<double, kAxes> target = current_units();
      target[axis] = ac.home_ref - dir * ac.home_backoff;
      plan_move(target, 0.0);
      home_phase_ = HomePhase::Backoff;
      return;
    }
    accum_[axis] += dir * ac.home_speed * ac.steps_per_unit * config_.tick_us * 1e-6;
    const int32_t whole = static_cast<int32_t>(accum_[axis]);
    accum_[axis] -= whole;
    out.step_delta[axis] += whole;
    steps_[axis] += whole;
    home_travel_ += std::fabs(whole) / ac.steps_per_unit;
    if (home_travel_ > (ac.max_pos - ac.min_pos) * 1.5 + 10.0) enter_fault(Cause::Limit);  // switch never found
    return;
  }
  if (seg_.active) {
    advance_segment(out);
    if (seg_.active) return;
  }
  home_phase_ = HomePhase::Approach;
  home_travel_ = 0.0;
  if (++homing_pos_ >= kAxes) {
    homed_ = true;
    state_ = State::Idle;
  }
}

Outputs Controller::tick(uint32_t now_ms, const Inputs& in) {
  Outputs out;
  power_ok_ = in.motor_power_ok;
  if (!in.motor_power_ok && state_ != State::PowerLoss) {
    seg_.active = false;
    queue_.clear();
    abort_sequence_ = false;
    homed_ = false;  // steps may have been lost with the power
    cause_ = Cause::Power;
    state_ = State::PowerLoss;
  }
  if (state_ == State::PowerLoss) return out;

  if (in.abort_button) request_abort(Cause::Button);
  if (armed_ && homed_ && now_ms - last_rx_ms_ > config_.watchdog_ms) request_abort(Cause::Watchdog);

  out.drivers_enabled = state_ != State::Fault;
  const std::array<int32_t, kAxes> before = steps_;

  if (state_ == State::Homing) {
    tick_homing(in, out);
  } else if (state_ == State::Moving || state_ == State::Aborting) {
    if (!seg_.active && !queue_.empty()) {
      plan_move(queue_.front().target, queue_.front().feed);
      queue_.pop_front();
    }
    if (seg_.active) advance_segment(out);
    if (!seg_.active && queue_.empty()) {
      if (state_ == State::Aborting && !abort_planned_) {
        plan_abort_sequence();
        abort_planned_ = true;
      } else if (state_ == State::Aborting) {
        state_ = State::Aborted;
        abort_sequence_ = false;
      } else {
        state_ = seg_.stopping ? State::Hold : State::Idle;
      }
    }
  }

  // A switch hit while moving towards it latches a fault, except during homing.
  if (state_ != State::Homing) {
    for (int i = 0; i < kAxes; ++i) {
      if ((in.limit_min[i] && out.step_delta[i] < 0) || (in.limit_max[i] && out.step_delta[i] > 0)) {
        steps_ = before;
        out.step_delta.fill(0);
        enter_fault(Cause::Limit);
        out.drivers_enabled = false;
        break;
      }
    }
  }
  if (state_ == State::Aborting || abort_sequence_) out.drivers_enabled = state_ != State::Fault;
  return out;
}

std::string Controller::handle_line(const std::string& line, uint32_t now_ms) {
  armed_ = true;
  last_rx_ms_ = now_ms;

  std::string text = upper(line);
  std::deque<std::string> tokens;
  std::string current;
  for (char c : text) {
    if (c == ' ' || c == '\t' || c == '\r') {
      if (!current.empty()) tokens.push_back(current);
      current.clear();
    } else {
      current += c;
    }
  }
  if (!current.empty()) tokens.push_back(current);
  if (tokens.empty()) return "error:syntax";
  const std::string command = tokens.front();
  tokens.pop_front();
  char buffer[200];

  if (command == "PING") return "ok pong";

  if (command == "STATUS") {
    std::snprintf(buffer, sizeof buffer, "ok state=%s homed=%d cause=%s x=%.4f y=%.4f z=%.4f a=%.3f b=%.3f p=%.4f",
                  state_name(state_), homed_ ? 1 : 0, cause_name(cause_), position(X), position(Y), position(Z),
                  position(A), position(B), position(P));
    return buffer;
  }

  if (command == "HOME") {
    if (state_ != State::NotHomed && state_ != State::Idle) return "error:state";
    begin_homing();
    return "ok homing";
  }

  if (command == "MOVE") {
    if (!homed_) return "error:not_homed";
    if (state_ == State::Moving) return "error:busy";
    if (state_ != State::Idle && state_ != State::Hold) return "error:state";
    std::array<double, kAxes> target = current_units();
    double feed = 0.0;
    bool any = false;
    for (const std::string& token : tokens) {
      double value = 0.0;
      if (token.size() < 2 || !parse_number(token.substr(1), value)) return "error:syntax";
      if (token[0] == 'F') {
        if (value <= 0.0) return "error:syntax";
        feed = value;
        continue;
      }
      const int axis = axis_from_letter(token[0]);
      if (axis < 0) return "error:syntax";
      target[axis] = value;
      any = true;
    }
    if (!any) return "error:syntax";
    if (!within_soft_limits(target)) return "error:limit";
    queue_.clear();
    plan_move(target, feed);
    state_ = State::Moving;
    return "ok";
  }

  if (command == "PARK") {
    if (!homed_) return "error:not_homed";
    if (state_ != State::Idle && state_ != State::Hold) return "error:state";
    std::array<double, kAxes> up = current_units();
    up[Z] = std::max(up[Z], config_.park[Z]);
    std::array<double, kAxes> park = up;
    for (int i = 0; i < 5; ++i) park[i] = config_.park[i];
    park[Z] = up[Z];
    queue_.clear();
    queue_.push_back({park, config_.abort_speed_mm_s});
    plan_move(up, config_.abort_speed_mm_s);
    state_ = State::Moving;
    return "ok";
  }

  if (command == "STOP") {
    if (state_ == State::Idle || state_ == State::Hold || state_ == State::NotHomed) return "ok";
    request_stop();
    return "ok";
  }

  if (command == "ABORT") {
    if (state_ == State::PowerLoss) return "error:power";
    if (!homed_) return "error:not_homed";
    request_abort(Cause::Command);
    return "ok";
  }

  if (command == "CLEAR") {
    if (state_ == State::PowerLoss && !power_ok_) return "error:power";
    if (state_ != State::Aborted && state_ != State::Fault && state_ != State::PowerLoss) return "error:state";
    // After a fault or a power loss the position is not trusted, so homing is required again.
    const bool must_rehome = rehome_ || state_ == State::Fault || state_ == State::PowerLoss;
    cause_ = Cause::None;
    rehome_ = false;
    homed_ = homed_ && !must_rehome;
    state_ = must_rehome ? State::NotHomed : State::Idle;
    return "ok";
  }

  return "error:unknown_command";
}

}  // namespace fw
