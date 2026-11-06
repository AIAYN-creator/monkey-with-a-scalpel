# Controller firmware core

Hardware-independent motion and safety logic for the gantry controller. No Arduino or ESP32 headers: the
board code feeds it the switch states and the clock, and turns the step counts it returns into pulses. This
keeps every safety rule testable on a PC.

**Status:** the core, its host tests and a **provisional board layer for an ESP32-S3 with one TMC2209 per
axis** exist. Both compile; **nothing here has run on hardware yet** and the pin map, the microstepping and the
wrist and plunger step counts are unverified assumptions.

## Board layer (ESP32-S3, six TMC2209 modules in standalone mode)

`firmware/board/controller_board/` is an Arduino sketch. A hardware timer fires at 40 kHz and emits the queued step
pulses (`firmware/core/step_queue.h`, tested on the PC); every millisecond the loop reads the pins, runs the core
and queues the steps it returns. Serial lines are read without blocking. Pins, polarity and microstepping are in
`board_config.h`: switches and the ABORT button are normally closed to ground with pull-ups, so a hit or a broken
wire reads as triggered, and a missing motor-power signal reads as power lost. The extra command `BOARD` reports
timer overruns.

- 1/8 microstepping gives 800 steps/mm (1.25 um) and 16 kHz at 20 mm/s, under the 20 kHz limit of the pulse timer.
- The steps per degree of the wrist axis B come from the worm drive of the CAD (80-tooth sector, about 355.6 steps per degree at 1/8 microstepping). The outer axis A and the plunger steps per unit are placeholders until the mechanics exist.
- The step pulse interrupt runs from flash cache; if it misbehaves during flash writes, move it to IRAM.
- On the bench, fit the ABORT button and the power-ok signal or the controller will (correctly) refuse to move.

Compile (needs `arduino-cli` with the `esp32:esp32` core; on Windows keep its data directories on a short path):

```
firmware/board/build.sh
```

Last compile: `esp32:esp32:esp32s3`, all warnings on, none reported, 332,494 bytes of program storage (25 %) and
23,096 bytes of RAM (7 %).

The earlier compile check of the bare core for the classic ESP32 (`esp32:esp32:esp32`) remains valid for the core.

## Build and test

From the repository root, on one line:

```
g++ -std=c++17 -Wall -Wextra -Werror -O2 -Ifirmware/core firmware/core/controller.cpp firmware/tests/test_controller.cpp -o test_controller
./test_controller
g++ -std=c++17 -Wall -Wextra -Werror -O2 -Ifirmware/core -Ifirmware/board/controller_board firmware/tests/test_board.cpp -o test_board
./test_board
```

To check that the tests would notice a broken safety rule, inject one fault at a time and require a failure (20 faults across the core, the step queue and the pin map, all detected today):

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
| `TOOL [ON\|OFF]` | The tool interface: `ok tool=<name\|none\|unknown> id=<n> ready=<0\|1> power=<0\|1>`. `TOOL ON` asks for the switched tool power of a known tool; `TOOL OFF` withdraws the request. |

Error codes: `syntax`, `unknown_command`, `not_homed`, `busy`, `state`, `limit`, `power`, `tool`. `STATUS` ends with `tool=<name>`.

## Tool interface

The controller reads a presence sensor and an identifier from the mounted tool (`Inputs::tool_present`, `tool_id`) and knows the tools of
the generated table `core/tool_table.h` (source: `tools/*/descriptor.yaml`, see `tools/README.md`).

- With `Config::require_tool` set, `HOME`, `MOVE` and `PARK` are refused with `error:tool` unless a known tool is mounted. The board layer
  does not set it yet: the connector, the presence sensor and the identification line are not chosen.
- The switched tool power (`Outputs::tool_power_enable`) is on only while the host asked for it with `TOOL ON`, a known tool is mounted and
  the motor supply is present. A fault, a power loss, or an abort of a tool that cuts its power on abort withdraws the request, and it
  takes a new `TOOL ON` to power the tool again. The emergency stop contactor cuts the tool power independently of all this.
- An abort withdraws the tool by its own `retract_mm`.
- Mounting, removing or swapping a tool while its power is on, or while the machine moves, homes or aborts, is a fault (`cause=tool`).
  A tool is changed at rest with `TOOL OFF`.

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
