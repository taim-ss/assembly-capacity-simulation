"""Package the SYNTHETIC P3 core separately from completed native evidence.

Run after report/results/accepted visuals are saved. No AnyLogic is started here.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PureWindowsPath
import re
import zipfile
from verify_package import sha256_file, verify_archive

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("analysis", "docs", "model", "results", "tests", "tools")
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".build", ".scratch", "diagnostics",
                  ".git", ".venv", "venv", "node_modules", ".cache"}
EXCLUDED_PREFIXES = (("results", "recovery"), ("results", "native"), ("results", "native-3d"))
EXCLUDED_NAMES = {"anylogic-editor.png", "anylogic-launch.png", "report-contact.png",
                  "P3_SYNTHETIC_Assembly.alp", "P3_SYNTHETIC_Assembly.original.alp"}


def excluded(relative: Path) -> bool:
    parts = relative.parts
    return (bool(EXCLUDED_PARTS.intersection(parts))
            or any(parts[:len(prefix)] == prefix for prefix in EXCLUDED_PREFIXES)
            or relative.name in EXCLUDED_NAMES
            or relative.name.endswith((".pyc", ".class", ".autosave")))


def included_files(root: Path | None = None) -> list[Path]:
    """Prune private/raw trees before walking; analysis/native remains source code."""
    root = Path(root or ROOT)
    files = [root / name for name in ("README.md", "requirements.txt", ".gitignore")]
    for folder in FOLDERS:
        for directory, dirs, names in os.walk(root / folder, followlinks=False):
            base = Path(directory)
            dirs[:] = sorted(d for d in dirs if not excluded((base / d).relative_to(root))
                             and not (base / d).is_symlink())
            for name in names:
                path = base / name
                if not excluded(path.relative_to(root)):
                    if path.is_symlink():
                        raise ValueError(f"Do not package a symbolic-link file: {path}")
                    files.append(path)
    return sorted(set(files), key=lambda p: p.relative_to(root).as_posix())


def terminal_native_log(path: Path) -> bool:
    """A terminal marker is necessary; full numerical acceptance lives in the analyzer."""
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - 1024))
        lines = [line.strip() for line in stream.read().splitlines() if line.strip()]
    return bool(lines and lines[-1].startswith(b"P3_DONE,"))


def evidence_files(root: Path | None = None) -> tuple[list[tuple[Path, str]], dict]:
    root = Path(root or ROOT)
    entries: dict[str, Path] = {}
    metadata = {"incomplete_logs_excluded": [], "missing_executed_models": [],
                "reference_v1_available": (root.parent / "p3-assembly-flow").is_dir(),
                "scope": "Completed logs and executed private model copies; no conversations or frames"}

    def add(path: Path, name: str):
        if name in entries and entries[name] != path:
            raise ValueError(f"Evidence archive path collision: {name}")
        entries[name] = path

    completed: set[Path] = set()
    for folder in ("native", "native-3d"):
        base = root / "results" / folder
        for path in sorted(base.rglob("native-seed-*.log")):
            if terminal_native_log(path):
                completed.add(path)
                add(path, f"v2/{folder}/" + path.relative_to(base).as_posix())
            else:
                metadata["incomplete_logs_excluded"].append(path.relative_to(root).as_posix())
        for launch in sorted(base.rglob("launch.json")):
            if not any(path.is_relative_to(launch.parent) for path in completed):
                continue
            add(launch, f"v2/{folder}/" + launch.relative_to(base).as_posix())
            data = json.loads(launch.read_text(encoding="utf-8-sig"))
            name = PureWindowsPath(data["alp"]).stem
            if not re.fullmatch(r"P3V2[A-Za-z0-9]+", name):
                raise ValueError(f"Unexpected executed private model name: {name}")
            private = root / "tools/.build/native" / name / (name + ".alp")
            if not private.is_file():
                metadata["missing_executed_models"].append(name)
                continue
            if sha256_file(private) != data["alp_sha256"]:
                raise ValueError(f"Executed private model changed after launch: {name}")
            add(private, f"v2/executed-models/{name}/{private.name}")
            manifest = private.with_name("batch-manifest.json")
            if manifest.is_file():
                add(manifest, f"v2/executed-models/{name}/batch-manifest.json")
            visual_plan = root / "results/native-3d" / name / "visual-plan.json"
            if visual_plan.is_file():
                add(visual_plan, f"v2/executed-models/{name}/visual-plan.json")

    # Keep reference inputs read-only. No source workbook or source CSV is copied.
    v1 = root.parent / "p3-assembly-flow" / "results/native"
    reference = list((v1 / "confirmation").glob("native-seed-*.log"))
    reference += list((v1 / "mm1-confirmation").glob("native-seed-*.log"))
    reference += list(v1.glob("native-seed-*-replay.log"))
    for path in sorted(reference):
        if terminal_native_log(path):
            add(path, "v1-reference/native/" + path.relative_to(v1).as_posix())
    metadata["v2_completed_logs"] = len(completed)
    metadata["v1_reference_completed_logs"] = sum(name.startswith("v1-reference/") for name in entries)
    return [(path, name) for name, path in sorted(entries.items())], metadata


def build_archive(archive: Path, entries: list[tuple[Path, str]], *, kind: str,
                  metadata: dict | None = None) -> dict:
    """Stream hashing/writes; verify content before atomically publishing the ZIP."""
    records = []
    for path, name in entries:
        if not path.is_file():
            raise ValueError(f"Required package file missing: {path}")
        records.append({"path": name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    manifest = {"label": "SYNTHETIC educational P3; agent-produced tier B", "kind": kind,
                "canonical_model": "model/P3_Assembly_Flow.alp" if kind == "core" else None,
                "files": records, "metadata": metadata or {}}
    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive.with_suffix(archive.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as output:
        for path, name in entries:
            output.write(path, name)
        output.writestr("MANIFEST.json", json.dumps(manifest, indent=2))
    result = verify_archive(temporary)
    temporary.replace(archive)
    result.update(archive=str(archive.resolve()), kind=kind)
    archive.with_suffix(".verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    manifest_name = "MANIFEST.json" if kind == "core" else "NATIVE-EVIDENCE-MANIFEST.json"
    (archive.parent / manifest_name).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    checksum_name = "package-sha256.txt" if kind == "core" else "native-evidence-sha256.txt"
    (archive.parent / checksum_name).write_text(f"{result['sha256']}  {archive.name}\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", action="store_true", help="Also create the large raw-native supplement")
    parser.add_argument("--evidence-only", action="store_true", help="Create only the raw-native supplement")
    parser.add_argument("--destination", type=Path, default=ROOT / "deliverables")
    args = parser.parse_args()
    if any(args.destination.resolve().is_relative_to((ROOT / folder).resolve()) for folder in FOLDERS):
        raise ValueError("Archive destination must be outside the packaged source/result folders")
    if not args.evidence_only:
        files = included_files()
        result = build_archive(args.destination / "P3_Assembly_Flow_SYNTHETIC.zip",
            [(path, path.relative_to(ROOT).as_posix()) for path in files], kind="core",
            metadata={"excluded": "Raw logs/captures, private recovery/builds, caches and failed diagnostics",
                      "native_evidence_archive": "P3_Native_Evidence_SYNTHETIC.zip",
                      "runtime_acceptance": "Packaging does not assert a new native run"})
        print(json.dumps(result), flush=True)
    if args.evidence or args.evidence_only:
        entries, metadata = evidence_files()
        if not entries:
            raise ValueError("No completed native evidence found")
        if metadata["missing_executed_models"]:
            raise ValueError(f"Missing executed private model copies: {metadata['missing_executed_models']}")
        result = build_archive(args.destination / "P3_Native_Evidence_SYNTHETIC.zip",
                               entries, kind="native-evidence", metadata=metadata)
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
