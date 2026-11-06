// Simulated controller for the host software: the real controller core plus a plant, driven over stdin and stdout.
//   g++ -std=c++17 -O2 -Ifirmware/core firmware/core/controller.cpp firmware/sim/sim_main.cpp -o sim_controller
//
// Every line is either a controller command (answered with the controller's reply, exactly as over the serial port) or a
// simulation control line that starts with '@':
//   @advance MS      run MS controller ticks of 1 ms (time only passes when the host asks for it)
//   @button 0|1      the ABORT button input
//   @power 0|1       the motor power input
//   @slip AXIS MM    the axis (X Y Z A B P) slips by MM under the controller, as after lost steps
//   @tool ID         mount the tool with this id (0 removes it); the id is what the tool interface would read
//   @phys            the physical position of every axis
//   @time            the simulated time in ms
//   @quit            exit
// The switches sit 2 units beyond the soft limits, as in the unit tests. Started with --require-tool, the controller refuses to
// home or move without a known tool.
#include <cstdio>
#include <iostream>
#include <sstream>
#include <string>

#include "controller.h"

using namespace fw;

namespace {

struct Plant {
  Config cfg = default_config();
  Controller ctl{default_config()};
  std::array<double, kAxes> phys{17.3, -40.0, 30.0, 10.0, -5.0, 30.0};
  bool button = false;
  bool power = true;
  bool tool_present = false;
  uint16_t tool_id = 0;
  uint32_t ms = 0;

  Inputs inputs() const {
    Inputs in;
    for (int i = 0; i < kAxes; ++i) {
      in.limit_min[i] = phys[i] <= cfg.axis[i].min_pos - 2.0;
      in.limit_max[i] = phys[i] >= cfg.axis[i].max_pos + 2.0;
    }
    in.abort_button = button;
    in.motor_power_ok = power;
    in.tool_present = tool_present;
    in.tool_id = tool_id;
    return in;
  }
  bool tool_power = false;
  void tick() {
    const Outputs out = ctl.tick(ms, inputs());
    tool_power = out.tool_power_enable;
    for (int i = 0; i < kAxes; ++i) phys[i] += out.step_delta[i] / cfg.axis[i].steps_per_unit;
    ++ms;
  }
};

int axis_index(char c) {
  const std::string letters = "XYZABP";
  const auto at = letters.find(static_cast<char>(std::toupper(static_cast<unsigned char>(c))));
  return at == std::string::npos ? -1 : static_cast<int>(at);
}

}  // namespace

int main(int argc, char** argv) {
  Config config = default_config();
  for (int i = 1; i < argc; ++i) {
    if (std::string(argv[i]) == "--require-tool") config.require_tool = true;
  }
  Plant plant;
  plant.cfg = config;
  plant.ctl = Controller(config);
  std::string line;
  while (std::getline(std::cin, line)) {
    while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) line.pop_back();
    if (line.empty() || line[0] != '@') {
      std::cout << plant.ctl.handle_line(line, plant.ms) << std::endl;
      continue;
    }
    std::istringstream in(line);
    std::string word;
    in >> word;
    if (word == "@advance") {
      long n = 0;
      in >> n;
      for (long i = 0; i < n; ++i) plant.tick();
      std::cout << "advanced " << n << std::endl;
    } else if (word == "@button") {
      int v = 0;
      in >> v;
      plant.button = v != 0;
      std::cout << "button " << v << std::endl;
    } else if (word == "@power") {
      int v = 1;
      in >> v;
      plant.power = v != 0;
      std::cout << "power " << v << std::endl;
    } else if (word == "@slip") {
      std::string axis;
      double mm = 0.0;
      in >> axis >> mm;
      const int i = axis.empty() ? -1 : axis_index(axis[0]);
      if (i < 0) {
        std::cout << "error:axis" << std::endl;
      } else {
        plant.phys[i] += mm;
        std::cout << "slipped" << std::endl;
      }
    } else if (word == "@tool") {
      int id = 0;
      in >> id;
      plant.tool_present = id != 0;
      plant.tool_id = static_cast<uint16_t>(id);
      std::cout << "tool " << id << std::endl;
    } else if (word == "@toolpower") {
      std::cout << (plant.tool_power ? 1 : 0) << std::endl;
    } else if (word == "@phys") {
      char buffer[200];
      std::snprintf(buffer, sizeof buffer, "x=%.4f y=%.4f z=%.4f a=%.3f b=%.3f p=%.4f", plant.phys[X], plant.phys[Y], plant.phys[Z],
                    plant.phys[A], plant.phys[B], plant.phys[P]);
      std::cout << buffer << std::endl;
    } else if (word == "@time") {
      std::cout << plant.ms << std::endl;
    } else if (word == "@quit") {
      return 0;
    } else {
      std::cout << "error:sim_command" << std::endl;
    }
  }
  return 0;
}
