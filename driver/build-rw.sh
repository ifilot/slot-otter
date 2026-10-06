#!/usr/bin/env bash
# Compatibility entry point; build.sh is the sole canonical driver build.
set -euo pipefail
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/build.sh" "$@"
