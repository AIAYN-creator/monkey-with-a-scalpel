"""Registry of the CAD modules: every file in this package that does not start with an underscore is a module.

A module owns a group of parts, from the geometry to where they stand in the assembly. Adding or changing a module touches
only its own file, so modules can be developed in parallel without editing system.py or build.py.

A module may define any of these (all optional):

    PARTS    {name: (maker, kind)}  parts to make; maker() returns the shape in its own frame, kind is printed or machined
    ALLOWED  set of frozenset({a, b}) pairs of assembly items that overlap by design
    fixed(variant, setback)  -> {name: (shape, kind)}            items that never move
    moving(pose)             -> {name: (shape, kind, group)}     items that move; pose is a layout.Pose, group is x, y, z or tool

kind in the assembly is printed, machined, purchased or dummy. A name used by two modules is an error.
"""
import importlib
import pkgutil


def discover():
    """Every module of the package, in alphabetical order."""
    found = []
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda i: i.name):
        if not info.name.startswith("_"):
            found.append(importlib.import_module(f"{__name__}.{info.name}"))
    return found


def _merge(parts_of, what):
    merged, owner = {}, {}
    for module in discover():
        for name, value in parts_of(module).items():
            if name in merged:
                raise ValueError(f"{what} {name!r} is defined by both {owner[name]} and {module.__name__}")
            merged[name] = value
            owner[name] = module.__name__
    return merged


def catalogue():
    """{name: (maker, kind)} of the parts to make that the modules define."""
    return _merge(lambda m: getattr(m, "PARTS", {}), "part")


def allowed():
    """Pairs that overlap by design, from every module."""
    pairs = set()
    for module in discover():
        pairs |= set(getattr(module, "ALLOWED", ()))
    return pairs


def fixed(variant, setback):
    return _merge(lambda m: m.fixed(variant, setback) if hasattr(m, "fixed") else {}, "fixed item")


def moving(pose):
    return _merge(lambda m: m.moving(pose) if hasattr(m, "moving") else {}, "moving item")
