# Full-game TAS shiftability validation (GBAHawk)

The deepest shiftability check: replay a **full-game TAS to the ending** on both the
matching ROM and a shifted ROM, and confirm they render identically. This exercises
*every* screen the run visits — battles, the world map, chapter transitions, the
class-reel screen where `gOpinfo_1` is used, the ending — far beyond what the mGBA
boot/title/menu oracle (`../run_dynamic.py`) reaches.

A TAS is a fixed per-frame input log recorded against one ROM. Our build is
byte-identical to the original, so the TAS syncs on it. Feeding the **same inputs**
to a correctly-shifted ROM must produce the **same frames**; a hardcoded pointer
that didn't relocate shows up as a framebuffer divergence (render bug) or a
desync/crash (the run stops matching / never reaches the ending). RAM is *not* a
valid oracle — it holds relocated pointers (= shifted addresses); only the
**framebuffer** is.

## Pieces

| File | Role |
| --- | --- |
| `get_gbahawk.sh` | Download portable GBAHawk v2.1.1 and verify/stage a user-supplied local GBA BIOS. |
| `repack_movie.py` | Copy the `.gbmv` (a BK2 zip) and rewrite `Header.txt`'s `SHA1` to the shifted ROM's, so GBAHawk plays the same inputs on it with no hash-mismatch dialog. |
| `fingerprint.lua` | GBAHawk Lua: replay the loaded movie headless (`invisibleemulation`), screenshot the framebuffer at ~40 evenly-spaced checkpoints + the final frame, write a manifest, `client.exit()`. |
| `run_tas.sh` | Drive `GBAHawk.exe` from WSL2 for one (rom, movie, tag). |
| `compare.py` | Hash the matching vs shifted checkpoint PNGs; report identical / first divergent checkpoint and whether both reached the movie end. |
| `get_vba_rr_sdl.sh` | Build exact source revision `fe4a46bd` (svn421) with a native SDL/C-core frontend and pinned non-root runtime dependencies. |
| `vba_fingerprint.lua` | Advance the public VBM and save raw GD framebuffer snapshots at evenly spaced checkpoints plus the endpoint. |
| `prepare_vba_movie.py` | Append one duplicated guard input frame so svn421 exits cleanly after capturing the original movie endpoint. |
| `collect_vba_fingerprint.py` | Hash GD snapshots, verify the manifest/end marker, and emit deterministic JSON with ROM provenance. |
| `run_vba_tas.sh` | Stage an isolated ROM/movie run and drive native VBA-rr SDL with dummy audio/video drivers. |
| `compare_vba.py` | Compare vanilla vs modern JSON fingerprints and require both runs to reach the public movie endpoint. |

## How to run

```bash
# 1. emulator + legally obtained local BIOS (sha1 300c20df...):
scripts/shiftcheck/tas/get_gbahawk.sh \
    v2.1.1 /mnt/c/gbahawk_test /path/to/gba_bios.bin
# 2. public 254,468-frame GBAHawk resync:
curl -L --fail \
    -o /mnt/c/gbahawk_test/vykan12-v2-fesacredstones.gbmv \
    'https://raw.githubusercontent.com/alyosha-tas/GBA_replay_files/main/gbmv%20files/vykan12-v2-fesacredstones.gbmv'
echo 'fd43e9fd3e10e0525b063433ef1c080d604d81f217f0a625e198165f922e93dd  /mnt/c/gbahawk_test/vykan12-v2-fesacredstones.gbmv' \
    | sha256sum -c -
# 3. movie + matching ROM into the C:\ working dir; build + stage the shifted ROM
#    (reuse diff_shift.build_shifted) and repack the movie for it:
python3 scripts/shiftcheck/tas/repack_movie.py <movie.gbmv> <shifted.gba> <shifted.gbmv>
# 4. replay both, then compare:
python3 scripts/shiftcheck/tas/compare.py /mnt/c/gbahawk_test/out matching shifted
```

## VBA-rr diagnostic lane

The original TASVideos VBM can also be replayed with exact-revision VBA-rr SDL.
This is useful for short compiler-timing diagnostics and does not require a BIOS,
but it is not a substitute for the GBAHawk resync above: VBA's optional prefetch
hack is compiler-cycle-sensitive, so a non-byte-identical modern ROM can desync
even when gameplay remains functional.

External prerequisites are intentionally untracked:

- Publication movie: <https://tasvideos.org/1843M> (`vykan12-v2-fesacredstones.vbm`,
  247,872 frames). The download response is a zip containing the VBM.
- Exact emulator source revision `fe4a46bd53d6b4006ab4899d06c5f986fed1defb`
  from <https://github.com/vba-rerecording/vba-rerecording>. The setup script
  applies only host-compiler/CLI glue (GNU++98 mode, current libpng API, C-core
  SDL stretcher, and the later upstream Lua CLI hook).
- An exact vanilla control ROM (`sha1 c25b145e37456171ada4b0d440bf88a19f4d509f`),
  supplied locally or built from the upstream decompilation.
- Python 3. The movie does not request a GBA BIOS.

On Ubuntu 24.04 x86-64 (including WSL2):

```bash
scripts/shiftcheck/tas/get_vba_rr_sdl.sh
make expansion-modern-rom MODERN_CONFIG=release MODERN_ABI=aapcs

scripts/shiftcheck/tas/run_vba_tas.sh \
    /path/to/vanilla/fireemblem8.gba \
    /path/to/vykan12-v2-fesacredstones.vbm vanilla
scripts/shiftcheck/tas/run_vba_tas.sh \
    build/expansion-modern/release/aapcs/fireemblem8.gba \
    /path/to/vykan12-v2-fesacredstones.vbm modern
python3 scripts/shiftcheck/tas/compare_vba.py \
    --policy endpoint \
    build/shiftcheck/tas-vba/out/vanilla.json \
    build/shiftcheck/tas-vba/out/modern.json
```

The default `exact` policy compares every captured diagnostic checkpoint.
`--policy endpoint` only requires both runs and their final frame to match. A short
calibration run can pass an explicit fourth argument, for example `3000`.

## Confirmed setup (this run)

- TAS: `vykan12-v2-fesacredstones.gbmv` (254,468 frames, ~71 min). Its `Header.txt`
  `SHA1 = C25B145E…` — **exactly our build**, so the matching ROM is recognized.
- Requires the real GBA BIOS (`GBA_Firmware_Bios 300C20DF…`); GBAHawk auto-resolves
  it from `Firmware/` (`Active Firmwares: GBA+Bios : 300C20DF…`).
- Use GBAHawk **v2.1.1** (the movie's `emuVersion`); the host's old v2.3.2 risked a
  core-version desync.
- Do not substitute an open-source replacement BIOS for the authoritative run.
  Compatibility is insufficient here: a full vanilla replay with the
  MIT-licensed Cult-of-GBA BIOS (commit `a30e9a96`) advanced through all
  254,468 movie frames but desynced to an early world-map state instead of the
  ending. GBAHawk executes BIOS code cycle-by-cycle, so the verified Nintendo
  BIOS timing is part of this movie's oracle.
- Shift: `+0x40000` (reuses the Layer-2 shifted-ROM build).
- `invisibleemulation` keeps `client.screenshot()` byte-identical (verified) — frame
  3000 hashed the same with and without it.

## Result

Authoritative completion is currently blocked on a locally supplied Nintendo
GBA BIOS with SHA-1 `300c20df6731a33952ded8c436f7f186d25d3492`.
The final staged ROM/movie pair targets modern release SHA-1
`96a9317a3f0cdfba6255df0f8421d47839859075`. The legal replacement-BIOS
control described below is not accepted because vanilla itself did not reach
the ending.

## Notes / gotchas

- `.gbmv` = BizHawk BK2 zip (`Header.txt` / `Input Log.txt` / `SyncSettings.json`).
- Files must live under a `C:\` working dir (`/mnt/c/...`); the Windows `GBAHawk.exe`
  can't conveniently read the WSL filesystem. Use Windows-style path args.
- GBAHawk's accurate core runs ~80 fps; `invisibleemulation` only saves ~10%, so the
  cost is the ~254k frames. Two parallel instances (separate extracted dirs to avoid
  `config.ini` clashes) halve wall-clock.
- This is intentionally *not* wired into `make`/CI: it needs the copyrighted BIOS,
  the Windows emulator, the external movie, and ~1 hour. It is a manual deep-proof on
  top of the static layers + the mGBA runtime layer.
