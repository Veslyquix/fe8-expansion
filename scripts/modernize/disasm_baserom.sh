#!/usr/bin/env bash
# Disassemble a range of the vanilla FE8U ROM (baserom.gba) at a given ROM
# offset, for cross-referencing old FEBuilder-style .event ROM patches (which
# only give raw hex addresses) against already-decompiled C in this project.
# See reference/fe8u_symbols.txt for the accompanying address/symbol table.
#
# Usage: disasm_baserom.sh <rom_offset_hex> [byte_count]
#   rom_offset_hex -- offset into the ROM file, hex, WITHOUT the 0x08000000
#                     base and WITHOUT a leading "0x" (e.g. 8A126, not
#                     0x0808A126). This matches the address style used in
#                     FEBuilder-style .event files' ORG statements.
#   byte_count      -- how many bytes to disassemble (default 128).
#
# Requires baserom.gba at the repo root (see docs/quickstart.md -- it is
# optional for building, only used here and by asmdiff.sh) and
# arm-none-eabi-objdump on PATH.
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <rom_offset_hex> [byte_count]" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ROM="${REPO_ROOT}/baserom.gba"

if [[ ! -f "${ROM}" ]]; then
    echo "error: ${ROM} not found (baserom.gba is optional for building; see docs/quickstart.md for how to provide one)" >&2
    exit 1
fi

if ! command -v arm-none-eabi-objdump >/dev/null 2>&1; then
    echo "error: arm-none-eabi-objdump not found on PATH" >&2
    exit 1
fi

OFFSET_HEX="$1"
LEN="${2:-128}"
FILE_OFFSET=$(( 0x${OFFSET_HEX} & ~1 ))
BASE_ADDR=$(( 0x08000000 + FILE_OFFSET ))

TMP="$(mktemp)"
trap 'rm -f "${TMP}"' EXIT

dd if="${ROM}" bs=1 skip="${FILE_OFFSET}" count="${LEN}" of="${TMP}" 2>/dev/null

printf -v BASE_ADDR_HEX '0x%08X' "${BASE_ADDR}"
arm-none-eabi-objdump -D -b binary -m arm --disassembler-options=force-thumb -EL \
    --adjust-vma="${BASE_ADDR_HEX}" "${TMP}"
