# CAD renders

Renders of the provisional parametric CAD (`cad/`). Orange parts are printed, light grey is machined aluminium, dark grey is a bought
part drawn as a placeholder. **Every size is an assumption or a catalogue value; nothing has been measured and nothing should be printed yet.**

| Image | What it shows |
|---|---|
| [system_100mm.png](system_100mm.png) | The whole system with the first prototype's 100 mm of travel per axis, fixed tool and active wrist |
| [system_400x250x150.png](system_400x250x150.png) | The same system with the large travel (X 400, Y 250, Z 150 mm): the tool rack and the wash station are inside the reach of the gantry, the panel, microscope and cameras are outside it |
| [tool_head.png](tool_head.png) | The tool head: syringe, actuator, clamp and mount |
| [tools_and_wash_station.png](tools_and_wash_station.png) | The eight tools (injector, probe, scalpel, drill, fluid, gripper, cautery, sensor) and the wash station |
| [parts.png](parts.png) | Every part, one tile each, with its size and volume |

They are generated, not drawn: `python cad/build.py out` builds the STL files and checks the geometry, `python cad/render.py out docs/cad`
renders the sheets. The travel is chosen with `VERNIER_TRAVEL="x,y,z"` (see [cad/README.md](../../cad/README.md)). The large-travel image is
a study (cards `mech-estaciones` and `mech-viga`): it builds without interferences and with every camera line of sight clear; the crossbeam
is the printed hollow box with aluminium rods (the large orange beam), and the transmission for that travel is not designed yet.

See also the [connection map](../connection_map.md) and the [block diagram](../wiring_blocks.png).
