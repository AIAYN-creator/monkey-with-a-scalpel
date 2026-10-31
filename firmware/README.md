# Controller firmware core

Hardware-independent motion and safety logic for the gantry controller. No Arduino or ESP32 headers: the
board code feeds it the switch states and the clock, and turns the step counts it returns into pulses. This
keeps every safety rule testable on a PC.

**Status:** the core and its host tests exist. The board layer (step pulses, serial port, pins) does not,
and nothing here has run on hardware yet.

The core also compiles for the ESP32 with `arduino-cli` (core `esp32:esp32` 3.3.12, board
`esp32:esp32:esp32`, all warnings on, none reported), using a sketch that only instantiates the controller:
291,392 bytes of program storage (22 %) and 22,948 bytes of RAM (7 %). On Windows, keep the Arduino data
directories on a short path: the toolchain fails to unpack under the 260-character path limit.

## Build and test

From the repository root, on one line:

```
g++ -std=c++17 -Wall -Wextra -Werror -O2 -Ifirmware/core firmware/core/controller.cpp firmware/tests/test_controller.cpp -o test_controller
./test_controller
```

To check that the tests would notice a broken safety rule, inject one fault at a time and require a failure (11 faults, all detected today):

```
python firmware/tests/mutation_check.py
```

## Protocol

One ASCII command per line, answered with `ok ...` or `error:<code>`. Axes are `X Y Z` (mm), `A B` (wrist
tilt, degrees) and `P` (plunger, mm).

| Command | Effect |
|---|---|
| `PING` | Heartbeat. Any valid line also counts. |
| `STATUS` | State, homed flag, last abort cause and the six positions. |
| `HOME` | Homes Z (to its top switch), then X, Y, A, B and P. |
| `MOVE X.. Y.. Z.. A.. B.. P.. F..` | Absolute coordinated move. `F` limits the XYZ path speed in mm/s. |
| `PARK` | Raises Z to the park height, then goes to the park pose. |
| `STOP` | Decelerates to a halt and holds. The tool stays where it is. |
| `ABORT` | Stops, withdraws the needle along its own axis, raises and parks. |
| `CLEAR` | Leaves `aborted`, `fault` or `power_loss`. After a fault or a power loss, homing is required again. |

Error codes: `syntax`, `unknown_command`, `not_homed`, `busy`, `state`, `limit`, `power`.

## Safety behaviour

- **ABORT** is triggered by the `ABORT` command, the abort button input, or the watchdog. It runs inside the
  controller, so it works with the host hung. The withdrawal follows the tool axis computed from the wrist
  angles, clamped to the soft limits.
- **Watchdog:** after the first command, and once homed, silence from the host for longer than
  `watchdog_ms` triggers an abort. The host must keep sending `PING`, also during moves.
- **Limit switches** are inputs. One hit while moving towards it latches a fault and cancels that tick's
  steps. During homing they are the reference.
- **Motor power** is only monitored. The emergency stop that cuts it is wired outside this code.
- After an abort, a fault or a power loss nothing moves until `CLEAR`.

## Known limits

- Homing accuracy is the approach speed times the tick period (5 µm at 5 mm/s and 1 ms). A board layer that
  captures the step count in the switch interrupt removes it.
- The default configuration is illustrative, not tuned to any hardware. It uses 100 mm of linear travel in total (-50 to +50 mm), with the limit switches 2 mm beyond the soft limits.
- The withdrawal does not know how deep the needle is: it always withdraws `retract_mm`.
- This is not certified safety software.
