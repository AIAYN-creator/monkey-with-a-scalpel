// Turns the step counts that the controller core returns every tick into step pulses, one decision per call of
// `next()`. Hardware independent: the board layer calls `next()` from a fixed-rate timer interrupt and writes the
// pins; the host tests call it directly. Not thread safe: the board layer guards `add()` and `clear()` against
// the interrupt.
#pragma once

#include <array>
#include <cstdint>

namespace fw {

template <int N>
class StepQueue {
 public:
  struct Pulse {
    bool step = false;     // the step pin must be high after this call
    bool forward = true;   // level of the direction pin (true = positive direction)
  };

  // Largest backlog per axis. The core never asks for more than a few dozen steps per tick, so a larger backlog
  // means the pulse generator is not keeping up and steps would be lost.
  static constexpr int32_t kMaxPending = 4000;

  void add(int axis, int32_t steps) {
    int64_t total = static_cast<int64_t>(pending_[axis]) + steps;
    if (total > kMaxPending || total < -kMaxPending) {
      overflow_ = true;
      total = total > 0 ? kMaxPending : -kMaxPending;
    }
    pending_[axis] = static_cast<int32_t>(total);
  }

  // Drops every pending step (drivers disabled or fault). Pins that are high still go low on the next call.
  void clear() { pending_.fill(0); }

  // One call per timer period and axis: a pulse is high for one period and low for the next, so the largest step
  // rate is half the timer rate.
  Pulse next(int axis) {
    Pulse pulse;
    pulse.forward = forward_[axis];
    if (high_[axis]) {
      high_[axis] = false;
      return pulse;
    }
    if (pending_[axis] != 0) {
      forward_[axis] = pending_[axis] > 0;
      pulse.forward = forward_[axis];
      pending_[axis] += forward_[axis] ? -1 : 1;
      high_[axis] = true;
      pulse.step = true;
    }
    return pulse;
  }

  int32_t pending(int axis) const { return pending_[axis]; }
  bool overflow() const { return overflow_; }
  void clear_overflow() { overflow_ = false; }

 private:
  std::array<int32_t, N> pending_{};
  std::array<bool, N> high_{};
  std::array<bool, N> forward_{};
  bool overflow_ = false;
};

}  // namespace fw
