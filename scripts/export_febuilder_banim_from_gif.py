#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageSequence


def collect_shared_palette(frames: list[Image.Image]) -> tuple[list[int], dict[tuple[int, int, int], int], tuple[int, int, int]]:
    bg = frames[0].getpixel((0, 0))[:3]

    colors: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()

    def add_color(rgb: tuple[int, int, int]) -> None:
        if rgb not in seen:
            colors.append(rgb)
            seen.add(rgb)

    add_color(bg)

    for frame in frames:
        frame_colors = frame.getcolors(maxcolors=1000000)
        if frame_colors is None:
            raise RuntimeError("Too many colors to inspect in GIF frame")

        for _, rgba in sorted(frame_colors, key=lambda item: item[1]):
            add_color(rgba[:3])

    if len(colors) > 16:
        raise RuntimeError(f"{len(colors)} colors found; FEBuilder GBA battle animation frames need 16 or fewer")

    padded = colors + [(0, 0, 0)] * (256 - len(colors))
    palette = [component for rgb in padded for component in rgb]
    index_by_rgb = {rgb: index for index, rgb in enumerate(colors)}

    return palette, index_by_rgb, bg


def write_indexed_frames(gif_path: Path, out_dir: Path, prefix: str) -> int:
    with Image.open(gif_path) as image:
        frames = [frame.convert("RGBA") for frame in ImageSequence.Iterator(image)]

    if len(frames) < 3:
        raise RuntimeError("Expected at least 3 frames so the last two can be used as dodge frames")

    palette, index_by_rgb, bg = collect_shared_palette(frames)

    for index, frame in enumerate(frames):
        out_frame = Image.new("P", frame.size)
        out_frame.putpalette(palette)
        out_frame.putdata([index_by_rgb[rgba[:3]] for rgba in frame.getdata()])
        out_frame.save(out_dir / f"{prefix}_{index:03d}.png", optimize=False)

    print(f"Wrote {len(frames)} frames. Background palette index: {index_by_rgb[bg]}")
    return len(frames)


def build_blocks(prefix: str, frame_count: int, frame_duration: int) -> tuple[list[str], list[str], list[str]]:
    dodge_a = frame_count - 2
    dodge_b = frame_count - 1
    attack_last = frame_count - 2
    spell_call_at = max(1, attack_last * 2 // 3)

    attack_block = ["C03", "C07"]
    for index in range(attack_last):
        if index == spell_call_at:
            attack_block.append("C05")
        attack_block.append(f"{frame_duration} p- {prefix}_{index:03d}.png")

    if "C05" not in attack_block:
        attack_block.append("C05")

    attack_block += ["C01", f"{frame_duration} p- {prefix}_000.png", "C0D"]

    dodge_block = [
        "C02",
        f"1 p- {prefix}_000.png",
        "C0E",
        f"3 p- {prefix}_{dodge_a:03d}.png",
        f"1 p- {prefix}_{dodge_b:03d}.png",
        "C01",
        f"3 p- {prefix}_{dodge_a:03d}.png",
        "C0D",
    ]

    stand_block = [f"1 p- {prefix}_000.png", "C01"]
    return attack_block, dodge_block, stand_block


def write_scripts(out_dir: Path, prefix: str, frame_count: int, frame_duration: int) -> None:
    attack_block, dodge_block, stand_block = build_blocks(prefix, frame_count, frame_duration)

    modes = [
        (1, attack_block),
        (3, attack_block),
        (5, attack_block),
        (6, attack_block),
        (7, dodge_block),
        (8, dodge_block),
        (9, stand_block),
        (10, stand_block),
        (11, stand_block),
        (12, attack_block),
    ]

    lines: list[str] = []
    for mode, block in modes:
        lines.append(f"/// - Mode {mode}")
        lines.extend(block)
        lines.append("~~~")
    lines.append("/// - End of animation")
    (out_dir / f"{prefix}_without_comment.txt").write_text("\n".join(lines) + "\n", newline="\n")

    comments = {
        1: "Melee Animation",
        3: "Melee Critical Animation",
        5: "Ranged Animation",
        6: "Ranged Critical Animation",
        7: "Dodge Melee Attack",
        8: "Dodge Ranged Attack",
        9: "Equipped with Melee Weapon",
        10: "Standing motions",
        11: "Equipped with Ranged weapon",
        12: "Attack Missed Animation",
    }
    command_comments = {
        "C03": "Start attack animation; need 07 right after this.",
        "C07": "Start attack animation; need 03 right before this.",
        "C05": "Call spell associated with equipped weapon",
        "C02": "Start of dodge",
        "C0E": "Start of dodging frames",
        "C01": "NOP",
        "C0D": "End of animation/dodge block",
    }

    comment_lines = [
        "#######################################################",
        f"# {prefix}",
        "#",
        "# FEBuilder/FEditor-style battle animation script generated from GIF.",
        f"# Frames {prefix}_{frame_count - 2:03d}.png and {prefix}_{frame_count - 1:03d}.png are dodge frames.",
        "#######################################################",
    ]
    for mode, block in modes:
        comment_lines.append(f"/// - Mode {mode}               #{comments[mode]}")
        for line in block:
            suffix = command_comments.get(line)
            if suffix:
                comment_lines.append(f"{line:<34}#{suffix}")
            else:
                comment_lines.append(line)
        comment_lines.append("~~~")
    comment_lines.append("/// - End of animation")
    (out_dir / f"{prefix}.txt").write_text("\n".join(comment_lines) + "\n", newline="\n")


def export_gif(gif_path: Path, out_dir: Path | None, prefix: str | None, frame_duration: int) -> None:
    gif_path = gif_path.resolve()
    if not gif_path.exists():
        raise FileNotFoundError(gif_path)

    prefix = prefix or gif_path.stem
    out_dir = (out_dir or gif_path.with_suffix("")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(gif_path, out_dir / gif_path.name)
    frame_count = write_indexed_frames(gif_path, out_dir, prefix)
    write_scripts(out_dir, prefix, frame_count, frame_duration)

    print(f"Exported {gif_path.name} to {out_dir}")
    print(f"Dodge frames: {prefix}_{frame_count - 2:03d}.png, {prefix}_{frame_count - 1:03d}.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a 16-color GIF into FEBuilder/FEditor-style battle animation PNGs and script.")
    parser.add_argument("gif", type=Path, help="Source GIF. The last two frames are used as dodge frames.")
    parser.add_argument("--out-dir", type=Path, default=None, help="Output folder. Defaults to the GIF name without .gif.")
    parser.add_argument("--prefix", default=None, help="Output file prefix. Defaults to the GIF stem.")
    parser.add_argument("--frame-duration", type=int, default=6, help="FEBuilder script duration for normal attack frames.")
    args = parser.parse_args()

    export_gif(args.gif, args.out_dir, args.prefix, args.frame_duration)


if __name__ == "__main__":
    main()
