#!/usr/bin/env python3
"""Copy an FE-Repo battle-animation pack's weapon-script sources into
banim/src/<tag>_<weapon>/, the exact format scripts/banim_event_to_source.py
compiles (via tools/aaa/AAA.py) -- see that script's own module docstring
for the compile step and its "lessons learned the hard way".

An FE-Repo pack directory (as shared on FEU, e.g. "[Nomad-Base] [M]
Vanilla Repal") has one subfolder per weapon, named "N. Weapon..." (N is
the pack's own internal weapon-slot number, and "Weapon..." sometimes
carries a trailing note like "Bow (Vanilla +Fix)"). Each subfolder holds
far more than banim/src/ needs: sheet-preview PNGs ("Weapon Sheet N.png"),
a raw frame-data dump (.dmp), a .bin/.gif preview, a README/CREDITS, and
sometimes alternate script variants (e.g. "Weapon_without_comment.txt").
Only "Weapon.txt" (the Event Assembler frame-command script) and the
numbered "Weapon_NNN.png" frames are real compiler input -- this copies
exactly those, nothing else, matching the existing checked-in shape at
banim/src/archer_bow/ etc.

Usage:
    banim_import_pack.py <pack_dir> <tag> --credit "<credit string>" \\
        --weapons Bow,Unarmed --class-tag arc [--force]

<pack_dir> subfolders are matched by their leading "N. " prefix; the
weapon name used for banim/src/<tag>_<weapon lowercased>/ and for locating
"Weapon.txt" inside is the FIRST WHITESPACE-DELIMITED WORD after that
prefix (so "5. Bow (Vanilla +Fix)" resolves to weapon "Bow", using the
subfolder's own plain "Bow.txt" -- the "(Vanilla +Fix)" note describes the
pack, not an alternate script to select).

--weapons must list every weapon this pack should contribute, in the
exact order slots should be assigned (this becomes banim_packs.json's
"weapons" list, consumed by banim_event_to_source.py). A subfolder that
exists in <pack_dir> but isn't named in --weapons is left alone (silently
skipped) -- useful for a pack that includes weapons you don't want yet.

Also appends (or updates, with --force) this pack's entry in
scripts/banim_packs.json, so banim_event_to_source.py --only <tag> picks
it up on the next run with no hand-editing.
"""
import argparse
import json
import pathlib
import re
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = REPO / "banim" / "src"
PACKS_JSON = REPO / "scripts" / "banim_packs.json"


def find_weapon_dir(pack_dir, weapon):
    """Match a "N. Weapon..." subfolder whose first word after the number
    prefix is `weapon` (case-insensitive)."""
    for child in sorted(pack_dir.iterdir()):
        if not child.is_dir():
            continue
        m = re.match(r'^\d+\.\s*(\S+)', child.name)
        if m and m.group(1).lower() == weapon.lower():
            return child
    raise FileNotFoundError(
        f"no 'N. {weapon}...' subfolder under {pack_dir} "
        f"(have: {[c.name for c in pack_dir.iterdir() if c.is_dir()]})")


def copy_weapon_source(pack_dir, weapon, dest_dir, force):
    src_dir = find_weapon_dir(pack_dir, weapon)
    txt_src = src_dir / f"{weapon}.txt"
    if not txt_src.is_file():
        raise FileNotFoundError(f"expected {txt_src} (weapon script) not found")

    frames = sorted(src_dir.glob(f"{weapon}_[0-9][0-9][0-9].png"))
    if not frames:
        raise FileNotFoundError(f"no {weapon}_NNN.png frames found under {src_dir}")

    if dest_dir.exists():
        if not force:
            raise FileExistsError(f"{dest_dir} already exists (pass --force to overwrite)")
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)

    shutil.copy(txt_src, dest_dir / f"{weapon}.txt")
    for f in frames:
        shutil.copy(f, dest_dir / f.name)

    return len(frames)


def update_packs_json(tag, credit, weapons, class_tag, force):
    packs = json.loads(PACKS_JSON.read_text()) if PACKS_JSON.is_file() else {}
    if tag in packs and not force:
        raise KeyError(f"{tag!r} already in {PACKS_JSON.name} (pass --force to overwrite)")
    packs[tag] = {"credit": credit, "weapons": weapons, "class_tag": class_tag}
    PACKS_JSON.write_text(json.dumps(packs, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pack_dir", type=pathlib.Path, help="FE-Repo pack source directory")
    ap.add_argument("tag", help="short pack tag, e.g. 'nomadm' -> banim_new<tag>_<weapon>")
    ap.add_argument("--credit", required=True, help='e.g. "[Nomad-Base] [M] Vanilla Repal"')
    ap.add_argument("--weapons", required=True,
                     help="comma-separated, in slot order, e.g. Bow,Unarmed")
    ap.add_argument("--class-tag", required=True,
                     help="short tag for struct BattleAnim::abbr ('new'+class-tag+2-char-weapon-tag+'1', "
                          "char[12] field so the whole thing must be <=11 chars -- i.e. class-tag <=5 chars)")
    ap.add_argument("--force", action="store_true",
                     help="overwrite an existing banim/src/ copy and/or banim_packs.json entry")
    args = ap.parse_args()

    if not args.pack_dir.is_dir():
        sys.exit(f"error: {args.pack_dir} is not a directory")

    weapons = [w.strip() for w in args.weapons.split(",") if w.strip()]
    if len(args.class_tag) > 5:
        sys.exit(f"error: --class-tag {args.class_tag!r} too long (max 5: "
                 f"'new'(3) + class-tag + weapon-tag(2) + '1'(1) must be <=11, "
                 f"struct BattleAnim::abbr is char[12])")

    for weapon in weapons:
        dest = SRC_DIR / f"{args.tag}_{weapon.lower()}"
        n = copy_weapon_source(args.pack_dir, weapon, dest, args.force)
        print(f"  {dest.relative_to(REPO)}: {n} frames")

    update_packs_json(args.tag, args.credit, weapons, args.class_tag, args.force)
    print(f"\n{args.tag!r} added to {PACKS_JSON.relative_to(REPO)} "
          f"({len(weapons)} weapons: {', '.join(weapons)})")
    print(f"Next: python3 scripts/banim_event_to_source.py --only {args.tag}")


if __name__ == "__main__":
    main()
