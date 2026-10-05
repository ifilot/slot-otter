"""Install the device into an explicitly supplied 86Box source checkout.

Only IBM PC/XT machine initializers are changed. No BIOS/DOS ROMs are supplied.
"""
import argparse
import pathlib
import re
import shutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("checkout", type=pathlib.Path)
args = parser.parse_args()
root = args.checkout.resolve()
here = pathlib.Path(__file__).resolve().parent
machine = root / "src/machine/m_xt.c"
cmake = root / "src/device/CMakeLists.txt"
text = machine.read_text()
build = cmake.read_text()
declaration = "extern const device_t slot_otter_device; /* Slot-otter integration */\n"
functions = ("machine_ibmpc_init", "machine_ibmpc82_init", "machine_ibmxt_init")
changes = 0
for name in functions:
    match = re.search(r"\b" + name + r"\(const machine_t \*model\)\s*\{", text)
    if not match:
        if name == "machine_ibmpc82_init":
            continue
        raise SystemExit(f"Unsupported 86Box source: {name} not found")
    start = match.end()
    end = text.find("\n}\n", start)
    body = text[start:end]
    hook = "    device_add(&slot_otter_device); /* Slot-otter integration */\n"
    if "device_add(&slot_otter_device)" not in body:
        anchor = "    machine_xt_common_init(model, 0);\n"
        if anchor not in body:
            raise SystemExit(f"Unsupported machine initializer: {name}")
        body = body.replace(anchor, anchor + hook, 1)
        text = text[:start] + body + text[end:]
        changes += 1
if declaration not in text:
    anchor = '#include <86box/device.h>\n'
    if anchor not in text:
        raise SystemExit("Cannot find 86Box device header")
    text = text.replace(anchor, anchor + declaration, 1)
if "slot_otter.c" not in build:
    anchor = "add_library(dev OBJECT\n"
    if anchor not in build:
        raise SystemExit("Unsupported 86Box device CMake file")
    build = build.replace(anchor, anchor + "    slot_otter.c\n    slot_model.c\n", 1)
# Validate all anchors before modifying the checkout.
for source in (here / "slot_otter.c", here.parent / "slot_model.c", here.parent / "slot_model.h"):
    shutil.copy2(source, root / "src/device" / source.name)
machine.write_text(text)
cmake.write_text(build)
print(f"Installed Slot-otter into {root}; added {changes} machine hooks.")
