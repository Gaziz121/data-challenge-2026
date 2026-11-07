"""Evidence that defect family QA-D02 is fixable by checklist CONFIGURATION alone.

The rules below are a QA proposal, built in memory only. The saved checklist
`src/cqa/checklists/official-v1.json` is NOT modified. Adoption is the engine
owner's decision and would need a new checklist version. Permitted sets keep
N/A where the criterion allows it, so the rules never force a non-N/A answer.
"""

import unittest

from cqa.engine import evaluate
from cqa.io import load_checklist
from cqa.loader import SHARED, load_conversation, read_dataset
from cqa.providers import MockProvider
from cqa.schemas import Checklist
from cqa.validation import validate_evaluation
from qa.fixtures import GATES_EN, as_model, decision, make_conversation, set_atomic, valid_raw

PROPOSED_RULES = {
    # criterion: [(question, when_answer, permitted responses), ...]
    "02": [("02.q2", "no", ["no", "N/A"])],
    "03": [("03.q2", "no", ["no", "N/A"])],
    "04": [("04.q2", "no", [0, 5, 10, "N/A"]), ("04.q3", "no", [0, "N/A"])],
    "05": [("05.q1", "no", ["no"]), ("05.q2", "no", ["no"])],
    "06": [("06.q1", "no", [0, 4, 7]), ("06.q2", "yes", [0, 4]), ("06.q3", "no", [0, 4, 7])],
    "07": [("07.q2", "no", ["no", "N/A"]), ("07.q3", "no", ["no", "N/A"])],
}


def proposed_checklist():
    value = load_checklist().model_dump()
    value["version"] = value["version"] + "+qa-proposal"
    for criterion in value["criteria"]:
        for qid, when, permitted in PROPOSED_RULES.get(criterion["criterion_id"], []):
            criterion["consistency_rules"].append(
                {"question_id": qid, "when_answer": when, "permitted_responses": permitted})
    return Checklist.model_validate(value)


class ProposedConfigFixTests(unittest.TestCase):
    def setUp(self):
        self.checklist = proposed_checklist()
        self.conv = make_conversation(GATES_EN)

    def validate(self, raw):
        return validate_evaluation(as_model(raw), self.conv, self.checklist)

    def test_d02_mutations_rejected_under_proposed_rules(self):
        mutations = {"d02a": [("03.q1", "yes"), ("03.q2", "no")], "d02b": [("07.q3", "no")],
                     "d02c": [("04.q2", "no")], "d02d": [("04.q3", "no")], "d02e": [("05.q1", "no")],
                     "d02f": [("06.q2", "yes")], "d02g": [("02.q2", "no")]}
        for name, changes in mutations.items():
            raw = valid_raw(self.conv, self.checklist)
            for qid, answer in changes:
                set_atomic(raw, qid, answer)
            with self.subTest(defect=name), self.assertRaisesRegex(ValueError, "consistency"):
                self.validate(raw)

    def test_compliant_and_correct_downgrades_still_accepted(self):
        self.validate(valid_raw(self.conv, self.checklist))
        cases = [("03", "no", [("03.q2", "no")]), ("07", "no", [("07.q3", "no")]),
                 ("04", 10, [("04.q2", "no")]), ("04", 0, [("04.q3", "no")]),
                 ("06", 4, [("06.q2", "yes")]), ("05", "no", [("05.q1", "no")])]
        for cid, response, changes in cases:
            raw = valid_raw(self.conv, self.checklist)
            decision(raw, cid)["response"] = response
            for qid, answer in changes:
                set_atomic(raw, qid, answer)
            with self.subTest(criterion=cid, response=response):
                self.validate(raw)

    def test_na_paths_still_accepted(self):
        for cid, trigger, extra in [("02", ("02.q1", "yes"), ("02.q2", "not_applicable")),
                                    ("03", ("03.q1", "no"), ("03.q2", "no")),
                                    ("04", ("04.q1", "no"), ("04.q2", "no")),
                                    ("07", ("07.q1", "yes"), ("07.q3", "no"))]:
            raw = valid_raw(self.conv, self.checklist)
            decision(raw, cid).update(response="N/A", na_reason="QA fixture: allowed N/A condition holds.")
            set_atomic(raw, *trigger)
            set_atomic(raw, *extra)
            with self.subTest(criterion=cid):
                self.validate(raw)

    def test_mock_pipeline_unaffected_on_all_shared_chats(self):
        data, _ = read_dataset(SHARED)
        for record in data["records"]:
            result = evaluate(load_conversation(SHARED, record["conversation_id"]), self.checklist, MockProvider())
            self.assertEqual(result.status, "mock_only")


if __name__ == "__main__":
    unittest.main()
