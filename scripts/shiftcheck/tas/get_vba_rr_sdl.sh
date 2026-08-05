#!/usr/bin/env bash
# Build the exact VBA-rr svn421 SDL frontend used by the public FE8 VBM.
#
# Usage: get_vba_rr_sdl.sh [work_dir]
#
# The setup is intentionally isolated and non-root. It pins the upstream source
# revision and Ubuntu 24.04 x86-64 SDL compatibility packages by SHA-256.
set -euo pipefail

WORK="${1:-$HOME/.cache/fe8-vba-rr-sdl}"
REVISION="fe4a46bd53d6b4006ab4899d06c5f986fed1defb"
SOURCE="$WORK/src"
DEPS="$WORK/deps"
DOWNLOADS="$WORK/downloads"
LIBDIR="$DEPS/usr/lib/x86_64-linux-gnu"

if [ "$(uname -s)" != "Linux" ] || [ "$(uname -m)" != "x86_64" ]; then
    echo "get_vba_rr_sdl: supported host is Linux x86_64" >&2
    exit 2
fi
for command in git curl dpkg-deb python3 sha256sum g++ make; do
    command -v "$command" >/dev/null || {
        echo "get_vba_rr_sdl: missing required command: $command" >&2
        exit 2
    }
done

mkdir -p "$DOWNLOADS"

download() {
    local name="$1" url="$2" sha="$3"
    local path="$DOWNLOADS/$name"
    if [ ! -f "$path" ]; then
        curl -L --fail --retry 6 --retry-all-errors --connect-timeout 20 \
            --silent --show-error -o "$path" "$url"
    fi
    printf '%s  %s\n' "$sha" "$path" | sha256sum -c -
}

download libsdl1.2-dev.deb \
    "https://archive.ubuntu.com/ubuntu/pool/universe/s/sdl12-compat/libsdl1.2-dev_1.2.68-2_amd64.deb" \
    "42f2799c0f5ac96f314797fdcfe90765849a6ad5389bde5b71d4be74ed448a7d"
download libsdl1.2debian.deb \
    "https://archive.ubuntu.com/ubuntu/pool/universe/s/sdl12-compat/libsdl1.2debian_1.2.68-2_amd64.deb" \
    "ab96fe60369fe364b00668d811e1a55d4b85ea483be7bbecb31ca18a73216540"
download libsdl2.deb \
    "https://archive.ubuntu.com/ubuntu/pool/main/libs/libsdl2/libsdl2-2.0-0_2.30.0%2bdfsg-1build3_amd64.deb" \
    "843864d304b9084b059c8385a2d11dd769534488b6f0091304f362e3b812d7d7"
download libxss1.deb \
    "https://archive.ubuntu.com/ubuntu/pool/main/libx/libxss/libxss1_1.2.3-1build3_amd64.deb" \
    "0ac60a2cc034ccc4bf4e2f846f38110469d7ae43b47e808d67aafc538bc3695e"
download libdecor.deb \
    "https://archive.ubuntu.com/ubuntu/pool/main/libd/libdecor-0/libdecor-0-0_0.2.2-1build2_amd64.deb" \
    "64bf085d16e504e9ed39b91d2a46748fb8881ad7f3603fbacef6c11c04aa7064"

rm -rf "$DEPS"
mkdir -p "$DEPS"
for package in "$DOWNLOADS"/*.deb; do
    dpkg-deb -x "$package" "$DEPS"
done

rm -rf "$SOURCE"
git clone --quiet https://github.com/vba-rerecording/vba-rerecording.git "$SOURCE"
git -C "$SOURCE" checkout --quiet --detach "$REVISION"

python3 - "$SOURCE" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])


def replace(relative, old, new):
    path = root / relative
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"get_vba_rr_sdl: expected source text missing in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace(
    "src/common/Util.cpp",
    "if (setjmp(png_ptr->jmpbuf))",
    "if (setjmp(png_jmpbuf(png_ptr)))",
)
for relative in ("src/sdl/expr.cpp", "src/sdl/expr.y"):
    replace(
        relative,
        "namespace std {  \n#include <stdio.h>\n#include <memory.h>\n"
        "#include <stdlib.h>\n#include <string.h>\n}\n",
        "#include <stdio.h>\n#include <memory.h>\n#include <stdlib.h>\n"
        "#include <string.h>\n",
    )

replace(
    "src/sdl/SDL.cpp",
    '  { "watchmovie", required_argument, 0, \'w\' },\n',
    '  { "watchmovie", required_argument, 0, \'w\' },\n'
    '  { "lua-script", required_argument, 0, \'l\' },\n',
)
replace(
    "src/sdl/SDL.cpp",
    "  ipsname[0] = 0;\n",
    "  ipsname[0] = 0;\n"
    "  std::string luaScriptFile;\n"
    "  bool loadLUAScript = false;\n",
)
replace(
    "src/sdl/SDL.cpp",
    "    case '?':\n      sdlPrintUsage = 1;\n      break;\n",
    "    case '?':\n"
    "      sdlPrintUsage = 1;\n"
    "      break;\n"
    "    case 'l':\n"
    "      if(optarg == NULL) {\n"
    '        fprintf(stderr, "Missing LUA script file name\\n");\n'
    "        exit(-1);\n"
    "      }\n"
    "      luaScriptFile = optarg;\n"
    "      loadLUAScript = true;\n"
    "      break;\n",
)
replace(
    "src/sdl/SDL.cpp",
    "  while(emulating) {\n    if(!paused && active) {\n",
    "  if(loadLUAScript) {\n"
    "    pauseNextFrame = true;\n"
    "  }\n\n"
    "  while(emulating) {\n"
    "    if(loadLUAScript && paused) {\n"
    "      if(!VBALoadLuaCode(luaScriptFile.c_str())) {\n"
    '        fprintf(stderr, "Failed to load and run lua script %s", '
    "luaScriptFile.c_str());\n"
    "      }\n"
    "      loadLUAScript = false;\n"
    "      paused = false;\n"
    "    }\n"
    "    if(!paused && active) {\n",
)
replace(
    "src/sdl/Makefile.in",
    "2xSaImmx.o  elf.o",
    "elf.o      ",
)
PY

find "$SOURCE" -name Makefile.in -exec touch {} +
touch "$SOURCE/aclocal.m4" "$SOURCE/configure"

cd "$SOURCE"
CPPFLAGS="-I$DEPS/usr/include/SDL" \
LDFLAGS="-L$LIBDIR -Wl,-rpath,$LIBDIR" \
SDL_CONFIG="$DEPS/usr/bin/sdl-config" \
CFLAGS="-O2 -fcommon -DC_CORE" \
CXXFLAGS="-O2 -fcommon -std=gnu++98 -DC_CORE" \
sh ./configure --enable-sdl --disable-gtk --enable-c-core --without-mmx \
    --disable-sdltest >/dev/null

python3 - "$SOURCE/src/sdl/Makefile" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = "2xSaImmx.o  elf.o"
if old in text:
    path.write_text(text.replace(old, "elf.o      ", 1), encoding="utf-8")
PY

CPPFLAGS="-I$DEPS/usr/include/SDL" \
LDFLAGS="-L$LIBDIR -Wl,-rpath,$LIBDIR" \
LIBRARY_PATH="$LIBDIR" \
SDL_CONFIG="$DEPS/usr/bin/sdl-config" \
make -j1 CFLAGS="-O2 -fcommon -DC_CORE" \
    CXXFLAGS="-O2 -fcommon -std=gnu++98 -DC_CORE" >/dev/null

test -x "$SOURCE/src/VisualBoyAdvance"
printf '%s\n' "$REVISION" > "$WORK/revision.txt"
echo "VBA_RR_EXE=$SOURCE/src/VisualBoyAdvance"
echo "VBA_RR_LIBDIR=$LIBDIR"
