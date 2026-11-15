"""Record exactly which data the results come from: snapshot, hashes, row counts, sample parameters.

Usage: uv run python -m sourced.manifest   -> results/data_manifest.json (committed; data/ is not)
"""

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from sourced import sample

SNAPSHOT = "2026/11/15"
SNAPSHOT_URL = "https://ton.twimg.com/birdwatch-public-data/" + SNAPSHOT + "/{table}/{table}-00000.zip"
FILES = [
    "data/raw/notes-00000.tsv",
    "data/raw/noteStatusHistory-00000.tsv",
    "data/raw/userEnrollment-00000.tsv",
    "data/processed/sample_notes.csv",
    "data/processed/sample_links.csv",
    "data/processed/links.jsonl",
]


def describe(path: Path) -> dict:
    digest, lines = hashlib.sha256(), 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
            lines += chunk.count(b"\n")
    return {"path": str(path), "bytes": path.stat().st_size, "lines": lines, "sha256": digest.hexdigest()}


def main() -> None:
    manifest = {
        "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "snapshot": SNAPSHOT,
        "snapshot_url_pattern": SNAPSHOT_URL,
        "sample_params": {k: getattr(sample, k) for k in
                          ("SINCE", "N_PAIRS", "N_CONTRAST_EACH", "MAX_LINKS_PER_NOTE", "SEED")},
        "python": platform.python_version(),
        "files": [describe(Path(p)) for p in FILES if Path(p).exists()],
    }
    out = Path("results/data_manifest.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {out} ({len(manifest['files'])} files)")


if __name__ == "__main__":
    main()
