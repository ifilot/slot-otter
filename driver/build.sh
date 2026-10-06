#!/usr/bin/env bash
# Standalone DOS build; TOOLCHAIN_DIR may point to any Turbo C 2/TASM 2 install.
set -euo pipefail
driver_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
toolchain_dir="${TOOLCHAIN_DIR:-$driver_dir/../buildenv}"
dosbox_bin="${DOSBOX_BIN:-dosbox}"
build_dir="$(mktemp -d /tmp/otterfs-build.XXXXXX)"
output_dir="${1:-$driver_dir}"
cp "$driver_dir"/*.C "$driver_dir"/*.H "$driver_dir"/*.ASM "$driver_dir/MAKEFILE" "$build_dir/"
python3 - "$build_dir" <<'PY'
import pathlib, sys
for path in pathlib.Path(sys.argv[1]).iterdir():
    data = path.read_bytes().replace(b'\r\n', b'\n').rstrip(b'\x1a')
    path.write_bytes(data.replace(b'\n', b'\r\n'))
PY
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy "$dosbox_bin" -noconsole -exit \
  -c "mount c \"$toolchain_dir\"" -c "mount d \"$build_dir\"" \
  -c 'set PATH=C:\TC;C:\TASM' -c 'd:' -c 'make > BUILD.TXT' -c exit \
  > "$build_dir/DOSBOX.LOG" 2>&1
cat "$build_dir/BUILD.TXT"
if [[ ! -s "$build_dir/OTTERFS.EXE" ]]; then
  echo "Build failed; logs retained in $build_dir" >&2
  exit 1
fi
python3 "$driver_dir/tests/layout.py" "$build_dir/OTTERFS.MAP"
mkdir -p "$output_dir"
cp "$build_dir/OTTERFS.EXE" "$build_dir/OTTERFS.MAP" "$output_dir/"
echo "Built $output_dir/OTTERFS.EXE; build files: $build_dir"
