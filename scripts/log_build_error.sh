#!/usr/bin/env bash
# Runs a command, streaming its output normally while recording it immediately
# in errorlog.txt at the repo root. The log is reset at the start of each run,
# so it always describes the current build rather than a previous failure.
#
# Usage: log_build_error.sh <label> -- <command...>
# Wired into the Makefile's/modern.mk's top-level entry points (all,
# legacy, sync-win) so build output is captured even when make is running many
# jobs in parallel, without needing to redirect make's own output yourself.
set -u

label=$1
shift
if [ "${1:-}" = "--" ]; then
    shift
fi

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
errorlog="$repo_root/errorlog.txt"

# Create a fresh log before the build starts, removing stale errors as soon as
# a new build is launched.
: > "$errorlog"
printf '=== %s build started: %s ===\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" "$label" | tee -a "$errorlog"

set -o pipefail
"$@" 2>&1 | tee -a "$errorlog"
status=$?

if [ "$status" -ne 0 ]; then
    {
        printf '=== %s build failed (exit %s) ===\n' \
            "$(date '+%Y-%m-%d %H:%M:%S')" "$label" "$status"
        printf '\n'
    } | tee -a "$errorlog" >&2
    printf 'Build failed -- see %s\n' "$errorlog" >&2
else
    printf '=== %s build succeeded ===\n' \
        "$(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$errorlog"
fi

exit "$status"
