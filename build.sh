#!/usr/bin/env bash
# Used to build OTTERNAV.EXE in Github Actions
set -e

# Folders relative to this script
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BUILDENV_DIR="$SCRIPT_DIR/buildenv"
SRC_DIR="$SCRIPT_DIR/src"
TARGET_EXE="$SRC_DIR/OTTERNAV.EXE"

# DOSBox config
DOSBOX_LOG="$SCRIPT_DIR/dosbox_build.log"

# Clean previous log
rm -f "$DOSBOX_LOG"
rm -f "$TARGET_EXE"

# This file runs inside DOSBox
cat > "$BUILDENV_DIR/BUILD.BAT" <<'EOF'
@echo off
echo === Setting up PATH ===
SET PATH=C:\TASM;C:\TC;%PATH%

echo === Mounting drives ===
C:
echo === PATH is now %PATH% ===

echo === Switching to D: and running MAKE ===
D:
make
exit
EOF

# run DosBox
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy dosbox -noconsole -exit \
  -c "mount c \"$BUILDENV_DIR\"" \
  -c "mount d \"$SRC_DIR\"" \
  -c "c:" \
  -c "call c:\\build.bat" \
  > "$DOSBOX_LOG" 2>&1

if [[ ! -s "$TARGET_EXE" ]]; then
  echo "=== DOS build failed ===" >&2
  echo "Expected build output was not created: $TARGET_EXE" >&2
  echo "Check '$DOSBOX_LOG' for DOSBox output." >&2
  exit 1
fi

echo "=== DOS build finished ==="
echo "Created '$TARGET_EXE' ($(stat -c '%s bytes' "$TARGET_EXE"))."
echo "Check '$DOSBOX_LOG' for DOSBox output."
