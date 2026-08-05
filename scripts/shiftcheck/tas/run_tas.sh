#!/usr/bin/env bash
# Drive GBAHawk (Windows, from WSL2) to replay a movie on a ROM and capture
# checkpoint screenshots via fingerprint.lua. Sequential use (shared out/cfg.txt).
# Each tag gets an isolated GBAHawk config to avoid config.ini/audio-device
# contention with stale or concurrently running emulator instances.
#
# Usage: run_tas.sh <rom_win> <movie_win> <tag> [ncheckpoints] [maxframe] [timeout_s]
#   rom_win/movie_win : Windows-style paths (C:\...), readable by GBAHawk.exe
#   tag               : output prefix (e.g. matching, shifted)
#   ncheckpoints      : evenly-spaced screenshot count (default 40)
#   maxframe          : stop early for testing (0 = full movie; default 0)
#
# Env: GBAHAWK_EXE (WSL path to GBAHawk.exe), WORK (WSL path to C:\gbahawk_test),
#      LUA_WIN (Windows path to fingerprint.lua), CONFIG_WIN/CONFIG_WSL
#      (optional matching Windows/WSL paths for an explicit GBAHawk config).
set -euo pipefail

ROM="$1"; MOVIE="$2"; TAG="$3"
NCP="${4:-40}"; MAXF="${5:-0}"; TMO="${6:-7200}"

WORK="${WORK:-/mnt/c/gbahawk_test}"
GBAHAWK_EXE="${GBAHAWK_EXE:-$WORK/GBAHawk_2.1.1/GBAHawk v2.1.1/GBAHawk.exe}"
LUA_WIN="${LUA_WIN:-C:\\gbahawk_test\\fingerprint.lua}"
CONFIG_WIN="${CONFIG_WIN:-C:\\gbahawk_test\\config-${TAG}.ini}"
CONFIG_WSL="${CONFIG_WSL:-$WORK/config-${TAG}.ini}"

mkdir -p "$WORK/out"
if [[ ! -f "$CONFIG_WSL" ]]; then
    printf '{\n  "LastWrittenFrom": "2.1.1",\n  "SoundOutputMethod": 3,\n  "SoundEnabled": false\n}\n' \
        > "$CONFIG_WSL"
fi
printf '%s\n%s\n%s\n' "$TAG" "$NCP" "$MAXF" > "$WORK/out/cfg.txt"
rm -f "$WORK/out/${TAG}_"*.png "$WORK/out/${TAG}_manifest.txt" "$WORK/out/${TAG}_done.txt"

echo "run_tas: tag=$TAG ncp=$NCP maxframe=$MAXF rom=$ROM"
cd "$(dirname "$GBAHAWK_EXE")"
timeout "$TMO" ./"$(basename "$GBAHAWK_EXE")" "$ROM" \
    --movie="$MOVIE" --lua="$LUA_WIN" --config="$CONFIG_WIN"
echo "run_tas: $TAG done -> $(cat "$WORK/out/${TAG}_done.txt" 2>/dev/null)"
