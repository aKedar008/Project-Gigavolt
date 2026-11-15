from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path.home() / "gigavolt-milestone6"
MANIFEST_PATH = ROOT / "state" / "manifest.json"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def load_manifest():
    if not MANIFEST_PATH.exists():
        return {
            "version": 1,
            "files": {}
        }

    return json.loads(
        MANIFEST_PATH.read_text()
    )


def save_manifest(manifest):
    temp_path = MANIFEST_PATH.with_suffix(".json.tmp")

    temp_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True
        ) + "\n"
    )

    temp_path.replace(MANIFEST_PATH)


def relative_name(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def check_file(path: Path):
    path = path.resolve()

    if not path.exists():
        raise FileNotFoundError(path)

    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    manifest = load_manifest()
    key = relative_name(path)

    current_hash = sha256_file(path)
    previous = manifest["files"].get(key)

    if previous is None:
        status = "NEW"

    elif previous.get("sha256") == current_hash:
        status = "UNCHANGED"

    else:
        status = "CHANGED"

    return {
        "path": key,
        "sha256": current_hash,
        "status": status,
        "previous": previous
    }


def mark_processed(path: Path, stage="processed"):
    path = path.resolve()

    manifest = load_manifest()
    key = relative_name(path)

    current_hash = sha256_file(path)

    manifest["files"][key] = {
        "sha256": current_hash,
        "status": "SUCCESS",
        "stage": stage,
        "processed_at_utc": utc_now(),
        "size_bytes": path.stat().st_size
    }

    save_manifest(manifest)

    return manifest["files"][key]


def mark_failed(path: Path, error: str, stage="unknown"):
    path = path.resolve()

    manifest = load_manifest()
    key = relative_name(path)

    current_hash = (
        sha256_file(path)
        if path.exists()
        else None
    )

    manifest["files"][key] = {
        "sha256": current_hash,
        "status": "FAILED",
        "stage": stage,
        "failed_at_utc": utc_now(),
        "error": str(error)
    }

    save_manifest(manifest)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Milestone 6 incremental file manifest"
    )

    parser.add_argument(
        "file",
        type=Path
    )

    parser.add_argument(
        "--mark-success",
        action="store_true"
    )

    parser.add_argument(
        "--stage",
        default="manual-test"
    )

    args = parser.parse_args()

    result = check_file(args.file)

    print(
        json.dumps(
            result,
            indent=2,
            default=str
        )
    )

    if args.mark_success:
        saved = mark_processed(
            args.file,
            stage=args.stage
        )

        print("\nManifest updated:")
        print(
            json.dumps(
                saved,
                indent=2
            )
        )
