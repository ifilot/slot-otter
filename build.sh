#!/usr/bin/env bash
# Used to build SLOTOTTER.EXE in Github Actions
set -e

# Folders relative to this script
BUILDENV_DIR="$(pwd)/buildenv"
SRC_DIR="$(pwd)/src"

# DOSBox config
DOSBOX_CONF="dosbox.conf"
DOSBOX_LOG="dosbox_build.log"

# Clean previous log
rm -f "$DOSBOX_LOG"

# This file runs inside DOSBox
cat > buildenv/BUILD.BAT <<'EOF'
@echo off
echo === Setting up PATH ===
SET PATH=C:\TASM;C:\TC;%PATH%

echo === Mounting drives ===
C:
echo === PATH is now %PATH% ===

echo === Switching to D: and running MAKE ===
D:
make

echo === Build complete ===
exit
EOF

# run DosBox
dosbox -noconsole -exit \
  -c "mount c \"$BUILDENV_DIR\"" \
  -c "mount d \"$SRC_DIR\"" \
  -c "c:" \
  -c "call c:\\build.bat" \
  > "$DOSBOX_LOG" 2>&1

echo "=== DOS build finished ==="
echo "Check '$DOSBOX_LOG' for DOSBox output."