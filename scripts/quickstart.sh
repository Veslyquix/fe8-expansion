#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/quickstart.sh [--rom /path/to/baserom.gba] [--legacy] [--refresh-agbcc]

Options:
  --rom PATH        Copy the ROM from PATH to baserom.gba if it is missing.
                    Optional: baserom.gba is NOT required to build. It is only
                    used by asmdiff.sh for disassembly comparison.
  --legacy          Build the archival fireemblem8.gba using the legacy
                    compiler toolchain instead of the supported modern
                    release ROM. Installs/reuses the main archival compiler
                    (and, transitively, mgfembp's own archival compiler
                    variant for the FE6 SIO sub-build). Intended for
                    decomp-matching work (see CONTRIBUTING.md); not required
                    for the default path.
  --refresh-agbcc   Force re-clone/rebuild of agbcc even if one exists in tools/agbcc.
                    Implies --legacy, since the archival compiler toolchain
                    is only needed by the archival legacy build.

Default (no --legacy): installs/probes the modern arm-none-eabi GCC
toolchain and the libmGBA playtest backend, then builds and boot-verifies
the supported modern AAPCS release ROM via `make expansion-modern-boot-check
MODERN_CONFIG=release MODERN_ABI=aapcs`. No legacy compiler toolchain of
any kind is installed or invoked on this path.

You can also set FIREEMBLEM8U_ROM to point to the ROM.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
AGBCC_SRC_DIR="${PROJECT_DIR}/.deps/agbcc"
AGBCC_INSTALL_DIR="${PROJECT_DIR}/tools/agbcc"
AGBCC_BIN="${AGBCC_INSTALL_DIR}/bin/agbcc"
BASEROM_PATH="${PROJECT_DIR}/baserom.gba"
FORCE_AGBCC_UPDATE=0
LEGACY_MODE=0
ROM_SOURCE="${FIREEMBLEM8U_ROM:-}"

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --rom)
        if [[ $# -lt 2 ]]; then
          echo "--rom requires a path" >&2
          return 1
        fi
        ROM_SOURCE="$2"
        shift 2
        ;;
      --rom=*)
        ROM_SOURCE="${1#*=}"
        shift
        ;;
      --legacy)
        LEGACY_MODE=1
        shift
        ;;
      --refresh-agbcc)
        FORCE_AGBCC_UPDATE=1
        shift
        ;;
      -h|--help)
        usage
        return 2
        ;;
      *)
        echo "Unknown option: $1" >&2
        usage
        return 1
        ;;
    esac
  done

  if (( FORCE_AGBCC_UPDATE == 1 && LEGACY_MODE == 0 )); then
    echo "[=] Refreshing the archival compiler toolchain implies --legacy (only used by the archival legacy build)"
    LEGACY_MODE=1
  fi
}

# baserom.gba is OPTIONAL. It is only used by asmdiff.sh for disassembly
# comparison, so a missing ROM is a note, not a failure.
ensure_baserom() {
  if [[ -f "${BASEROM_PATH}" ]]; then
    return
  fi

  if [[ -n "${ROM_SOURCE}" ]]; then
    echo "[+] Copying ROM from ${ROM_SOURCE}"
    cp "${ROM_SOURCE}" "${BASEROM_PATH}"
    return
  fi

  cat <<'EOF'
[=] No baserom.gba found -- continuing (it is optional and not needed to build).
    Provide one with --rom /path/to/rom.gba (or FIREEMBLEM8U_ROM=...) only if you
    want to use asmdiff.sh for disassembly comparison.
EOF
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

job_count() {
  local count=""
  if have_cmd nproc; then
    count="$(nproc)"
  elif have_cmd sysctl; then
    count="$(sysctl -n hw.logicalcpu 2>/dev/null || true)"
  fi

  if [[ ! "${count}" =~ ^[1-9][0-9]*$ ]]; then
    count=1
  fi
  printf '%s\n' "${count}"
}

probe_arm_toolchain_headers() {
  have_cmd arm-none-eabi-as || return 1
  have_cmd arm-none-eabi-gcc || return 1

  local header_flags=()
  if [[ -f /usr/include/newlib/stdlib.h ]]; then
    header_flags=(-isystem /usr/include/newlib)
  fi

  printf '#include <stdlib.h>\n#include <stdint.h>\n' |
    arm-none-eabi-gcc "${header_flags[@]}" -E -x c - >/dev/null 2>&1 || return 1
  printf '#include "global.h"\n' |
    arm-none-eabi-gcc "${header_flags[@]}" -std=gnu11 -DMODERN=1 -DNONMATCHING=1 \
      -I"${PROJECT_DIR}/include" -I"${PROJECT_DIR}" -fsyntax-only -x c - \
      >/dev/null 2>&1
}

install_python_modules() {
  if have_cmd pip3; then
    pip3 install --user --upgrade numpy pillow >/dev/null
  fi
}

have_arm_binutils() {
  have_cmd arm-none-eabi-as && have_cmd arm-none-eabi-ld
}

install_deps() {
  local pkg_mgr=""
  if have_cmd apt-get; then
    pkg_mgr="apt"
  elif have_cmd pacman; then
    pkg_mgr="pacman"
  elif have_cmd brew; then
    pkg_mgr="brew"
  else
    echo "[!] No supported package manager detected (apt, pacman, brew)." >&2
    if (( LEGACY_MODE == 1 )); then
      echo "    Install the prerequisites manually: arm-none-eabi binutils, pkg-config, libpng, python3, pip, numpy, pillow." >&2
    else
      echo "    Install the prerequisites manually: arm-none-eabi GCC/binutils/newlib, pkg-config, libpng, python3, pip, numpy, pillow." >&2
    fi
    return
  fi

  # --legacy builds fireemblem8.gba with agbcc (built from source by
  # prepare_agbcc) plus the system arm-none-eabi binutils (as/ld) for
  # assembling and linking. It does not need, and must not require or
  # probe for, the modern arm-none-eabi GCC/newlib toolchain.
  local need_toolchain=0
  local need_binutils=0
  if (( LEGACY_MODE == 1 )); then
    if ! have_arm_binutils; then
      need_binutils=1
    fi
  elif ! probe_arm_toolchain_headers; then
    need_toolchain=1
  fi

  # The libmGBA playtest backend is only needed by the default modern
  # boot-check path; --legacy builds fireemblem8.gba without it.
  local need_playtest_backend=0
  if (( LEGACY_MODE == 0 )); then
    need_playtest_backend=1
  fi

  case "${pkg_mgr}" in
    apt)
      local sudo_cmd=""
      if (( EUID != 0 )); then
        if have_cmd sudo; then
          sudo_cmd="sudo"
        else
          echo "[!] Need root privileges to install packages via apt, but sudo is unavailable." >&2
          echo "    Install the prerequisites manually and rerun the script." >&2
          return 1
        fi
      fi
      echo "[+] Updating apt package index..."
      ${sudo_cmd} apt-get update -y >/dev/null
      local packages=(pkg-config libpng-dev python3-pip python3-numpy python3-pil)
      if (( need_playtest_backend )); then
        packages=("${packages[@]}" libmgba-dev)
      fi
      if (( LEGACY_MODE == 1 )); then
        if (( need_binutils )); then
          packages=(binutils-arm-none-eabi "${packages[@]}")
        fi
      elif (( need_toolchain )); then
        packages=(binutils-arm-none-eabi gcc-arm-none-eabi libnewlib-arm-none-eabi "${packages[@]}")
      fi
      if [[ ${#packages[@]} -gt 0 ]]; then
        echo "[+] Installing packages via apt: ${packages[*]}"
        ${sudo_cmd} apt-get install -y "${packages[@]}" >/dev/null
      fi
      ;;
    pacman)
      local sudo_cmd=""
      if (( EUID != 0 )); then
        if have_cmd sudo; then
          sudo_cmd="sudo"
        else
          echo "[!] Need root privileges to install packages via pacman, but sudo is unavailable." >&2
          echo "    Install the prerequisites manually and rerun the script." >&2
          return 1
        fi
      fi
      local packages=(pkgconf libpng python-pip python-numpy python-pillow)
      if (( need_playtest_backend )); then
        packages=("${packages[@]}" mgba)
      fi
      if (( LEGACY_MODE == 1 )); then
        if (( need_binutils )); then
          packages=(arm-none-eabi-binutils "${packages[@]}")
        fi
      elif (( need_toolchain )); then
        packages=(arm-none-eabi-binutils arm-none-eabi-gcc arm-none-eabi-newlib "${packages[@]}")
      fi
      echo "[+] Installing packages via pacman: ${packages[*]}"
      if ! ${sudo_cmd} pacman -S --needed --noconfirm "${packages[@]}"; then
        echo "[!] pacman install failed; if package databases are stale, run a full" >&2
        echo "    'sudo pacman --sync --refresh --sysupgrade' upgrade, then rerun." >&2
        return 1
      fi
      ;;
    brew)
      local packages=(pkg-config libpng)
      if (( LEGACY_MODE == 1 )); then
        if (( need_binutils )); then
          echo "[+] Installing official Arm GNU toolchain cask (bundled binutils for --legacy)"
          brew install --cask gcc-arm-embedded
        fi
      elif (( need_toolchain )); then
        if brew list --formula arm-none-eabi-gcc >/dev/null 2>&1; then
          echo "[!] Homebrew's arm-none-eabi-gcc formula is installed without target headers." >&2
          echo "    Run 'brew uninstall arm-none-eabi-gcc', then" >&2
          echo "    'brew install --cask gcc-arm-embedded', and rerun this script." >&2
          return 1
        fi
        echo "[+] Installing official Arm GNU toolchain cask (bundled newlib)"
        brew install --cask gcc-arm-embedded
      fi
      echo "[+] Installing packages via Homebrew: ${packages[*]}"
      brew update >/dev/null
      brew install "${packages[@]}"
      if (( need_playtest_backend )); then
        if brew list --formula mgba >/dev/null 2>&1; then
          echo "[=] Homebrew mgba (libmGBA) already installed"
        else
          echo "[+] Installing mgba (libmGBA playtest backend) via Homebrew"
          brew install mgba
        fi
      fi
      echo "[+] Ensuring Python modules (numpy, pillow) via pip3"
      install_python_modules
      ;;
  esac

  hash -r
  if (( LEGACY_MODE == 1 )); then
    if ! have_arm_binutils; then
      echo "[!] arm-none-eabi-as/arm-none-eabi-ld are still unavailable for the --legacy build." >&2
      echo "    Install arm-none-eabi binutils (e.g. binutils-arm-none-eabi) and rerun." >&2
      return 1
    fi
    return
  fi

  if ! probe_arm_toolchain_headers; then
    echo "[!] arm-none-eabi-gcc still cannot parse <stdlib.h> and include/global.h." >&2
    if [[ "${pkg_mgr}" == "brew" ]]; then
      echo "    Remove a headerless formula with 'brew uninstall arm-none-eabi-gcc'," >&2
      echo "    then install 'brew install --cask gcc-arm-embedded'." >&2
    else
      echo "    Install the matching arm-none-eabi newlib headers and rerun." >&2
    fi
    return 1
  fi
}

prepare_agbcc() {
  if [[ -x "${AGBCC_BIN}" && ${FORCE_AGBCC_UPDATE} -eq 0 ]]; then
    echo "[=] Using existing agbcc at ${AGBCC_INSTALL_DIR}"
    return
  fi

  mkdir -p "${PROJECT_DIR}/.deps"
  if [[ ! -d "${AGBCC_SRC_DIR}/.git" ]]; then
    echo "[+] Cloning agbcc into ${AGBCC_SRC_DIR}"
    rm -rf "${AGBCC_SRC_DIR}"
    git clone https://github.com/pret/agbcc.git "${AGBCC_SRC_DIR}"
  fi

  pushd "${AGBCC_SRC_DIR}" >/dev/null
    echo "[+] Updating agbcc source"
    git fetch origin >/dev/null
    git reset --hard origin/master >/dev/null
    echo "[+] Building agbcc"
    ./build.sh
    echo "[+] Installing agbcc into project"
    ./install.sh "${PROJECT_DIR}"
  popd >/dev/null
}

build_project() {
  local jobs
  jobs="$(job_count)"
  pushd "${PROJECT_DIR}" >/dev/null
    echo "[+] Fetching submodules (mgfembp is the FE6 SIO payload source in both build paths)"
    git submodule update --init --recursive
    echo "[+] Building project-specific tools"
    ./build_tools.sh

    if (( LEGACY_MODE == 1 )); then
      echo "[+] Building archival fireemblem8.gba via the legacy compiler toolchain (this can take several minutes)"
      echo "    (first build also fetches/builds mgfembp's own agbcc variant for its FE6 SIO sub-build)"
      # Calls the explicit, clearly-named `legacy` target by name (see
      # Makefile's Main Targets section) instead of relying on any
      # environment/command-line variable to redirect a bare `make`: a
      # plain `make`/`make all` always builds the supported modern AAPCS
      # release lane, unconditionally, with no lane-selection variable of
      # any kind able to change that.
      make legacy -j"${jobs}"
      echo "[✓] Legacy build complete: ${PROJECT_DIR}/fireemblem8.gba"
    else
      echo "[+] Building and boot-verifying the supported modern AAPCS release ROM"
      echo "    (make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs; this can take several minutes)"
      make expansion-modern-toolchain-check
      make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs -j"${jobs}"
      echo "[✓] Modern build complete: ${PROJECT_DIR}/build/expansion-modern/release/aapcs/fireemblem8.gba"
    fi
  popd >/dev/null
}

main() {
  local parse_status=0
  parse_args "$@" || parse_status=$?
  if (( parse_status == 2 )); then
    return 0
  elif (( parse_status != 0 )); then
    return "${parse_status}"
  fi

  ensure_baserom
  install_deps
  if (( LEGACY_MODE == 1 )); then
    prepare_agbcc
  fi
  build_project
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
