"""Validate FEBuilderGBA schema-v1 packages and import compact ROM assets."""

from __future__ import annotations

import binascii
import csv
import hashlib
import io
import json
import struct
import zipfile
import zlib
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from .inventory import (
    CjkFontError,
    LOCALES,
    STYLES,
    json_bytes,
    scalar_text,
    sha256_bytes,
)

PACKAGE_ARCHIVE = "fonts/cjk/packages/febuilder-schema-v1.zip"
GENERATION_REPORT = "fonts/cjk/reports/febuilder-generation-report.json"
ASSET_ROOT = "graphics/fonts/cjk"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SLOTS_HEADER = (
    "moji\tunicode\tstyle\twidth\tfilename\tpackedSha256\tpngSha256"
)


def _safe_member(name: str) -> str:
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise CjkFontError(f"unsafe package member {name!r}")
    return path.as_posix()


class PackageReader:
    def __init__(self, path: Path):
        self.path = path
        self.archive = None
        if path.is_dir():
            self.kind = "directory"
        elif path.is_file() and zipfile.is_zipfile(path):
            self.kind = "zip"
            self.archive = zipfile.ZipFile(path, "r")
            seen = set()
            for info in self.archive.infolist():
                name = _safe_member(info.filename)
                if name in seen:
                    raise CjkFontError(f"duplicate ZIP member {name}")
                seen.add(name)
                if info.is_dir():
                    raise CjkFontError("package ZIP must not contain directory entries")
        else:
            raise CjkFontError(f"{path}: expected a package directory or ZIP archive")

    def close(self) -> None:
        if self.archive is not None:
            self.archive.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def names(self) -> Tuple[str, ...]:
        if self.kind == "zip":
            return tuple(sorted(info.filename for info in self.archive.infolist()))
        names = []
        for path in self.path.rglob("*"):
            if path.is_file():
                names.append(path.relative_to(self.path).as_posix())
        return tuple(sorted(names))

    def read(self, name: str) -> bytes:
        name = _safe_member(name)
        if self.kind == "zip":
            try:
                return self.archive.read(name)
            except KeyError as error:
                raise CjkFontError(f"package member is missing: {name}") from error
        path = self.path / name
        if not path.is_file():
            raise CjkFontError(f"package member is missing: {name}")
        return path.read_bytes()


def _archive_bytes(members: Iterable[Tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        "w",
        compression=zipfile.ZIP_STORED,
        strict_timestamps=True,
    ) as archive:
        for name, data in sorted(members):
            name = _safe_member(name)
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, data)
    return buffer.getvalue()


def archive_package(package_dir: Path, output: Path) -> bytes:
    if not package_dir.is_dir():
        raise CjkFontError(f"{package_dir}: package directory is missing")
    members = (
        (path.relative_to(package_dir).as_posix(), path.read_bytes())
        for path in package_dir.rglob("*")
        if path.is_file()
    )
    data = _archive_bytes(members)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return data


def check_package_archive(package_path: Path) -> None:
    committed = package_path.read_bytes()
    with PackageReader(package_path) as package:
        rebuilt = _archive_bytes((name, package.read(name)) for name in package.names())
    if rebuilt != committed:
        raise CjkFontError("committed FEBuilder package ZIP is not canonical")


def _read_png_indices(png: bytes) -> bytes:
    if not png.startswith(PNG_SIGNATURE):
        raise CjkFontError("invalid PNG signature")
    position = len(PNG_SIGNATURE)
    chunks: List[Tuple[bytes, bytes]] = []
    while position < len(png):
        if position + 12 > len(png):
            raise CjkFontError("truncated PNG chunk")
        length = struct.unpack_from(">I", png, position)[0]
        chunk_type = png[position + 4 : position + 8]
        start = position + 8
        end = start + length
        if end + 4 > len(png):
            raise CjkFontError("PNG chunk exceeds file bounds")
        payload = png[start:end]
        expected_crc = struct.unpack_from(">I", png, end)[0]
        actual_crc = binascii.crc32(chunk_type + payload) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise CjkFontError(f"{chunk_type!r} PNG CRC mismatch")
        chunks.append((chunk_type, payload))
        position = end + 4
        if chunk_type == b"IEND":
            break
    if position != len(png):
        raise CjkFontError("PNG has trailing bytes")
    if [chunk_type for chunk_type, _ in chunks] != [
        b"IHDR",
        b"PLTE",
        b"tRNS",
        b"IDAT",
        b"IEND",
    ]:
        raise CjkFontError("PNG chunk order is not canonical")
    ihdr = chunks[0][1]
    if (
        len(ihdr) != 13
        or struct.unpack_from(">II", ihdr, 0) != (16, 16)
        or ihdr[8:] != bytes((2, 3, 0, 0, 0))
    ):
        raise CjkFontError("PNG is not canonical 16x16 indexed 2bpp")
    if len(chunks[1][1]) != 12:
        raise CjkFontError("PNG palette must contain exactly four RGB entries")
    if chunks[2][1] != bytes((0, 255, 255, 255)):
        raise CjkFontError("PNG transparency table is not canonical")
    try:
        raw = zlib.decompress(chunks[3][1])
    except zlib.error as error:
        raise CjkFontError(f"PNG zlib stream is invalid: {error}") from error
    if len(raw) != 80:
        raise CjkFontError("PNG decompressed scanline size is invalid")
    indices = bytearray()
    for row in range(16):
        scanline = raw[row * 5 : (row + 1) * 5]
        if scanline[0] != 0:
            raise CjkFontError("PNG must use filter None for every scanline")
        for packed in scanline[1:]:
            indices.extend(
                (
                    (packed >> 6) & 3,
                    (packed >> 4) & 3,
                    (packed >> 2) & 3,
                    packed & 3,
                )
            )
    return bytes(indices)


def _pack_engine_tile(indices: bytes) -> bytes:
    if len(indices) != 256 or any(value > 3 for value in indices):
        raise CjkFontError("glyph indices must contain 256 values in 0..3")
    packed = bytearray()
    for offset in range(0, 256, 4):
        packed.append(
            indices[offset]
            | (indices[offset + 1] << 2)
            | (indices[offset + 2] << 4)
            | (indices[offset + 3] << 6)
        )
    return bytes(packed)


def _parse_scalar(text: str) -> int:
    if not text.startswith("U+"):
        raise CjkFontError(f"invalid Unicode scalar spelling {text!r}")
    try:
        value = int(text[2:], 16)
    except ValueError as error:
        raise CjkFontError(f"invalid Unicode scalar spelling {text!r}") from error
    if text != scalar_text(value) or value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
        raise CjkFontError(f"non-canonical Unicode scalar {text!r}")
    return value


def _parse_slots(data: bytes, job_id: str) -> List[Dict[str, object]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CjkFontError(f"{job_id}/slots.tsv is not UTF-8") from error
    if "\r" in text or not text.endswith("\n"):
        raise CjkFontError(f"{job_id}/slots.tsv must use canonical LF text")
    lines = text.splitlines()
    if not lines or lines[0] != SLOTS_HEADER:
        raise CjkFontError(f"{job_id}/slots.tsv header is invalid")
    rows = []
    reader = csv.reader(lines[1:], delimiter="\t", strict=True)
    for columns in reader:
        if len(columns) != 7:
            raise CjkFontError(f"{job_id}/slots.tsv row must have seven columns")
        moji, scalar, style, width, filename, packed_hash, png_hash = columns
        try:
            moji_value = int(moji, 16)
            width_value = int(width, 10)
        except ValueError as error:
            raise CjkFontError(f"{job_id}/slots.tsv has invalid numeric data") from error
        if moji != f"{moji_value:X}" or width != str(width_value):
            raise CjkFontError(f"{job_id}/slots.tsv numeric spelling is not canonical")
        if style not in ("item", "text") or not 1 <= width_value <= 16:
            raise CjkFontError(f"{job_id}/slots.tsv style or width is invalid")
        if filename != f"{style}_{moji_value:X}.png":
            raise CjkFontError(f"{job_id}/slots.tsv filename is not canonical")
        for digest in (packed_hash, png_hash):
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise CjkFontError(f"{job_id}/slots.tsv hash is invalid")
        rows.append(
            {
                "moji": moji_value,
                "scalar": _parse_scalar(scalar),
                "style": style,
                "width": width_value,
                "filename": filename,
                "packed_sha256": packed_hash,
                "png_sha256": png_hash,
            }
        )
    if not rows:
        raise CjkFontError(f"{job_id}/slots.tsv is empty")
    return rows


def _expected_jobs(root: Path) -> Dict[str, Dict[str, object]]:
    manifest_path = root / "fonts/cjk/febuilder-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    jobs = {}
    for job in manifest["jobs"]:
        job_id = job["id"]
        if job_id in jobs:
            raise CjkFontError(f"duplicate FEBuilder job id {job_id}")
        jobs[job_id] = job
    return jobs


def _tree_sha256(package: PackageReader, names: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(names):
        data = package.read(name)
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(struct.pack(">Q", len(data)))
        digest.update(data)
    return digest.hexdigest()


def _job_contract(job: Mapping[str, object]) -> Tuple[str, str, str]:
    locale = str(job["locale"])
    if locale not in LOCALES:
        raise CjkFontError(f"unsupported locale {locale}")
    styles = job["styles"]
    if styles == ["item"]:
        return locale, "system", "item"
    if styles == ["text"]:
        return locale, "talk", "text"
    raise CjkFontError(f"{job['id']}: expected exactly one item/text style")


def build_compact_assets(
    root: Path,
    package_path: Path,
    report_path: Path,
) -> Dict[str, bytes]:
    jobs = _expected_jobs(root)
    manifest_data = (root / "fonts/cjk/febuilder-manifest.json").read_bytes()
    inventory_data = (root / "fonts/cjk/inventory.json").read_bytes()
    report_data = report_path.read_bytes()
    try:
        report = json.loads(report_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CjkFontError(f"{report_path}: invalid generation report") from error
    if report.get("schemaVersion") != 1 or report.get("mode") != "generate":
        raise CjkFontError("generation report is not FEBuilder schema-v1 generate output")
    if report.get("manifestSha256") != sha256_bytes(manifest_data):
        raise CjkFontError("generation report manifest SHA-256 mismatch")

    package_data = package_path.read_bytes() if package_path.is_file() else b""
    outputs: Dict[str, bytes] = {}
    asset_records: Dict[str, object] = {}
    payload_total = 0
    aligned_total = 0
    expected_names = {"package-report.json"}

    with PackageReader(package_path) as package:
        package_names = set(package.names())
        actual_full_tree = _tree_sha256(package, package_names)
        if actual_full_tree != report.get("fullTreeSha256"):
            raise CjkFontError("generation report full-tree SHA-256 mismatch")
        package_report_data = package.read("package-report.json")
        try:
            package_report = json.loads(package_report_data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CjkFontError("package-report.json is invalid") from error
        if package_report.get("manifestSha256") != sha256_bytes(manifest_data):
            raise CjkFontError("package report manifest SHA-256 mismatch")
        payload_names = package_names - {"package-report.json"}
        actual_payload_tree = _tree_sha256(package, payload_names)
        if actual_payload_tree != package_report.get("payloadTreeSha256"):
            raise CjkFontError("package report payload-tree SHA-256 mismatch")
        if actual_payload_tree != report.get("payloadTreeSha256"):
            raise CjkFontError("generation report payload-tree SHA-256 mismatch")
        report_jobs = {row["id"]: row for row in report.get("jobs", [])}
        package_jobs = {row["id"]: row for row in package_report.get("jobs", [])}
        if set(report_jobs) != set(jobs) or set(package_jobs) != set(jobs):
            raise CjkFontError("FEBuilder reports do not cover exactly the manifest jobs")

        for job_id in sorted(jobs):
            job = jobs[job_id]
            locale, runtime_style, package_style = _job_contract(job)
            corpus_path = root / "fonts/cjk" / job["corpus"]["path"]
            corpus = corpus_path.read_text(encoding="utf-8")
            expected_scalars = tuple(ord(character) for character in corpus)
            if expected_scalars != tuple(sorted(set(expected_scalars))):
                raise CjkFontError(f"{corpus_path}: scalars must be sorted and unique")
            if sha256_bytes(corpus.encode("utf-8")) != job["corpus"]["sha256"]:
                raise CjkFontError(f"{corpus_path}: corpus SHA-256 mismatch")

            slots_name = f"{job_id}/slots.tsv"
            fontall_name = f"{job_id}/{job_id}.fontall.txt"
            rows = _parse_slots(package.read(slots_name), job_id)
            expected_names.update((slots_name, fontall_name))
            rows.sort(key=lambda row: row["scalar"])
            actual_scalars = tuple(row["scalar"] for row in rows)
            if actual_scalars != expected_scalars:
                raise CjkFontError(f"{job_id}: package scalar coverage mismatch")
            if len(set(actual_scalars)) != len(actual_scalars):
                raise CjkFontError(f"{job_id}: duplicate Unicode scalar")
            if any(row["style"] != package_style for row in rows):
                raise CjkFontError(f"{job_id}: package style mismatch")
            if report_jobs[job_id]["scalarCount"] != len(rows):
                raise CjkFontError(f"{job_id}: generation report scalar count mismatch")
            if package_jobs[job_id]["scalarCount"] != len(rows):
                raise CjkFontError(f"{job_id}: package report scalar count mismatch")

            glyphs = bytearray()
            widths = bytearray()
            codepoints = bytearray()
            for row in rows:
                png_name = f"{job_id}/{row['filename']}"
                png = package.read(png_name)
                expected_names.add(png_name)
                if sha256_bytes(png) != row["png_sha256"]:
                    raise CjkFontError(f"{png_name}: PNG SHA-256 mismatch")
                packed = _pack_engine_tile(_read_png_indices(png))
                if sha256_bytes(packed) != row["packed_sha256"]:
                    raise CjkFontError(f"{png_name}: packed SHA-256 mismatch")
                if not any(packed):
                    raise CjkFontError(f"{png_name}: all-zero glyph")
                glyphs.extend(packed)
                widths.append(row["width"])
                codepoints.extend(struct.pack("<I", row["scalar"]))

            prefix = f"{locale}.{runtime_style}"
            files = {
                "codepoints": (f"{prefix}.codepoints.bin", bytes(codepoints)),
                "widths": (f"{prefix}.widths.bin", bytes(widths)),
                "glyphs": (f"{prefix}.glyphs.2bpp", bytes(glyphs)),
            }
            for _, (filename, data) in files.items():
                outputs[f"{ASSET_ROOT}/{filename}"] = data
                payload_total += len(data)
                aligned_total += (len(data) + 3) & ~3
            asset_records[prefix] = {
                "locale": locale,
                "runtime_style": runtime_style,
                "febuilder_job": job_id,
                "febuilder_style": package_style,
                "glyph_count": len(rows),
                "bitmap": {
                    "format": "16x16 row-major 2bpp, four pixels per byte, low-bit-first",
                    "stride_bytes": 64,
                    "path": f"{ASSET_ROOT}/{files['glyphs'][0]}",
                    "byte_count": len(files["glyphs"][1]),
                    "sha256": sha256_bytes(files["glyphs"][1]),
                },
                "widths": {
                    "format": "one unsigned byte per glyph; valid range 1..16",
                    "path": f"{ASSET_ROOT}/{files['widths'][0]}",
                    "byte_count": len(files["widths"][1]),
                    "sha256": sha256_bytes(files["widths"][1]),
                },
                "codepoints": {
                    "format": "sorted unique little-endian uint32 Unicode scalars",
                    "path": f"{ASSET_ROOT}/{files['codepoints'][0]}",
                    "byte_count": len(files["codepoints"][1]),
                    "sha256": sha256_bytes(files["codepoints"][1]),
                },
            }

        if package_names != expected_names:
            extras = sorted(package_names - expected_names)
            missing = sorted(expected_names - package_names)
            raise CjkFontError(
                f"package tree mismatch; extras={extras[:5]} missing={missing[:5]}"
            )

    asset_manifest = {
        "schema_version": 1,
        "contract": {
            "lookup": (
                "binary-search codepoints; use the same index for widths and "
                "the fixed 64-byte bitmap stride"
            ),
            "ascii": "continue using the existing runtime ASCII font",
            "spacing": (
                "U+3000 is inventoried as a spacing scalar, not a bitmap; "
                "Sprint 3 must give it an explicit advance"
            ),
        },
        "spacing_scalars": [
            {
                "scalar": "U+3000",
                "advance": 16,
                "locales": ["ja"],
                "runtime_styles": ["system", "talk"],
                "bitmap": None,
            }
        ],
        "sources": {
            "inventory": {
                "path": "fonts/cjk/inventory.json",
                "sha256": sha256_bytes(inventory_data),
            },
            "febuilder_manifest": {
                "path": "fonts/cjk/febuilder-manifest.json",
                "sha256": sha256_bytes(manifest_data),
            },
            "febuilder_package": {
                "path": PACKAGE_ARCHIVE,
                "sha256": sha256_bytes(package_data) if package_data else "",
                "byte_count": len(package_data),
                "package_report_sha256": sha256_bytes(package_report_data),
                "payload_tree_sha256": package_report.get("payloadTreeSha256"),
                "full_tree_sha256": report.get("fullTreeSha256"),
            },
            "febuilder_generation_report": {
                "path": GENERATION_REPORT,
                "sha256": sha256_bytes(report_data),
                "byte_count": len(report_data),
            },
        },
        "assets": asset_records,
        "rom_budget": {
            "payload_bytes": payload_total,
            "four_byte_aligned_blob_bytes": aligned_total,
            "bytes_per_glyph": 69,
            "includes": "64-byte bitmap + 1-byte width + 4-byte Unicode scalar",
        },
    }
    outputs[f"{ASSET_ROOT}/manifest.json"] = json_bytes(asset_manifest)
    return outputs


def write_compact_assets(
    root: Path,
    package_path: Path,
    report_path: Path,
) -> Dict[str, bytes]:
    outputs = build_compact_assets(root, package_path, report_path)
    for relative_path, data in outputs.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return outputs


def check_compact_assets(root: Path) -> Dict[str, bytes]:
    package_path = root / PACKAGE_ARCHIVE
    report_path = root / GENERATION_REPORT
    check_package_archive(package_path)
    gate_path = root / "fonts/cjk/reports/febuilder-gates.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if gate.get("result") != "all FEBuilder schema-v1 gates exited 0":
        raise CjkFontError("FEBuilder gate evidence does not record a passing run")
    manifest_hash = sha256_bytes(
        (root / "fonts/cjk/febuilder-manifest.json").read_bytes()
    )
    for name in ("dry_run", "generate", "validate", "roundtrip"):
        result = gate.get("gates", {}).get(name, {})
        if (
            result.get("manifest_sha256") != manifest_hash
            or result.get("job_count") != 4
            or result.get("row_count") != 8610
            or result.get("outcomes") != []
        ):
            raise CjkFontError(f"FEBuilder {name} gate evidence is invalid")
    if gate["files"]["generation_report_sha256"] != sha256_bytes(
        report_path.read_bytes()
    ):
        raise CjkFontError("FEBuilder gate generation-report hash drifted")
    outputs = build_compact_assets(root, package_path, report_path)
    mismatches = []
    for relative_path, expected in outputs.items():
        path = root / relative_path
        if not path.is_file() or path.read_bytes() != expected:
            mismatches.append(relative_path)
    if mismatches:
        raise CjkFontError(
            "committed compact font assets drifted: " + ", ".join(mismatches)
        )
    return outputs
