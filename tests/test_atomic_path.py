"""Atomic-first offline regressions. Scripted facts are not accuracy labels."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from cqa.engine import EvaluationRejected, evaluate
from cqa.io import digest, load_checklist
from cqa.loader import ROOT, SHARED, load_conversation, normalize_record
from cqa.prompt import build_request
from cqa.providers import MockProvider, OpenAIProvider, ProviderReply
from cqa.schemas import Checklist, EvaluationConfig, EvaluationResult
from tests.helpers import conversation


def atomic_checklist():
    return load_checklist(ROOT / "src/cqa/checklists/official-v4.json")


def quote(message):
    return {"kind": "quote", "message_id": message.message_id, "quote": message.text,
            "start_message_id": None, "end_message_id": None, "explanation": "Offline fixture quote."}


def scope(conv):
    return {"kind": "scope", "message_id": None, "quote": None,
            "start_message_id": conv.messages[0].message_id, "end_message_id": conv.messages[-1].message_id,
            "explanation": "Offline fixture: full source scope inspected."}


def raw_fixture(conv, checklist):
    agent = next(m for m in conv.messages if m.role == "agent")
    criteria = []
    for c in checklist.criteria:
        checks = []
        for q in c.questions:
            answer = "no" if c.kind == "critical" else "yes"
            if q.question_id in ("02.q2", "03.q2", "05.q2", "06.q3"):
                answer = "not_applicable"
            if q.question_id in ("03.q1", "05.q3", "06.q2", "07.q1"):
                answer = "no"
            allowed = q.fact_policy.yes_roles if q.fact_policy and q.fact_policy.yes_roles else ["agent"]
            message = next((m for m in conv.messages if m.role in allowed), agent)
            checks.append({"question_id": q.question_id, "answer": answer, "rationale": "Offline hand-authored fact fixture.",
                           "evidence": [scope(conv), quote(message)], "events": []})
        na = c.applicability_rule and next(a for a in checks if a["question_id"] == c.applicability_rule.question_id)["answer"] == c.applicability_rule.na_when
        judgment = None if c.output_source == "atomic" or na else {
            "response": max(c.levels) if c.kind == "discrete" else "yes", "rationale": "Offline discretionary anchor fixture.",
            "evidence": [quote(agent)], "violation_categories": [], "needs_review": False, "review_reason": None}
        criteria.append({"criterion_id": c.criterion_id, "atomic_checks": checks, "judgment": judgment})
    return {"schema_version": "1.2", "criteria": criteria}


class Scripted(MockProvider):
    def __init__(self, raw):
        self.raw = deepcopy(raw)

    def evaluate(self, *args):
        return ProviderReply(deepcopy(self.raw), model="offline-atomic-fixture")


def decision(raw, cid):
    return next(c for c in raw["criteria"] if c["criterion_id"] == cid)


def fact(raw, qid):
    return next(a for c in raw["criteria"] for a in c["atomic_checks"] if a["question_id"] == qid)


class AtomicHelpers(unittest.TestCase):
    def setUp(self):
        self.conv, self.checklist = conversation(), atomic_checklist()
        self.raw = raw_fixture(self.conv, self.checklist)

    def reject(self, raw=None, conv=None):
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(conv or self.conv, self.checklist, Scripted(raw or self.raw))
        diagnostic = caught.exception.diagnostic
        self.assertNotIn("score", diagnostic)
        return diagnostic


class AtomicPathTests(AtomicHelpers):
    def test_atomic_mode_derives_without_redundant_model_response(self):
        before = deepcopy(self.raw)
        result = evaluate(self.conv, self.checklist, Scripted(self.raw))
        self.assertEqual(result.original_provider_output, before)
        self.assertEqual(self.raw, before)
        responses = {d.criterion_id: d.response for d in result.validated_evaluation.decisions}
        self.assertEqual(responses, {"01": "yes", "02": "N/A", "03": "N/A", "04": 20, "05": "yes", "06": 10, "07": "yes", "08": "no"})
        self.assertEqual(result.score.total_score, "100.00")
        self.assertEqual(result.score.applicable_weight, 65)
        self.assertEqual(result.run.configuration.prompt_version, "atomic-v1")
        self.assertEqual(result.decision_path, "atomic_first")
        self.assertEqual(result.decision_rule_checks, [])  # No tautological model/derived comparison.
        self.assertTrue(all(r.state.startswith("accepted_") for r in result.criterion_reviews))
        self.assertEqual(EvaluationResult.model_validate_json(result.model_dump_json()), result)

    def test_unsolicited_atomic_judgment_is_preserved_as_conflict(self):
        judgment = deepcopy(decision(self.raw, "07")["judgment"])
        judgment["response"] = "no"
        decision(self.raw, "05")["judgment"] = judgment
        diagnostic = self.reject()
        review = next(r for r in diagnostic["criterion_reviews"] if r["criterion_id"] == "05")
        self.assertEqual(review["state"], "conflict")
        self.assertEqual(review["original_judgment"], judgment)
        self.assertEqual(diagnostic["original_model_output"], self.raw)
        self.assertEqual(len(diagnostic["validated_criteria"]), 7)

    def test_one_bad_fact_retains_other_review_states_without_total(self):
        fact(self.raw, "05.q1")["evidence"] = [quote(self.conv.messages[0])]
        diagnostic = self.reject()
        states = {r["criterion_id"]: r["state"] for r in diagnostic["criterion_reviews"]}
        self.assertEqual(states["05"], "invalid_facts")
        self.assertEqual(sum(v.startswith("accepted_") for v in states.values()), 7)
        self.assertTrue(any("eligible source role" in i["message"] for i in diagnostic["issues"]))

    def test_unknown_and_schema_error_are_independent_criterion_states(self):
        fact(self.raw, "05.q1")["answer"] = "unknown"
        del fact(self.raw, "01.q1")["events"]
        diagnostic = self.reject()
        states = {r["criterion_id"]: r["state"] for r in diagnostic["criterion_reviews"]}
        self.assertEqual(states["05"], "needs_review")
        self.assertEqual(states["01"], "schema_invalid")
        self.assertEqual(states["04"], "accepted_model")

    def test_discretionary_scales_are_not_derived_from_atomic_answers(self):
        decision(self.raw, "04")["judgment"]["response"] = 15
        decision(self.raw, "06")["judgment"]["response"] = 7
        result = evaluate(self.conv, self.checklist, Scripted(self.raw))
        self.assertEqual([d.response for d in result.validated_evaluation.decisions if d.criterion_id in ("04", "06")], [15, 7])
        decision(self.raw, "04")["judgment"]["needs_review"] = True
        decision(self.raw, "04")["judgment"]["review_reason"] = "Factual policy unresolved in offline scenario."
        self.assertEqual(next(r for r in self.reject()["criterion_reviews"] if r["criterion_id"] == "04")["state"], "needs_review")

    def test_applicability_owned_by_backend_including_discretionary_criteria(self):
        fact(self.raw, "07.q1")["answer"] = "yes"
        decision(self.raw, "07")["judgment"] = None
        result = evaluate(self.conv, self.checklist, Scripted(self.raw))
        self.assertEqual(next(d.response for d in result.validated_evaluation.decisions if d.criterion_id == "07"), "N/A")
        decision(self.raw, "04")["judgment"]["response"] = "N/A"
        self.assertEqual(next(r for r in self.reject()["criterion_reviews"] if r["criterion_id"] == "04")["state"], "schema_invalid")

    def test_wire_schema_forbids_redundant_decisions_and_na_reason(self):
        request, _ = build_request(self.conv, self.checklist)
        branches = request["schema"]["properties"]["criteria"]["items"]["anyOf"]
        for branch, c in zip(branches, self.checklist.criteria):
            if c.output_source == "atomic":
                self.assertEqual(branch["properties"]["judgment"], {"type": "null"})
            self.assertLess(list(branch["properties"]).index("atomic_checks"), list(branch["properties"]).index("judgment"))
        self.assertNotIn("na_reason", request["schema"]["$defs"]["ApplicableJudgment"]["properties"])
        self.assertEqual(request["schema"]["properties"]["schema_version"]["const"], "1.2")

    def test_unseen_languages_and_new_configured_criterion(self):
        from tests.test_control_backend import supplied
        for lang in ("RU", "KZ", "EN"):
            value = supplied(lang)
            conv = normalize_record(value["record"], value["dataset_group_id"], digest(value))
            result = evaluate(conv, self.checklist, Scripted(raw_fixture(conv, self.checklist)))
            self.assertEqual(result.conversation.messages[0].text, value["record"]["transcript"][0]["text"])
        value = self.checklist.model_dump()
        new = deepcopy(value["criteria"][0]); new["criterion_id"] = "organizer-added"
        mapping = {q["question_id"]: "new-" + str(i) for i, q in enumerate(new["questions"])}
        for q in new["questions"]:q["question_id"] = mapping[q["question_id"]]
        new["decision_rule"]["all_of"] = [mapping[q] for q in new["decision_rule"]["all_of"]]
        for r in new["consistency_rules"]:r["question_id"] = mapping[r["question_id"]]
        value["criteria"].append(new);value["version"] = "atomic-new-criterion"
        checklist = Checklist.model_validate(value)
        result = evaluate(self.conv, checklist, Scripted(raw_fixture(self.conv, checklist)))
        self.assertEqual(len(result.validated_evaluation.decisions), 9)

    def test_atomic_mode_mock_requests_review_without_a_fake_total(self):
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, MockProvider())
        self.assertTrue(all(r["state"] == "needs_review" for r in caught.exception.diagnostic["criterion_reviews"]))
        self.assertNotIn("score", caught.exception.diagnostic)

    def test_real_adapter_offline_atomic_schema_and_single_transport(self):
        conv = load_conversation(SHARED, "p1-ru-001"); raw = raw_fixture(conv, self.checklist);calls=[]
        def transport(payload, timeout):
            calls.append(payload)
            self.assertEqual(payload["text"]["format"]["name"], "cqa_atomic_v1_2")
            return {"id":"offline-only", "status":"completed", "model":"offline-model",
                    "output":[{"content":[{"type":"output_text", "text":json.dumps(raw)}]}]}
        result = evaluate(conv, self.checklist, OpenAIProvider("offline-model", api_key="offline-placeholder", transport=transport),
                          EvaluationConfig(external_synthetic_allowed=True))
        self.assertEqual(len(calls), 1)
        self.assertEqual(result.original_provider_output, raw)


class IdentificationTests(AtomicHelpers):
    def setUp(self):
        turns = [("client", "What is my account balance?"), ("operator", "Hello, I am Sam. Please verify your identity."),
                 ("system", "Customer identity verified."), ("operator", "Your account balance is 100 USD. Goodbye.")]
        record = {"conversation_id":"protected-offline", "channel":"agent chat", "language":"EN", "audio_url":None,
                  "transcript":[{"speaker":s,"timestamp":f"00:0{i}","text":t} for i,(s,t) in enumerate(turns)]}
        self.conv=normalize_record(record,"OFFLINE",digest(record));self.checklist=atomic_checklist()
        self.raw=raw_fixture(self.conv,self.checklist)
        need, verified=fact(self.raw,"03.q1"),fact(self.raw,"03.q2")
        need.update(answer="yes", evidence=[scope(self.conv),quote(self.conv.messages[0]),quote(self.conv.messages[3])],
                    events=[{"kind":"protected_request","message_id":"m0000","quote":self.conv.messages[0].text},
                            {"kind":"protected_action","message_id":"m0003","quote":self.conv.messages[3].text}])
        verified.update(answer="yes", evidence=[scope(self.conv),quote(self.conv.messages[2])],
                        events=[{"kind":"verification","message_id":"m0002","quote":self.conv.messages[2].text}])

    def test_confirmed_before_action_accepts_system_and_agent_evidence(self):
        for role in ("system","agent"):
            conv=self.conv.model_copy(deep=True);conv.messages[2]=conv.messages[2].model_copy(update={"role":role})
            result=evaluate(conv,self.checklist,Scripted(self.raw))
            self.assertEqual(next(d.response for d in result.validated_evaluation.decisions if d.criterion_id=="03"),"yes")

    def test_customer_bot_or_unquoted_confirmation_cannot_authorize_positive(self):
        for role in ("customer","bot"):
            conv=self.conv.model_copy(deep=True);conv.messages[2]=conv.messages[2].model_copy(update={"role":role})
            self.assertTrue(any("ineligible source role" in i["message"] for i in self.reject(conv=conv)["issues"]))
        fact(self.raw,"03.q2")["events"][0]["quote"]="Unquoted fabricated confirmation"
        self.reject()

    def test_late_same_turn_or_missing_confirmation_is_never_positive(self):
        for index in (3,):
            raw=deepcopy(self.raw);v=fact(raw,"03.q2")
            v["events"][0].update(message_id=f"m{index:04d}",quote=self.conv.messages[index].text)
            v["evidence"].append(quote(self.conv.messages[index]))
            self.assertTrue(any("precede every protected action" in i["message"] for i in self.reject(raw)["issues"]))
        fact(self.raw,"03.q2")["events"]=[]
        self.reject()
        fact(self.raw,"03.q2")["answer"]="no"
        result=evaluate(self.conv,self.checklist,Scripted(self.raw))
        self.assertEqual(next(d.response for d in result.validated_evaluation.decisions if d.criterion_id=="03"),"no")

    def test_one_early_protected_action_cannot_hide_behind_a_later_valid_action(self):
        conv=self.conv.model_copy(deep=True)
        conv.messages[1]=conv.messages[1].model_copy(update={"text":"Hello, I am Sam. Your balance is 100 USD. Please verify your identity."})
        raw=raw_fixture(conv,self.checklist)
        need,verified=fact(raw,"03.q1"),fact(raw,"03.q2")
        need.update(answer="yes",evidence=[scope(conv),quote(conv.messages[0]),quote(conv.messages[1]),quote(conv.messages[3])],
                    events=[{"kind":"protected_request","message_id":"m0000","quote":conv.messages[0].text},
                            {"kind":"protected_action","message_id":"m0001","quote":conv.messages[1].text},
                            {"kind":"protected_action","message_id":"m0003","quote":conv.messages[3].text}])
        verified.update(answer="yes",evidence=[scope(conv),quote(conv.messages[2])],
                        events=[{"kind":"verification","message_id":"m0002","quote":conv.messages[2].text}])
        self.assertTrue(any("precede every protected action" in i["message"] for i in self.reject(raw,conv)["issues"]))

    def test_protected_action_need_and_coverage_are_independently_checked(self):
        raw=deepcopy(self.raw);fact(raw,"03.q1")["answer"]="no";fact(raw,"03.q2")["answer"]="not_applicable"
        self.assertTrue(any("unnecessary conflicts" in i["message"] for i in self.reject(raw)["issues"]))
        raw=deepcopy(self.raw);fact(raw,"03.q1")["events"]=[fact(raw,"03.q1")["events"][0]]
        self.assertTrue(any("relevant protected action" in i["message"] for i in self.reject(raw)["issues"]))
        raw=raw_fixture(self.conv,self.checklist);fact(raw,"03.q1")["evidence"]=[quote(self.conv.messages[0])]
        self.assertTrue(any("full-dialogue" in i["message"] for i in self.reject(raw)["issues"]))


class ThreeLiveReplayTests(unittest.TestCase):
    def test_all_three_original_runs_stay_rejected_and_raw_judgments_retained(self):
        folder=Path(__file__).parent/"fixtures";conv=load_conversation(SHARED,"p1-ru-001")
        for filename,version,expected in [("live_first.json","v2",{"02","04","07"}),
                                          ("live_c379231.json","v2",{"05","08"}),
                                          ("live_f4599f0.json","v3",{"03"})]:
            raw=json.loads((folder/filename).read_text())["original_model_output"]
            with self.subTest(filename=filename),self.assertRaises(EvaluationRejected) as caught:
                evaluate(conv,load_checklist(ROOT/f"src/cqa/checklists/official-{version}.json"),Scripted(raw))
            self.assertEqual({i["criterion_id"] for i in caught.exception.diagnostic["issues"]},expected)
            self.assertEqual(caught.exception.diagnostic["original_model_output"],raw)
            self.assertNotIn("score",caught.exception.diagnostic)
            with self.assertRaises(EvaluationRejected):
                evaluate(conv,atomic_checklist(),Scripted(raw))  # No silent migration into accepted atomic facts.
