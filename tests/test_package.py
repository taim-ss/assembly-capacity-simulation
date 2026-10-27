"""Fabricated archive fixtures test packaging; they are not native execution evidence."""
import hashlib
import json
from pathlib import Path
import stat
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from package_project import build_archive, evidence_files, included_files
from verify_package import sha256_file, verify_archive


def fixture_archive(path, files, *, manifest_files=None):
    records = [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
               for name, data in files.items()]
    manifest = {"canonical_model": "model/P3_Assembly_Flow.alp" if "model/P3_Assembly_Flow.alp" in files else None,
                "files": records if manifest_files is None else manifest_files}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        archive.writestr("MANIFEST.json", json.dumps(manifest))


def test_core_prunes_private_raw_trees_but_preserves_native_analyzer(tmp_path):
    paths = ["README.md", "requirements.txt", ".gitignore", "analysis/native/parsing.py",
             "results/visual-final/animation.gif", "results/analysis/summary.csv",
             "results/native/pilot/raw.log", "results/native-3d/frames/one.png",
             "results/recovery/private-conversation.json", "tools/.build/private.py",
             "tools/.scratch/private.py", "tools/__pycache__/cached.pyc"]
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    included = {p.relative_to(tmp_path).as_posix() for p in included_files(tmp_path)}
    assert included == set(paths[:6])


def test_streamed_package_verifies_and_fresh_extract_refuses_existing_folder(tmp_path, monkeypatch):
    source = tmp_path / "source.alp"
    source.write_bytes(b"synthetic unit-test model\n" * 100_000)
    archive = tmp_path / "package.zip"
    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", lambda self: pytest.fail("Whole-file read is forbidden"))
        result = build_archive(archive, [(source, "model/P3_Assembly_Flow.alp")], kind="core")
        extracted = tmp_path / "fresh"
        accepted = verify_archive(archive, extract_to=extracted)
    assert result["crc"] == accepted["file_sha256"] == "passed"
    assert accepted["extracted_model_sha256"] == sha256_file(extracted / "model/P3_Assembly_Flow.alp")
    assert result["sha256"] == sha256_file(archive)
    with pytest.raises(ValueError, match="new, nonexistent"):
        verify_archive(archive, extract_to=extracted)


@pytest.mark.parametrize("name", ["../outside.txt", "/absolute.txt", "C:/outside.txt",
                                  "dir\\outside.txt", "dir//alias.txt", "NUL.txt", "."])
def test_unsafe_archive_member_is_rejected_before_extraction(tmp_path, name):
    archive = tmp_path / "unsafe.zip"
    fixture_archive(archive, {name: b"fixture"})
    destination = tmp_path / "fresh"
    with pytest.raises(ValueError, match="Unsafe"):
        verify_archive(archive, extract_to=destination)
    assert not destination.exists()


def test_valid_zip_crc_does_not_hide_manifest_hash_mismatch(tmp_path):
    archive = tmp_path / "wrong-hash.zip"
    fixture_archive(archive, {"value.txt": b"changed"}, manifest_files=[
        {"path": "value.txt", "bytes": 7, "sha256": "0" * 64}])
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_archive(archive)


def test_unmanifested_member_is_rejected(tmp_path):
    archive = tmp_path / "extra.zip"
    fixture_archive(archive, {"private.txt": b"fixture"}, manifest_files=[])
    with pytest.raises(ValueError, match="inventory mismatch"):
        verify_archive(archive)


def test_extracted_model_hash_is_measured_from_written_file(tmp_path, monkeypatch):
    archive = tmp_path / "extract-failure.zip"
    fixture_archive(archive, {"model/P3_Assembly_Flow.alp": b"fixture model"})
    import verify_package
    original_copy = verify_package.shutil.copyfileobj
    def faulty_copy(source, output, length):
        if source.name == "model/P3_Assembly_Flow.alp":
            output.write(b"damaged write")
        else:
            original_copy(source, output, length)
    monkeypatch.setattr(verify_package.shutil, "copyfileobj", faulty_copy)
    with pytest.raises(ValueError, match="Extracted model SHA-256 mismatch"):
        verify_archive(archive, extract_to=tmp_path / "fresh")


def test_crc_corruption_is_rejected_before_extraction(tmp_path):
    archive = tmp_path / "bad-crc.zip"
    payload = b"unique CRC corruption sample"
    fixture_archive(archive, {"value.txt": payload})
    content = bytearray(archive.read_bytes())
    content[content.index(payload)] ^= 1
    archive.write_bytes(content)
    destination = tmp_path / "fresh"
    with pytest.raises(zipfile.BadZipFile, match="CRC"):
        verify_archive(archive, extract_to=destination)
    assert not destination.exists()


def test_symbolic_link_and_case_aliases_are_rejected(tmp_path):
    archive = tmp_path / "symlink.zip"
    link = zipfile.ZipInfo("linked")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(link, "../outside")
        output.writestr("MANIFEST.json", json.dumps({"files": []}))
    with pytest.raises(ValueError, match="Symbolic links"):
        verify_archive(archive)
    fixture_archive(archive, {"Case.txt": b"one", "case.txt": b"two"})
    with pytest.raises(ValueError, match="Case-colliding"):
        verify_archive(archive)


def test_evidence_uses_completed_logs_and_hash_matched_executed_copy(tmp_path):
    root = tmp_path / "p3-assembly-flow-v2"
    logs = root / "results/native/pilot"
    logs.mkdir(parents=True)
    completed = logs / "native-seed-1-scenario-0-finite.log"
    completed.write_text("P3_META,SYNTHETIC\nP3_DONE,1,0,1,1,5,1\n", encoding="utf-8")
    incomplete = logs / "native-seed-2-scenario-0-finite.log"
    incomplete.write_text("P3_META,SYNTHETIC\n", encoding="utf-8")
    model = root / "tools/.build/native/P3V2Pilot01/P3V2Pilot01.alp"
    model.parent.mkdir(parents=True)
    model.write_text("fabricated unit-test model", encoding="utf-8")
    model.with_name("batch-manifest.json").write_text("{}", encoding="utf-8")
    (logs / "launch.json").write_text(json.dumps({"alp": "C:/test/P3V2Pilot01.alp",
        "alp_sha256": sha256_file(model)}), encoding="utf-8")
    reference = tmp_path / "p3-assembly-flow/results/native/confirmation"
    reference.mkdir(parents=True)
    (reference / completed.name).write_text(completed.read_text(), encoding="utf-8")
    files, metadata = evidence_files(root)
    names = {name for _, name in files}
    assert "v2/native/pilot/" + completed.name in names
    assert not any(incomplete.name in name for name in names)
    assert "v2/executed-models/P3V2Pilot01/P3V2Pilot01.alp" in names
    assert metadata["v2_completed_logs"] == metadata["v1_reference_completed_logs"] == 1
    assert len(metadata["incomplete_logs_excluded"]) == 1
    model.write_text("changed after launch", encoding="utf-8")
    with pytest.raises(ValueError, match="changed after launch"):
        evidence_files(root)
