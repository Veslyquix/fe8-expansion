#!/usr/bin/env python3
"""Compare vanilla and candidate VBA-rr TAS framebuffer fingerprints."""

import argparse
import json
from pathlib import Path
import sys


def _load(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: {error}") from error
    if data.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported schema_version")
    return data


def _checkpoint_map(data):
    result = {}
    for item in data.get("checkpoints", []):
        frame = item.get("frame")
        digest = item.get("sha256")
        if not isinstance(frame, int) or not isinstance(digest, str):
            raise ValueError("malformed checkpoint entry")
        if frame in result:
            raise ValueError(f"duplicate checkpoint frame {frame}")
        result[frame] = digest
    return result


def compare(baseline, candidate):
    identity_fields = (
        "fingerprint_format",
        "expected_frames",
        "checkpoint_frames",
    )
    for field in identity_fields:
        if baseline.get(field) != candidate.get(field):
            raise ValueError(
                f"incompatible fingerprints: {field} differs "
                f"({baseline.get(field)!r} vs {candidate.get(field)!r})"
            )

    baseline_checkpoints = _checkpoint_map(baseline)
    candidate_checkpoints = _checkpoint_map(candidate)
    frames = sorted(set(baseline_checkpoints) | set(candidate_checkpoints))
    divergences = []
    for frame in frames:
        expected = baseline_checkpoints.get(frame)
        actual = candidate_checkpoints.get(frame)
        if expected != actual:
            divergences.append((frame, expected, actual))

    complete = (
        baseline.get("complete") is True
        and candidate.get("complete") is True
        and baseline.get("emulation_frames") == baseline.get("expected_frames")
        and candidate.get("emulation_frames") == candidate.get("expected_frames")
    )
    return complete, frames, divergences


def endpoint_matches(baseline, candidate):
    frame = baseline.get("expected_frames")
    if frame != candidate.get("expected_frames"):
        raise ValueError("incompatible fingerprints: expected_frames differs")
    baseline_hash = _checkpoint_map(baseline).get(frame)
    candidate_hash = _checkpoint_map(candidate).get(frame)
    matches = baseline_hash is not None and baseline_hash == candidate_hash
    return frame, baseline_hash, candidate_hash, matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--policy", choices=("exact", "endpoint"), default="exact")
    args = parser.parse_args()

    try:
        baseline = _load(args.baseline)
        candidate = _load(args.candidate)
        complete, frames, divergences = compare(baseline, candidate)
        endpoint_frame, baseline_endpoint, candidate_endpoint, endpoint_ok = endpoint_matches(
            baseline, candidate
        )
    except ValueError as error:
        print(f"compare_vba: error: {error}", file=sys.stderr)
        return 2

    print("=" * 72)
    print(
        "VBA-rr TAS replay: "
        f"{baseline.get('tag', 'baseline')} vs {candidate.get('tag', 'candidate')}"
    )
    print("=" * 72)
    print(
        f"baseline:  {baseline.get('emulation_frames')} / "
        f"{baseline.get('expected_frames')} frames, complete={baseline.get('complete')}"
    )
    print(
        f"candidate: {candidate.get('emulation_frames')} / "
        f"{candidate.get('expected_frames')} frames, complete={candidate.get('complete')}"
    )
    for frame in frames:
        expected = _checkpoint_map(baseline).get(frame)
        actual = _checkpoint_map(candidate).get(frame)
        status = "OK" if expected == actual else "DIVERGE"
        print(f"  frame {frame:7d}: {expected}  {actual}  [{status}]")

    if not complete:
        print("RESULT: a replay did not produce the complete expected frame stream.")
        return 1
    if args.policy == "endpoint":
        if not endpoint_ok:
            print(
                f"RESULT: endpoint mismatch at frame {endpoint_frame}: "
                f"{baseline_endpoint} vs {candidate_endpoint}."
            )
            return 1
        print(
            f"RESULT: both replays completed and the frame-{endpoint_frame} "
            f"endpoint matches ({len(divergences)} intermediate timing divergence(s))."
        )
        return 0
    if divergences:
        print(f"RESULT: first framebuffer divergence at frame {divergences[0][0]}.")
        return 1
    print(
        f"RESULT: identical at all {len(frames)} checkpoints and both replays "
        "reached the movie endpoint."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
