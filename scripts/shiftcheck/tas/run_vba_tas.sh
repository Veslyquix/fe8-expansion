#!/usr/bin/env bash
# Replay the public Sacred Stones VBM with exact-revision VBA-rr SDL.
#
# Usage: run_vba_tas.sh <rom.gba> <movie.vbm> <tag> [frames] [checkpoints] [timeout_s]
#
# Environment:
#   VBA_RR_ROOT    setup root from get_vba_rr_sdl.sh
#   VBA_RR_EXE     native VisualBoyAdvance override
#   VBA_RR_LIBDIR  local SDL runtime library directory override
#   WORK           output/staging directory (default build/shiftcheck/tas-vba)
set -euo pipefail

ROM="$(realpath "$1")"
MOVIE="$(realpath "$2")"
TAG="$3"
FRAMES="${4:-}"
CHECKPOINTS="${5:-40}"
TIMEOUT_SECONDS="${6:-7200}"
VBA_RR_THROTTLE="${VBA_RR_THROTTLE:-400}"

VBA_RR_ROOT="${VBA_RR_ROOT:-$HOME/.cache/fe8-vba-rr-sdl}"
VBA_RR_EXE="${VBA_RR_EXE:-$VBA_RR_ROOT/src/src/VisualBoyAdvance}"
VBA_RR_LIBDIR="${VBA_RR_LIBDIR:-$VBA_RR_ROOT/deps/usr/lib/x86_64-linux-gnu}"
WORK="${WORK:-build/shiftcheck/tas-vba}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$TAG" in
    *[!A-Za-z0-9_.-]* | "") echo "run_vba_tas: invalid tag: $TAG" >&2; exit 2 ;;
esac

if [ ! -x "$VBA_RR_EXE" ]; then
    echo "run_vba_tas: VBA-rr executable not found: $VBA_RR_EXE" >&2
    echo "Run scripts/shiftcheck/tas/get_vba_rr_sdl.sh first." >&2
    exit 2
fi
if [ ! -d "$VBA_RR_LIBDIR" ]; then
    echo "run_vba_tas: VBA-rr SDL runtime directory not found: $VBA_RR_LIBDIR" >&2
    exit 2
fi
if [ ! -f "$ROM" ] || [ ! -f "$MOVIE" ]; then
    echo "run_vba_tas: ROM or movie not found" >&2
    exit 2
fi
if [ "$(dd if="$MOVIE" bs=4 count=1 status=none)" != $'VBM\032' ]; then
    echo "run_vba_tas: movie is not an extracted VBM file: $MOVIE" >&2
    exit 2
fi

if [ -z "$FRAMES" ]; then
    FRAMES="$(
        python3 - "$MOVIE" <<'PY'
import pathlib
import sys

data = pathlib.Path(sys.argv[1]).read_bytes()
if len(data) < 16 or data[:4] != b"VBM\x1a":
    raise SystemExit("invalid VBM")
print(int.from_bytes(data[12:16], "little"))
PY
    )"
fi
if [ "$FRAMES" -le 0 ]; then
    echo "run_vba_tas: frame count must be positive" >&2
    exit 2
fi
case "$VBA_RR_THROTTLE" in
    25 | 50 | 100 | 200 | 400) ;;
    *)
        echo "run_vba_tas: VBA_RR_THROTTLE must be 25, 50, 100, 200, or 400" >&2
        exit 2
        ;;
esac

RUN_DIR="$WORK/runs/$TAG"
OUT_DIR="$WORK/out"
CAPTURE_DIR="$OUT_DIR/$TAG"
HOME_DIR="$RUN_DIR/home"
CONFIG="$RUN_DIR/config.txt"
OUTPUT="$OUT_DIR/$TAG.json"
LOG="$OUT_DIR/$TAG.log"
rm -rf "$RUN_DIR" "$CAPTURE_DIR"
mkdir -p "$RUN_DIR" "$OUT_DIR" "$CAPTURE_DIR" "$HOME_DIR"
find "$CAPTURE_DIR" -mindepth 1 -maxdepth 1 -type f -delete
rm -f "$OUTPUT" "$OUTPUT.tmp" "$LOG"
cp "$ROM" "$RUN_DIR/game.gba"
cp "$MOVIE" "$RUN_DIR/movie-source.vbm"
python3 "$SCRIPT_DIR/prepare_vba_movie.py" \
    "$RUN_DIR/movie-source.vbm" "$RUN_DIR/movie.vbm" >> "$LOG"
printf '%s\n%s\n%s\n%s\n' \
    "$(realpath "$CAPTURE_DIR")" "$TAG" "$FRAMES" "$CHECKPOINTS" > "$CONFIG"

VBA_RR_EXE="$(realpath "$VBA_RR_EXE")"
VBA_RR_LIBDIR="$(realpath "$VBA_RR_LIBDIR")"
HOME_DIR="$(realpath "$HOME_DIR")"
CONFIG="$(realpath "$CONFIG")"

echo "run_vba_tas: tag=$TAG frames=$FRAMES checkpoints=$CHECKPOINTS"
echo "run_vba_tas: rom_sha1=$(sha1sum "$ROM" | cut -d' ' -f1)"

(
    cd "$RUN_DIR"
    HOME="$HOME_DIR" \
    VBA_TAS_CONFIG="$CONFIG" \
    SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-dummy}" \
    SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-dummy}" \
    LD_LIBRARY_PATH="$VBA_RR_LIBDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    timeout --foreground "$TIMEOUT_SECONDS" "$VBA_RR_EXE" \
        --watchmovie="$(realpath movie.vbm)" \
        --lua-script="$SCRIPT_DIR/vba_fingerprint.lua" \
        --throttle="$VBA_RR_THROTTLE" \
        --no-auto-frameskip \
        --no-pause-when-inactive \
        --no-mmx \
        --frameskip=0 \
        "$(realpath game.gba)"
) >> "$LOG" 2>&1

python3 "$SCRIPT_DIR/collect_vba_fingerprint.py" \
    --out-dir "$CAPTURE_DIR" \
    --tag "$TAG" \
    --expected-frames "$FRAMES" \
    --checkpoint-count "$CHECKPOINTS" \
    --rom "$RUN_DIR/game.gba" \
    --output "$OUTPUT"
