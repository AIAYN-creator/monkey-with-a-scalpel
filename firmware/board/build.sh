#!/usr/bin/env bash
# Compiles the board layer for the ESP32-S3 with arduino-cli. Usage, from the repository root:
#   firmware/board/build.sh [fqbn]            (default fqbn: esp32:esp32:esp32s3)
# The Arduino build wants the sketch folder to hold every source, so the core is copied next to it in a temporary
# folder. Keep ARDUINO_DIRECTORIES_DATA on a short path on Windows (the toolchain fails under the 260-character limit).
set -euo pipefail
FQBN="${1:-esp32:esp32:esp32s3}"
STAGE="$(mktemp -d)/controller_board"
mkdir -p "$STAGE"
cp firmware/board/controller_board/* "$STAGE"/
cp firmware/core/controller.cpp firmware/core/*.h "$STAGE"/
arduino-cli compile --fqbn "$FQBN" --warnings all "$STAGE"
