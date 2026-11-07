"""Dataset fidelity checks, independent of the production evaluation engine."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dev_review_build", ROOT / "tools/dev_review/build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class DevReviewFidelity(unittest.TestCase):
    def test_all_records_and_messages_preserved(self):
        source = ROOT / "data/shared/DEV_synthetic_60.json"
        before = source.read_bytes()
        (ROOT / "outputs/dev_review").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs/dev_review") as directory:
            output = Path(directory) / "index.html"
            builder.build(output)
            html = output.read_text(encoding="utf-8")
        embedded = html.split('<script type="application/json" id="review-data">', 1)[1].split('</script>', 1)[0]
        data = json.loads(embedded)
        records = json.loads(before)["data"]["records"]
        self.assertEqual(data["records"], records)  # Includes wording, order, metadata and empty fields.
        self.assertEqual(len(records), 60)
        self.assertEqual(sum(len(r["transcript"]) for r in records), 882)
        self.assertEqual(data["source"]["sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(source.read_bytes(), before)
        for language in ("RU", "KZ", "EN"):
            self.assertTrue(any(r["language"] == language for r in data["records"]))
        self.assertTrue(all(set(m) == {"speaker", "timestamp", "text"} for r in records for m in r["transcript"]))

    def test_script_terminators_are_safely_embedded(self):
        value = {"text": '</script><script>alert("x")</script> & Kazakh: Ә і ң ғ ү ұ қ ө һ\n  spaces'}
        encoded = builder.embedded_json(value)
        self.assertNotIn("<", encoded)
        self.assertEqual(json.loads(encoded), value)

    def test_input_cannot_be_output(self):
        with self.assertRaises(ValueError):
            builder.build(ROOT / "data/shared/DEV_synthetic_60.json")


if __name__ == "__main__":
    unittest.main()
