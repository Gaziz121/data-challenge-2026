#!/usr/bin/env python3
"""Build an offline human-review page. Standard library only; no engine imports."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATASET = ROOT / "data/shared/DEV_synthetic_60.json"


def embedded_json(value):
    # JSON script elements are raw text: prevent source text closing the element.
    return json.dumps(value, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def build(output):
    raw = DATASET.read_bytes()
    dataset = json.loads(raw)
    records = dataset["data"]["records"]
    assert dataset["isSuccess"] is True
    assert dataset["data"]["total_records"] == len(records)
    assert len({r["conversation_id"] for r in records}) == len(records)
    for record in records:
        assert isinstance(record["conversation_id"], str)
        assert isinstance(record["language"], str) and isinstance(record["channel"], str)
        assert isinstance(record["transcript"], list)
        for message in record["transcript"]:
            assert isinstance(message["text"], str) and isinstance(message["speaker"], str)
    rubric_raw = (HERE / "rubric.json").read_bytes()
    payload = {
        "source": {"path": "data/shared/DEV_synthetic_60.json", "sha256": hashlib.sha256(raw).hexdigest(),
                   "dataset_group_id": dataset["data"]["dataset_group_id"], "record_count": len(records)},
        "rubric": json.loads(rubric_raw),
        "rubric_sha256": hashlib.sha256(rubric_raw).hexdigest(),
        "records": records,
    }
    html = (HERE / "viewer.html").read_text(encoding="utf-8")
    html = html.replace("/* REVIEW_SCRIPT */", (HERE / "viewer.js").read_text(encoding="utf-8"))
    html = html.replace("<!-- REVIEW_DATA -->", embedded_json(payload))
    output = Path(output).resolve()
    # Keep generated output in its own directory, never overwrite inputs or source.
    if output.suffix != ".html" or ROOT / "outputs/dev_review" not in output.parents:
        raise ValueError("Output must be an .html file under outputs/dev_review/")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    print(f"Built {output} ({len(records)} conversations; dataset SHA256 {payload['source']['sha256']})")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/dev_review/index.html")
    args = parser.parse_args()
    build(args.output)
