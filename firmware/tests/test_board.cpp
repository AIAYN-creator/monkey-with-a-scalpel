// Host tests for the hardware-independent parts of the board layer: the step queue and the pin map.
//   g++ -std=c++17 -Wall -Wextra -Werror -O2 -Ifirmware/core -Ifirmware/board/controller_board firmware/tests/test_board.cpp -o test_board
//   ./test_board
#include <cmath>
#include <cstdio>

#include "board_config.h"
#include "step_queue.h"

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

using Queue = fw::StepQueue<6>;

// Runs `periods` timer periods on one axis and returns the number of rising edges and the final direction.
struct Run {
  int pulses = 0;
  int widest = 0;  // longest run of periods with the step pin high
  bool forward = true;
};

Run run_axis(Queue& q, int axis, int periods) {
  Run run;
  int width = 0;
  bool was_high = false;
  for (int i = 0; i < periods; ++i) {
    const Queue::Pulse p = q.next(axis);
    run.forward = p.forward;
    if (p.step) {
      if (!was_high) ++run.pulses;
      ++width;
      run.widest = width > run.widest ? width : run.widest;
    } else {
      width = 0;
    }
    was_high = p.step;
  }
  return run;
}

void test_pulse_count_and_shape() {
  std::printf("step queue emits exactly the requested steps as single-period pulses\n");
  Queue q;
  q.add(0, 16);
  const Run run = run_axis(q, 0, 100);
  CHECK(run.pulses == 16);
  CHECK(run.widest == 1);
  CHECK(q.pending(0) == 0);
  CHECK(run.forward);
}

void test_rate_limit() {
  std::printf("the largest rate is one pulse every two periods\n");
  Queue q;
  q.add(1, 40);
  const Run run = run_axis(q, 1, 40);
  CHECK(run.pulses == 20);
}

void test_direction() {
  std::printf("negative steps set the direction low and are counted\n");
  Queue q;
  q.add(2, -7);
  Run run = run_axis(q, 2, 20);
  CHECK(run.pulses == 7);
  CHECK(!run.forward);
  q.add(2, 3);
  run = run_axis(q, 2, 10);
  CHECK(run.pulses == 3);
  CHECK(run.forward);
}

void test_axes_are_independent() {
  std::printf("axes do not disturb each other\n");
  Queue q;
  q.add(0, 5);
  q.add(5, -9);
  const Run x = run_axis(q, 0, 30);
  const Run p = run_axis(q, 5, 30);
  CHECK(x.pulses == 5);
  CHECK(p.pulses == 9);
  CHECK(run_axis(q, 3, 30).pulses == 0);
}

void test_clear_and_reversal() {
  std::printf("clear drops the backlog and a reversal nets out\n");
  Queue q;
  q.add(0, 50);
  q.clear();
  CHECK(run_axis(q, 0, 200).pulses == 0);
  q.add(0, 10);
  q.add(0, -10);
  CHECK(run_axis(q, 0, 200).pulses == 0);
}

void test_pin_held_high_goes_low_after_clear() {
  std::printf("a pulse that is high when the queue is cleared still ends\n");
  Queue q;
  q.add(0, 5);
  CHECK(q.next(0).step);
  q.clear();
  CHECK(!q.next(0).step);
  CHECK(!q.next(0).step);
}

void test_overflow_is_reported() {
  std::printf("a backlog beyond the limit is reported, not silently dropped\n");
  Queue q;
  q.add(0, Queue::kMaxPending);
  CHECK(!q.overflow());
  q.add(0, 1);
  CHECK(q.overflow());
  CHECK(q.pending(0) == Queue::kMaxPending);
  q.clear_overflow();
  CHECK(!q.overflow());
  q.add(1, -Queue::kMaxPending - 5);
  CHECK(q.overflow());
  CHECK(q.pending(1) == -Queue::kMaxPending);
}

void test_pin_map() {
  std::printf("pin map\n");
  CHECK(board::pin_map_valid());
  CHECK(board::forbidden(0));
  CHECK(board::forbidden(19));
  CHECK(board::forbidden(33));
  CHECK(!board::forbidden(4));
  CHECK(board::kLinearStepsPerMm == 800.0);
  CHECK(std::fabs(board::kWristBStepsPerDeg - 355.5556) < 1e-3);  // 1600 microsteps per turn, 80 teeth
  // 20 mm/s must fit under half of the timer rate
  CHECK(20.0 * board::kLinearStepsPerMm <= board::kPulseTimerHz / 2.0);
  CHECK(board::kTickDivider * 1000 == board::kPulseTimerHz);
}

}  // namespace

int main() {
  test_pulse_count_and_shape();
  test_rate_limit();
  test_direction();
  test_axes_are_independent();
  test_clear_and_reversal();
  test_pin_held_high_goes_low_after_clear();
  test_overflow_is_reported();
  test_pin_map();
  std::printf("\n%d checks, %d failures\n%s\n", g_checks, g_failures, g_failures == 0 ? "ALL TESTS PASSED" : "TESTS FAILED");
  return g_failures == 0 ? 0 : 1;
}
