#!/usr/bin/env bash
# Standalone writable build. Read-only driver/release binaries stay separate.
set -euo pipefail
driver_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
toolchain_dir="${TOOLCHAIN_DIR:-$driver_dir/../buildenv}"
dosbox_bin="${DOSBOX_BIN:-dosbox}"
build_dir="$(mktemp -d /tmp/otterwr-build.XXXXXX)"
output_dir="${1:-$driver_dir}"
cp "$driver_dir"/*.C "$driver_dir"/*.H "$driver_dir"/*.ASM "$driver_dir/MAKERW" "$build_dir/"
# Turbo C/TASM consume DOS text. Normalize line endings and old Ctrl-Z EOFs
# in private copies; DOSBox's built-in DOS hosts compilation only. Runtime
# validation separately boots a genuine MS-DOS kernel on private images.
python3 - "$build_dir" <<'PY'
import pathlib, sys
for path in pathlib.Path(sys.argv[1]).iterdir():
    data = path.read_bytes().replace(b'\r\n', b'\n').rstrip(b'\x1a')
    path.write_bytes(data.replace(b'\n', b'\r\n'))
PY
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy "$dosbox_bin" -noconsole -exit \
  -c "mount c \"$toolchain_dir\"" -c "mount d \"$build_dir\"" \
  -c 'set PATH=C:\TC;C:\TASM' -c 'd:' -c 'make -fMAKERW > BUILD.TXT' -c exit \
  > "$build_dir/DOSBOX.LOG" 2>&1
cat "$build_dir/BUILD.TXT"
if [[ ! -s "$build_dir/OTTERWR.EXE" ]] || rg -qi '(^Error [^ ]+ [0-9]+|^Error:|^Fatal:|Undefined symbol)' "$build_dir/BUILD.TXT"; then
  echo "Build failed; logs retained in $build_dir" >&2
  exit 1
fi
python3 "$driver_dir/tests/layout.py" "$build_dir/OTTERWR.MAP"
mkdir -p "$output_dir"
cp "$build_dir/OTTERWR.EXE" "$build_dir/OTTERWR.MAP" "$output_dir/"
echo "Built $output_dir/OTTERWR.EXE; build files: $build_dir"
