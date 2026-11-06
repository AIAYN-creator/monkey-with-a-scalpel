# Tool descriptors

One folder per tool, `tools/<name>/descriptor.yaml`. It is the **single source** of what the firmware knows about the tool (the table
`firmware/core/tool_table.h`, generated), of the host plugin that will expose its capabilities, and of the integration checks. Every
number is provisional until it is measured.

The contract behind it (mechanical, electrical, firmware, software, safe state) is the card `dec-iface`. In short: the controller reads
the id of a mounted tool, refuses a tool it does not know, powers a known one only after `TOOL ON`, cuts the power of tools that cut
on abort, and treats a tool change while powered or moving as a fault.

## Fields

| Field | Meaning |
|---|---|
| `id` | Integer from 1 to 65535, unique. What the tool interface reads |
| `name` | Lowercase letters, digits and underscores, unique |
| `class` | `injector`, `probe`, `cutter`, `drill`, `fluid`, `gripper`, `cautery`, `sensor` or `camera` |
| `mass_g` | Total mass, up to 1000 |
| `tip_mm` | Offset of the working point from the tool origin, three numbers, in the tool frame |
| `retract_mm` | Withdrawal length along the tool axis on abort, up to 100 |
| `axes` | Machine axes the tool uses, letters among `XYZABP` (for example `[P]` for the plunger) |
| `power.max_current_a` | Largest current of the switched tool power, up to 5 |
| `power.hw_cutoff` | The power also goes through a hardware cut-off outside the controller |
| `power.cut_on_abort` | The power is cut as soon as an abort starts, and stays off until the next `TOOL ON` |
| `safe_state` | What the tool does on abort, in words |
| `capabilities` | The operations the tool offers, as a non-empty list of names |
| `limits` | Optional. The numeric limits the simulation model enforces (a depth, a force, an energy). They do not go into the firmware table; the models in `host/toolsim` and the LLM validator read them |

Rules the generator enforces: a drill or a cautery must have `power.cut_on_abort: true`; a drill, a cautery or a cutter drawing more than
0.5 A must have `power.hw_cutoff: true`; ids and names are unique.

The YAML is a small subset (`key: value`, one level of nested keys, inline lists) so that no library is needed.

## Commands

```
python tools/gen_tool_table.py            rewrite firmware/core/tool_table.h
python tools/gen_tool_table.py --check    fail if the table is out of date or a descriptor is invalid (also in the CI)
python tools/test_gen_tool_table.py       tests of the parser and of the rules
```

```
python tools/int_check.py                 descriptors against the firmware table, the models, the LLM interface, the wiring and the CAD module,
                                          and every tool mounted, powered, aborted and changed on the simulated controller (needs g++)
```

A new tool is a new folder with its descriptor and a regenerated table; nothing else in the firmware changes. Its CAD module (`cad/modules/tool_<name>.py`), its model (`host/toolsim/models.py`) and its capability table (`host/llm/capabilities.py`) are checked against the descriptor by `cad/tool_check.py`, `host/toolsim/test_toolsim.py` and `host/llm/test_llm.py`.
