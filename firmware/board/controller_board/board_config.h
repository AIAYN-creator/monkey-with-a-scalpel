// Pin map and pulse settings for the ESP32-S3 board layer (ESP32-S3-DevKitC-1 class board, module without octal
// PSRAM) with one TMC2209 module per axis in standalone mode. PROVISIONAL: nothing here has run on hardware.
// Plain C++ with no Arduino headers, so the host tests can check the pin map.
#pragma once

#include <array>

namespace board {

constexpr int kAxes = 6;  // X Y Z A B P, the order of fw::Axis
constexpr int kNoPin = -1;

constexpr std::array<int, kAxes> kStepPin{4, 5, 6, 7, 15, 16};
constexpr std::array<int, kAxes> kDirPin{17, 18, 8, 9, 10, 11};
constexpr int kEnablePin = 12;  // shared, low = drivers on (TMC2209 EN)
constexpr int kReservedUartTx = 13;  // reserved for TMC2209 UART mode later, not used in standalone mode
constexpr int kReservedUartRx = 14;

// Limit switches, wired normally closed to ground with the internal pull-up: a hit or a broken wire reads high.
// A pin set to kNoPin is not fitted and never triggers. The five switches of the design: X-, X+, Y-, Y+, Z top.
// Z bottom is protected by the soft limit and the hard stop only.
constexpr std::array<int, kAxes> kLimitMinPin{1, 21, kNoPin, kNoPin, kNoPin, kNoPin};
constexpr std::array<int, kAxes> kLimitMaxPin{2, 38, 40, kNoPin, kNoPin, kNoPin};

constexpr int kAbortPin = 41;     // normally closed push button to ground: pressed or broken wire reads high
constexpr int kPowerOkPin = 42;   // high = motor supply present, from a divider or opto after the contactor; low or open = lost
constexpr int kLedPin = 47;

// Microstepping of the TMC2209 modules, set with their MS1 and MS2 pins (check the datasheet table: both low is
// expected to give 1/8 with interpolation to 1/256). 200 full steps per revolution and 2 mm of screw lead.
constexpr double kMicrosteps = 8.0;
constexpr double kLinearStepsPerMm = 200.0 * kMicrosteps / 2.0;  // 800 steps/mm = 1.25 um per step

// Wrist axis B (rotation about X): a single-start worm on an 80-tooth sector (cad/modules/wrist_drive.py). The outer axis A is not
// designed yet and keeps the placeholder of the core.
constexpr double kWristBTeeth = 80.0;
constexpr double kWristBStepsPerDeg = 200.0 * kMicrosteps * kWristBTeeth / 360.0;  // about 355.6 steps per degree

// The step interrupt runs at this rate; a pulse is one period high and one low, so the largest step rate per axis
// is half of it. 20 mm/s at 800 steps/mm needs 16 kHz.
constexpr int kPulseTimerHz = 40000;
constexpr int kTickDivider = kPulseTimerHz / 1000;  // one controller tick (1 ms) every this many timer periods

// Pins that must not be used on this board: boot straps (0, 3, 45, 46), USB (19, 20), flash and PSRAM (26 to 37),
// the console UART (43, 44) and the on-board RGB LED (48).
constexpr bool forbidden(int pin) {
  return pin == 0 || pin == 3 || pin == 19 || pin == 20 || (pin >= 26 && pin <= 37) || pin == 43 || pin == 44 ||
         pin == 45 || pin == 46 || pin == 48;
}

constexpr int kPinCount = 3 * kAxes + 3 * kAxes + 6;

constexpr std::array<int, kPinCount> all_pins() {
  std::array<int, kPinCount> pins{};
  int n = 0;
  for (int pin : kStepPin) pins[n++] = pin;
  for (int pin : kDirPin) pins[n++] = pin;
  for (int pin : kLimitMinPin) pins[n++] = pin;
  for (int pin : kLimitMaxPin) pins[n++] = pin;
  pins[n++] = kEnablePin;
  pins[n++] = kReservedUartTx;
  pins[n++] = kReservedUartRx;
  pins[n++] = kAbortPin;
  pins[n++] = kPowerOkPin;
  pins[n++] = kLedPin;
  while (n < kPinCount) pins[n++] = kNoPin;  // padding
  return pins;
}

// True when no pin is used twice and none is forbidden.
constexpr bool pin_map_valid() {
  const std::array<int, kPinCount> pins = all_pins();
  for (int i = 0; i < kPinCount; ++i) {
    if (pins[i] == kNoPin) continue;
    if (forbidden(pins[i]) || pins[i] < 0 || pins[i] > 48) return false;
    for (int j = i + 1; j < kPinCount; ++j) {
      if (pins[j] == pins[i]) return false;
    }
  }
  return true;
}

static_assert(pin_map_valid(), "the pin map repeats a pin or uses a forbidden one");

}  // namespace board
