#!/usr/bin/env bash
# One standalone build for the driver and its public hardware tester.
set -euo pipefail
driver_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
toolchain_dir="${TOOLCHAIN_DIR:-$driver_dir/../buildenv}"
dosbox_bin="${DOSBOX_BIN:-dosbox}"
build_dir="$(mktemp -d /tmp/otter-driver-build.XXXXXX)"
output_dir="${1:-$driver_dir/build}"
cp "$driver_dir"/*.C "$driver_dir"/*.H "$driver_dir"/*.ASM "$driver_dir/MAKEFILE" "$build_dir/"
python3 - "$build_dir" <<'DOS_TEXT'
import pathlib,sys
for p in pathlib.Path(sys.argv[1]).iterdir():
    b=p.read_bytes().replace(b'\r\n',b'\n').rstrip(b'\x1a')
    p.write_bytes(b.replace(b'\n',b'\r\n'))
DOS_TEXT
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy timeout 90 "$dosbox_bin" -noconsole -exit \
  -c "mount c \"$toolchain_dir\"" -c "mount d \"$build_dir\"" \
  -c 'set PATH=C:\TC;C:\TASM' -c 'd:' -c 'make BOOT.OBJ CRT.OBJ RWDIR.OBJ RWFS.OBJ FAT32.OBJ SDRW.OBJ FASTIO.OBJ ENTRY.OBJ > CORE.TXT' \
  -c 'tcc -ms -O -d -Z -S -zCINITTAIL INSTALL.C > INIT.TXT' -c exit \
  > "$build_dir/compiler.log" 2>&1
cat "$build_dir/CORE.TXT" "$build_dir/INIT.TXT"
if rg -qi '(^Error [^ ]+ [0-9]+|^Error:|^Fatal:|^Warning [^ ]+ [0-9]+|^Warning:|^Warning messages:[[:space:]]*[1-9]|Undefined symbol)' "$build_dir/CORE.TXT" "$build_dir/INIT.TXT"; then
  echo "Compilation failed: $build_dir" >&2; exit 1
fi
python3 "$driver_dir/installer_segments.py" "$build_dir/INSTALL.ASM"
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy timeout 90 "$dosbox_bin" -noconsole -exit \
  -c "mount c \"$toolchain_dir\"" -c "mount d \"$build_dir\"" \
  -c 'set PATH=C:\TC;C:\TASM' -c 'd:' -c 'make > LINK.TXT' -c exit \
  > "$build_dir/linker.log" 2>&1
cat "$build_dir/LINK.TXT"
if [[ ! -s "$build_dir/OTTERSD.EXE" ]] || rg -qi '(^Error [^ ]+ [0-9]+|^Error:|^Fatal:|^Warning [^ ]+ [0-9]+|^Warning:|^Warning messages:[[:space:]]*[1-9]|Undefined symbol)' "$build_dir/LINK.TXT"; then
  echo "Assembly/link failed: $build_dir" >&2; exit 1
fi
python3 "$driver_dir/tests/layout.py" "$build_dir/OTTERSD.MAP"
mkdir -p "$output_dir"
cp "$build_dir/OTTERSD.EXE" "$build_dir/OTTERSD.MAP" "$output_dir/"
echo "Built $output_dir/OTTERSD.EXE; compiler files: $build_dir"
python3 "$driver_dir/build_test.py" --output "$output_dir"
