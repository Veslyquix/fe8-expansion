#!/usr/bin/env bash
# Runs a command, streaming its output normally, and -- only if it fails --
# also appends that output to errorlog.txt at the repo root, timestamped
# and labeled. A successful run never touches errorlog.txt.
#
# Usage: log_build_error.sh <label> -- <command...>
# Wired into the Makefile's/modern.mk's top-level entry points (all,
# legacy, sync-win) so a failed `make` always leaves a record, without
# needing to redirect make's own output yourself.
set -u

label=$1
shift
if [ "${1:-}" = "--" ]; then
    shift
fi

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
errorlog="$repo_root/errorlog.txt"
logfile=$(mktemp)
trap 'rm -f "$logfile"' EXIT

set -o pipefail
"$@" 2>&1 | tee "$logfile"
status=$?

if [ "$status" -ne 0 ]; then
    {
        printf '=== %s build failed: %s (exit %s) ===\n' \
            "$(date '+%Y-%m-%d %H:%M:%S')" "$label" "$status"
        cat "$logfile"
        printf '\n'
    } >> "$errorlog"
    printf 'Build failed -- see %s\n' "$errorlog" >&2
fi

exit "$status"
