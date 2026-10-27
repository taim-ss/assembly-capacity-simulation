"""Verify ZIP inventory/hashes/CRC and optionally extract into a new folder.

Reading every member through ZipExtFile checks CRC without a second full
decompression pass. Archive acceptance never implies native model acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import zipfile

CHUNK_BYTES = 1024 * 1024


def sha256_stream(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
        digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return sha256_stream(stream)


def safe_member(name: str, *, directory: bool = False) -> PurePosixPath:
    trimmed = name[:-1] if directory and name.endswith("/") else name
    path = PurePosixPath(trimmed)
    if (not trimmed or not path.parts or "\\" in trimmed or path.is_absolute()
            or path.as_posix() != trimmed or any(part in (".", "..") for part in path.parts)
            or any(":" in part or "\x00" in part for part in path.parts)):
        raise ValueError(f"Unsafe ZIP member path: {name!r}")
    for part in path.parts:
        stem = part.split(".", 1)[0].upper()
        if (part.endswith((" ", ".")) or stem in {"CON", "PRN", "AUX", "NUL"}
                or re.fullmatch(r"(?:COM|LPT)[1-9]", stem)):
            raise ValueError(f"Unsafe Windows ZIP member path: {name!r}")
    return path


def verify_archive(archive: Path, *, extract_to: Path | None = None) -> dict:
    archive = Path(archive).resolve()
    destination = Path(extract_to).resolve() if extract_to is not None else None
    if destination is not None and destination.exists():
        raise ValueError(f"Extraction requires a new, nonexistent directory: {destination}")
    with zipfile.ZipFile(archive) as zipped:
        infos = zipped.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP member names")
        if len(names) != len({name.casefold() for name in names}):
            raise ValueError("Case-colliding ZIP member names")
        for item in infos:
            safe_member(item.filename, directory=item.is_dir())
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError(f"Symbolic links are not allowed: {item.filename}")
        if "MANIFEST.json" not in names:
            raise ValueError("Missing MANIFEST.json")
        manifest = json.loads(zipped.read("MANIFEST.json"))
        records = manifest.get("files")
        if not isinstance(records, list):
            raise ValueError("Manifest files must be a list")
        expected = {}
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                raise ValueError("Invalid manifest record")
            name = record["path"]
            safe_member(name)
            if name in expected or name == "MANIFEST.json":
                raise ValueError(f"Duplicate/reserved manifest path: {name}")
            if (type(record.get("bytes")) is not int or record["bytes"] < 0
                    or not re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", "")))):
                raise ValueError(f"Invalid manifest size/hash: {name}")
            expected[name] = record
        actual = {item.filename for item in infos if not item.is_dir()} - {"MANIFEST.json"}
        if actual != set(expected):
            raise ValueError(f"ZIP inventory mismatch; missing={sorted(set(expected)-actual)}, extra={sorted(actual-set(expected))}")
        for name, record in expected.items():
            if zipped.getinfo(name).file_size != record["bytes"]:
                raise ValueError(f"ZIP size mismatch: {name}")
            with zipped.open(name) as member:
                if sha256_stream(member) != record["sha256"]:
                    raise ValueError(f"ZIP SHA-256 mismatch: {name}")
        model_name = manifest.get("canonical_model")
        if model_name is not None and (not isinstance(model_name, str) or model_name not in expected):
            raise ValueError("Canonical model is not a manifested payload file")
        if destination is not None:
            destination.mkdir(parents=True, exist_ok=False)
            for item in infos:
                relative = safe_member(item.filename, directory=item.is_dir())
                target = destination.joinpath(*relative.parts)
                if not target.resolve().is_relative_to(destination):
                    raise ValueError(f"ZIP extraction escapes its destination: {item.filename}")
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zipped.open(item) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output, length=CHUNK_BYTES)
    extracted_model_hash = None
    if destination is not None and model_name is not None:
        extracted_model_hash = sha256_file(destination.joinpath(*safe_member(model_name).parts))
        if extracted_model_hash != expected[model_name]["sha256"]:
            raise ValueError("Extracted model SHA-256 mismatch")
    return {"archive": str(archive), "bytes": archive.stat().st_size,
            "sha256": sha256_file(archive), "files": len(expected), "crc": "passed",
            "inventory": "passed", "file_sha256": "passed",
            "extracted_to": str(destination) if destination is not None else None,
            "extracted_model_sha256": extracted_model_hash,
            "scope": "Archive integrity and optional fresh extraction; no AnyLogic execution"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--extract-to", type=Path)
    parser.add_argument("--report", type=Path, help="External verification JSON")
    args = parser.parse_args()
    report = args.report or args.archive.with_suffix(".verification.json")
    if report.resolve() == args.archive.resolve():
        raise ValueError("The verification report must not overwrite its archive")
    if args.extract_to is not None and report.resolve().is_relative_to(args.extract_to.resolve()):
        raise ValueError("Keep the verification report outside the fresh extraction directory")
    result = verify_archive(args.archive, extract_to=args.extract_to)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
