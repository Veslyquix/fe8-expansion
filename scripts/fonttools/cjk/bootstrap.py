"""Explicit network bootstrap for the hash-pinned vendored Noto inputs."""

from __future__ import annotations

import urllib.request
from pathlib import Path

from .inventory import (
    CjkFontError,
    FONT_SOURCES,
    LICENSE_SOURCE,
    sha256_bytes,
)


def _fetch(url: str, maximum: int) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "fireemblem8-expansion-cjk-font-bootstrap/1"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read(maximum + 1)
    if not data or len(data) > maximum:
        raise CjkFontError(f"{url}: download size is outside the allowed bound")
    return data


def bootstrap_fonts(root: Path) -> int:
    sources = [
        (
            record["path"],
            record["source_url"],
            record["sha256"],
            record["byte_length"],
        )
        for record in FONT_SOURCES.values()
    ]
    sources.append(
        (
            LICENSE_SOURCE["path"],
            LICENSE_SOURCE["source_url"],
            LICENSE_SOURCE["sha256"],
            1024 * 1024,
        )
    )
    downloaded = 0
    for relative_path, url, expected_hash, maximum in sources:
        path = root / relative_path
        if path.is_file() and sha256_bytes(path.read_bytes()) == expected_hash:
            continue
        data = _fetch(url, maximum)
        if sha256_bytes(data) != expected_hash:
            raise CjkFontError(f"{url}: downloaded SHA-256 does not match the pin")
        path.parent.mkdir(parents=True, exist_ok=True)
        staging = path.with_name(path.name + ".download")
        try:
            staging.write_bytes(data)
            staging.replace(path)
        finally:
            staging.unlink(missing_ok=True)
        downloaded += 1
    return downloaded
