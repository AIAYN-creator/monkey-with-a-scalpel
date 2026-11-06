// Board layer for the controller core on an ESP32-S3 with one TMC2209 per axis (standalone mode).
// PROVISIONAL: it compiles but has never run on hardware. Nothing here is certified safety software; the
// emergency stop that cuts motor power is wired outside this code.
//
// Flow: a hardware timer fires at kPulseTimerHz. Every period it emits the step pulses queued so far; every
// kTickDivider periods it flags a controller tick. loop() reads the pins, runs the core and queues the steps it
// returns. Serial lines are read without blocking.
#include <Arduino.h>

#include "controller.h"
#include "step_queue.h"

#include "board_config.h"

namespace {

fw::Controller* controller = nullptr;
fw::StepQueue<board::kAxes> queue;
portMUX_TYPE queue_lock = portMUX_INITIALIZER_UNLOCKED;
hw_timer_t* pulse_timer = nullptr;
volatile uint32_t ticks_due = 0;
volatile bool drivers_on = false;
uint32_t divider_count = 0;
uint32_t overruns = 0;
String line;

fw::Config make_config() {
  fw::Config c = fw::default_config();
  for (int axis : {fw::X, fw::Y, fw::Z}) c.axis[axis].steps_per_unit = board::kLinearStepsPerMm;
  c.axis[fw::P].steps_per_unit = board::kLinearStepsPerMm;  // placeholder: depends on the actuator, to measure
  c.axis[fw::B].steps_per_unit = board::kWristBStepsPerDeg;  // worm drive of the CAD (axis B, rotation about X)
  // The steps per degree of the outer wrist axis A and the plunger lead are illustrative: set them from the real drive.
  return c;
}

void IRAM_ATTR on_pulse_timer() {
  portENTER_CRITICAL_ISR(&queue_lock);
  for (int axis = 0; axis < board::kAxes; ++axis) {
    const auto pulse = queue.next(axis);
    digitalWrite(board::kDirPin[axis], pulse.forward ? HIGH : LOW);
    digitalWrite(board::kStepPin[axis], pulse.step ? HIGH : LOW);
  }
  portEXIT_CRITICAL_ISR(&queue_lock);
  if (++divider_count >= board::kTickDivider) {
    divider_count = 0;
    ticks_due = ticks_due + 1;
  }
}

bool read_switch(int pin) {  // normally closed to ground: high means hit or broken wire
  return pin != board::kNoPin && digitalRead(pin) == HIGH;
}

fw::Inputs read_inputs() {
  fw::Inputs in;
  for (int axis = 0; axis < board::kAxes; ++axis) {
    in.limit_min[axis] = read_switch(board::kLimitMinPin[axis]);
    in.limit_max[axis] = read_switch(board::kLimitMaxPin[axis]);
  }
  in.abort_button = digitalRead(board::kAbortPin) == HIGH;
  in.motor_power_ok = digitalRead(board::kPowerOkPin) == HIGH;
  return in;
}

void set_drivers(bool on) {
  digitalWrite(board::kEnablePin, on ? LOW : HIGH);  // TMC2209 EN is active low
  drivers_on = on;
}

void answer(const String& text) {
  Serial.println(text);
}

void handle_serial_line(const String& text) {
  if (text == "BOARD") {
    answer(String("ok board esp32s3 overruns=") + overruns + " pending_overflow=" + (queue.overflow() ? 1 : 0));
    return;
  }
  answer(controller->handle_line(text.c_str(), millis()).c_str());
}

void read_serial() {
  while (Serial.available()) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r') continue;
    if (c == '\n') {
      handle_serial_line(line);
      line = "";
    } else if (line.length() < 120) {
      line += c;
    } else {
      line = "";
      answer("error:syntax");
    }
  }
}

void run_tick() {
  const fw::Outputs out = controller->tick(millis(), read_inputs());
  portENTER_CRITICAL(&queue_lock);
  if (!out.drivers_enabled) queue.clear();
  for (int axis = 0; axis < board::kAxes; ++axis) queue.add(axis, out.step_delta[axis]);
  const bool lost_steps = queue.overflow();
  portEXIT_CRITICAL(&queue_lock);
  if (out.drivers_enabled != drivers_on) set_drivers(out.drivers_enabled);
  if (lost_steps) {  // the pulse generator fell behind: the position is no longer trusted
    controller->handle_line("ABORT", millis());
    portENTER_CRITICAL(&queue_lock);
    queue.clear_overflow();
    portEXIT_CRITICAL(&queue_lock);
  }
  digitalWrite(board::kLedPin, controller->state() == fw::State::Idle || controller->state() == fw::State::Moving);
}

}  // namespace

void setup() {
  Serial.begin(115200);
  pinMode(board::kEnablePin, OUTPUT);
  set_drivers(false);  // drivers off until the core asks for them
  for (int axis = 0; axis < board::kAxes; ++axis) {
    pinMode(board::kStepPin[axis], OUTPUT);
    pinMode(board::kDirPin[axis], OUTPUT);
    digitalWrite(board::kStepPin[axis], LOW);
    if (board::kLimitMinPin[axis] != board::kNoPin) pinMode(board::kLimitMinPin[axis], INPUT_PULLUP);
    if (board::kLimitMaxPin[axis] != board::kNoPin) pinMode(board::kLimitMaxPin[axis], INPUT_PULLUP);
  }
  pinMode(board::kAbortPin, INPUT_PULLUP);   // open or broken wire reads high = abort
  pinMode(board::kPowerOkPin, INPUT_PULLDOWN);  // open or lost reads low = no motor power
  pinMode(board::kLedPin, OUTPUT);
  static fw::Controller instance(make_config());
  controller = &instance;
  pulse_timer = timerBegin(1000000);  // 1 MHz base
  timerAttachInterrupt(pulse_timer, &on_pulse_timer);
  timerAlarm(pulse_timer, 1000000 / board::kPulseTimerHz, true, 0);
}

void loop() {
  read_serial();
  uint32_t due;
  portENTER_CRITICAL(&queue_lock);
  due = ticks_due;
  ticks_due = 0;
  portEXIT_CRITICAL(&queue_lock);
  if (due > 1) overruns += due - 1;  // the loop was too slow to run every tick
  if (due > 0) run_tick();
}
