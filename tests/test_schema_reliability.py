"""atomic-v3 schema completeness, bounded repair and adversarial regressions.

Every model output here is either the verbatim saved genuine reply or a
hand-authored/scripted offline fixture. None is a model accuracy measurement,
official Ground Truth or a team_human label. No network calls are made.
"""

from copy import deepcopy
from itertools import product
import json
from pathlib import Path
import unittest

from cqa.atomic import AtomicReviewRequired, process_atomic_output
from cqa.atomic_prompt import ANSWERS, _full_scope_answers, compile_atomic_schema
from cqa.engine import EvaluationRejected, evaluate
from cqa.io import digest, load_checklist
from cqa.loader import SHARED, load_conversation, normalize_record
from cqa.prompt import build_request
from cqa.providers import OpenAIProvider, ProviderError, ProviderReply
from cqa.repair import build_repair_request
from cqa.schemas import EvaluationConfig, EvaluationResult, RepairPolicy
from cqa.strict_schema import conforms, strict_issues
from tests.test_atomic_path import Scripted, atomic_checklist, decision, fact, quote, raw_fixture, scope

FIXTURES = Path(__file__).parent / "fixtures"
V2_P1_RU_001_SHA = "9f5bcb6512eb35433a5590b15cd6f47ad59661ef0b052f9cc629a4ccd055cdad"
V3 = EvaluationConfig(prompt_version="atomic-v3")
STRUCTURAL = ("full-dialogue source coverage", "Configured rule cannot derive a decision", "requires its original model judgment",
              "supplied for a backend-derived decision", "must be not_applicable when identification is unnecessary",
              "cannot use not_applicable for verification", "conditional obligation",
              "contradicts a configured atomic consistency rule", "never not_applicable")
# The single documented residual: identification verified=no keeps quotes beside its
# scope (events need them), so its coverage stays validator-enforced (and repairable).
RESIDUAL = "Missing/late verification requires full-dialogue source coverage"


def genuine():
    return json.loads((FIXTURES / "live_atomic_5d256ac.json").read_text())["original_model_output"]


def branches(schema):
    return schema["properties"]["criteria"]["items"]["anyOf"]


def entry_conforms(entry, schema):
    return any(conforms(entry, b, schema) for b in branches(schema))


def record(turns, cid="offline", language="EN"):
    value = {"conversation_id": cid, "channel": "agent chat", "language": language, "audio_url": None,
             "transcript": [{"speaker": s, "timestamp": f"00:{i:02d}", "text": t} for i, (s, t) in enumerate(turns)]}
    return normalize_record(value, "OFFLINE", digest(value))


def full_scope_normalized(entry, criterion):
    """The one documented narrowing: absence answers cite only the full scope."""
    entry = deepcopy(entry)
    policy = criterion.identification_policy
    for a in entry["atomic_checks"]:
        if a["answer"] in _full_scope_answers(criterion, a["question_id"]) and not (
                policy and a["question_id"] == policy.verified_question_id):
            a["evidence"] = [e for e in a["evidence"] if e["kind"] == "scope"]
    return entry


def enumerate_entries(conv, criterion):
    """Every answer combination x evidence mode x judgment option for one criterion."""
    first_agent = next(m for m in conv.messages if m.role == "agent")
    for answers in product(ANSWERS, repeat=len(criterion.questions)):
        for mode in ("scope", "quote", "both"):
            checks = []
            for q, answer in zip(criterion.questions, answers):
                roles = q.fact_policy.yes_roles if q.fact_policy and q.fact_policy.yes_roles else ["agent"]
                message = first_agent if q.fact_policy and q.fact_policy.yes_locator == "first_agent" else next(
                    (m for m in conv.messages if m.role in roles), first_agent)
                evidence = {"scope": [scope(conv)], "quote": [quote(message)], "both": [scope(conv), quote(message)]}[mode]
                checks.append({"question_id": q.question_id, "answer": answer, "rationale": "Enumerated fixture.",
                               "evidence": evidence, "events": []})
            options = [None]
            if criterion.output_source == "model":
                options += [{"response": r, "rationale": "Enumerated anchor fixture.", "evidence": [quote(first_agent)],
                             "violation_categories": [], "needs_review": False, "review_reason": None}
                            for r in (criterion.levels if criterion.kind == "discrete" else ["yes", "no"])]
            for judgment in options:
                yield {"criterion_id": criterion.criterion_id, "atomic_checks": deepcopy(checks), "judgment": judgment}


def criterion_review(raw, conv, checklist, cid):
    try:
        _, reviews = process_atomic_output(raw, conv, checklist)
    except AtomicReviewRequired as error:
        reviews = error.reviews
    return next(r for r in reviews if r.criterion_id == cid)


class SchemaCompilerTests(unittest.TestCase):
    def setUp(self):
        self.conv, self.checklist = load_conversation(SHARED, "p1-ru-001"), atomic_checklist()

    def test_v2_default_request_is_byte_identical_to_integration_baseline(self):
        request, sha = build_request(self.conv, self.checklist)
        self.assertEqual(sha, V2_P1_RU_001_SHA)
        result = evaluate(self.conv, self.checklist, Scripted(raw_fixture(self.conv, self.checklist)))
        self.assertEqual(result.run.configuration.prompt_version, "atomic-v2")
        self.assertEqual(result.run.prompt_sha256, V2_P1_RU_001_SHA)

    def test_v3_changes_only_schema_and_declared_version(self):
        v2, _ = build_request(self.conv, self.checklist)
        v3, sha = build_request(self.conv, self.checklist, prompt_version="atomic-v3")
        self.assertNotEqual(sha, V2_P1_RU_001_SHA)
        self.assertEqual(v2["instructions"], v3["instructions"])
        p2, p3 = json.loads(v2["input"]), json.loads(v3["input"])
        self.assertEqual((p2.pop("prompt_version"), p3.pop("prompt_version")), ("atomic-v2", "atomic-v3"))
        self.assertEqual(p2, p3)
        with self.assertRaises(ValueError):
            build_request(self.conv, self.checklist, prompt_version="atomic-v9")

    def test_genuine_atomic_reply_was_permitted_by_v2_and_is_unrepresentable_in_v3(self):
        raw = genuine()
        v2 = build_request(self.conv, self.checklist)[0]["schema"]
        v3 = build_request(self.conv, self.checklist, prompt_version="atomic-v3")[0]["schema"]
        self.assertTrue(conforms(raw, v2))  # Root cause: every observed failure was legal output.
        self.assertFalse(conforms(raw, v3))
        invalid = {c["criterion_id"] for c in raw["criteria"] if not entry_conforms(c, v3)}
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, Scripted(raw), V3)
        self.assertEqual(invalid, {i["criterion_id"] for i in caught.exception.diagnostic["issues"]})
        self.assertEqual(invalid, {"03", "05", "07"})

    def test_strict_subset_and_published_limits_across_dev_long_and_new_criteria(self):
        records = json.loads(Path(SHARED).read_text())["data"]["records"]
        conversations = [load_conversation(SHARED, r["conversation_id"]) for r in records]
        filler = [("client", "Hello?")] + [("bot" if i % 3 else "client", f"Unrelated turn {i}.") for i in range(396)]
        conversations.append(record(filler + [("operator", "Hello, I am Sam. Goodbye."), ("client", "Bye.")], "long-400"))
        value = self.checklist.model_dump()
        new = deepcopy(value["criteria"][6]); new["criterion_id"] = "organizer-added"
        value["criteria"].append(new); value["version"] = "offline-new-criterion"
        extended = type(self.checklist).model_validate(value)
        for conv in conversations:
            for checklist in (self.checklist, extended):
                schema = compile_atomic_schema(conv, checklist)
                self.assertEqual(strict_issues(schema), [], conv.conversation_id)
        self.assertEqual(len(conversations), 61)

    def test_soundness_and_structural_completeness_by_exhaustive_enumeration(self):
        """Validator-accepted => v3-representable; v3-representable => no structural class."""
        conv = self.conv
        schema = compile_atomic_schema(conv, self.checklist)
        base = raw_fixture(conv, self.checklist)
        accepted = representable = blocked = 0
        for criterion in self.checklist.criteria:
            for entry in enumerate_entries(conv, criterion):
                raw = deepcopy(base)
                raw["criteria"] = [entry if c["criterion_id"] == criterion.criterion_id else c for c in raw["criteria"]]
                review = criterion_review(raw, conv, self.checklist, criterion.criterion_id)
                ok = entry_conforms(entry, schema)
                if review.state.startswith("accepted_"):
                    accepted += 1
                    self.assertTrue(entry_conforms(full_scope_normalized(entry, criterion), schema),
                                    (criterion.criterion_id, entry))
                if ok:
                    representable += 1
                    hits = [i for i in review.issues if any(s in i for s in STRUCTURAL) and i != RESIDUAL]
                    self.assertEqual(hits, [], (criterion.criterion_id, entry))
                elif any(any(s in i for s in STRUCTURAL) for i in review.issues):
                    blocked += 1
        self.assertGreater(accepted, 100)
        self.assertGreater(blocked, 1000)
        self.assertGreater(representable, accepted)

    def test_identification_fixtures_remain_representable_and_ordering_stays_validator_owned(self):
        from tests.test_atomic_path import IdentificationTests
        case = IdentificationTests(); case.setUp()
        schema = compile_atomic_schema(case.conv, case.checklist)
        for c in case.raw["criteria"]:
            criterion = next(x for x in case.checklist.criteria if x.criterion_id == c["criterion_id"])
            self.assertTrue(entry_conforms(full_scope_normalized(c, criterion), schema), c["criterion_id"])
        late = deepcopy(case.raw); v = fact(late, "03.q2")
        v["events"][0].update(message_id="m0003", quote=case.conv.messages[3].text)
        v["evidence"].append(quote(case.conv.messages[3]))
        self.assertTrue(entry_conforms(decision(late, "03"), schema))  # Chronology is not schema-encodable.
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(case.conv, case.checklist, Scripted(late), V3)
        self.assertTrue(any("precede every protected action" in i["message"] for i in caught.exception.diagnostic["issues"]))

    def test_provider_binds_requested_prompt_version(self):
        raw = raw_fixture(self.conv, self.checklist); calls = []
        for entry in raw["criteria"]:
            criterion = next(x for x in self.checklist.criteria if x.criterion_id == entry["criterion_id"])
            entry.update(full_scope_normalized(entry, criterion))

        def transport(payload, timeout):
            calls.append(payload)
            return {"id": "offline", "status": "completed", "model": "offline-model",
                    "output": [{"content": [{"type": "output_text", "text": json.dumps(raw)}]}]}
        provider = OpenAIProvider("offline-model", api_key="offline-placeholder", transport=transport)
        config = EvaluationConfig(prompt_version="atomic-v3", external_synthetic_allowed=True)
        result = evaluate(self.conv, self.checklist, provider, config)
        self.assertEqual(result.score.total_score, "100.00")
        self.assertEqual(calls[0]["text"]["format"]["schema"], compile_atomic_schema(self.conv, self.checklist))
        v2_request, _ = build_request(self.conv, self.checklist)
        with self.assertRaises(ProviderError):
            provider.evaluate(self.conv, self.checklist, v2_request, config)
        self.assertEqual(len(calls), 1)


class CountingRepairProvider(Scripted):
    def __init__(self, raw, repair_output=None):
        super().__init__(raw)
        self.repair_output, self.repair_calls, self.requests = repair_output, 0, []

    def repair(self, conversation, checklist, request, config, original_raw, reviews):
        self.repair_calls += 1
        self.requests.append(request)
        return ProviderReply(deepcopy(self.repair_output), model="offline-repair-fixture",
                             response_id="offline-repair", usage={"input_tokens": 11, "output_tokens": 7}, latency_ms=5)


def scripted_repair_of_genuine(conv):
    """Hand-authored repair fixture: the genuine answers unchanged, scope added, C07 judgment supplied."""
    raw = genuine()
    c03, c05, c07 = (deepcopy(next(c for c in raw["criteria"] if c["criterion_id"] == cid)) for cid in ("03", "05", "07"))
    fact_of = lambda c, qid: next(a for a in c["atomic_checks"] if a["question_id"] == qid)
    fact_of(c03, "03.q1")["evidence"] = [scope(conv)]
    fact_of(c05, "05.q3")["evidence"] = [scope(conv)]
    c07["judgment"] = {"response": "yes", "rationale": "Hand-authored repair fixture.",
                       "evidence": [quote(conv.messages[11])], "violation_categories": [],
                       "needs_review": False, "review_reason": None}
    return {"schema_version": "1.2", "criteria": [c03, c05, c07]}


class BoundedRepairTests(unittest.TestCase):
    def setUp(self):
        self.conv, self.checklist = load_conversation(SHARED, "p1-ru-001"), atomic_checklist()
        self.policy = RepairPolicy(authorization="offline unit test; no paid call")

    def test_disabled_by_default_and_requires_explicit_authorization(self):
        provider = CountingRepairProvider(genuine(), scripted_repair_of_genuine(self.conv))
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, provider, V3)
        self.assertEqual(provider.repair_calls, 0)
        self.assertEqual(caught.exception.diagnostic["repair_attempts"], [])
        for bad in ("", "   "):
            with self.assertRaises(ValueError):
                RepairPolicy(authorization=bad)
        with self.assertRaises(ValueError):
            evaluate(self.conv, load_checklist(), provider, repair=self.policy)  # Legacy path: never.

    def test_genuine_reply_repaired_once_without_changing_answers_or_original(self):
        original = genuine()
        provider = CountingRepairProvider(original, scripted_repair_of_genuine(self.conv))
        result = evaluate(self.conv, self.checklist, provider, V3, repair=self.policy)
        self.assertEqual(provider.repair_calls, 1)
        self.assertEqual(result.original_provider_output, original)
        self.assertEqual(result.status, "mock_only")  # Scripted provider is mock; real repairs => needs_review.
        attempt = result.repair_attempts[0]
        self.assertEqual((attempt.status, attempt.criterion_ids), ("merged", ["03", "05", "07"]))
        self.assertEqual(attempt.answer_changes, [])
        self.assertEqual(attempt.pinned_answers["03.q1"], "no")
        self.assertEqual(attempt.usage, {"input_tokens": 11, "output_tokens": 7})
        self.assertEqual(result.run.usage, {})  # Primary usage stays separate from repair usage.
        merged = {c["criterion_id"]: c for c in attempt.merged_output["criteria"]}
        kept = {c["criterion_id"]: c for c in original["criteria"]}
        for cid in ("01", "02", "04", "06", "08"):
            self.assertEqual(merged[cid], kept[cid])
        self.assertEqual({d.criterion_id: d.response for d in result.validated_evaluation.decisions}["03"], "N/A")
        self.assertIsNotNone(result.score.total_score)
        self.assertTrue(any(a.stage == "bounded_criterion_repair" and a.outcome == "review" for a in result.audit))
        self.assertEqual(EvaluationResult.model_validate_json(result.model_dump_json()), result)

    def test_repair_schema_pins_answers_and_merge_rejects_flips(self):
        reviews = None
        try:
            process_atomic_output(genuine(), self.conv, self.checklist)
        except AtomicReviewRequired as error:
            reviews = error.reviews
        request, _, targets, pins, _ = build_repair_request(self.conv, self.checklist, genuine(), reviews, "atomic-v3")
        self.assertEqual(targets, ["03", "05", "07"])
        self.assertEqual(strict_issues(request["schema"]), [])
        payload = json.loads(request["input"])
        self.assertEqual([c["criterion_id"] for c in payload["criteria_to_repair"]], targets)
        self.assertTrue(all(c["diagnostics"] for c in payload["criteria_to_repair"]))
        good = scripted_repair_of_genuine(self.conv)
        self.assertTrue(conforms(good, request["schema"]))
        flipped = deepcopy(good)
        next(a for a in flipped["criteria"][0]["atomic_checks"] if a["question_id"] == "03.q1").update(
            answer="yes", evidence=[quote(self.conv.messages[0])])
        self.assertFalse(conforms(flipped, request["schema"]))
        provider = CountingRepairProvider(genuine(), flipped)
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, provider, V3, repair=self.policy)
        attempt = caught.exception.diagnostic["repair_attempts"][0]
        self.assertEqual((attempt["status"], provider.repair_calls), ("rejected_output", 1))
        self.assertIn({"question_id": "03.q1", "original": "no", "repaired": "yes"}, attempt["answer_changes"])
        self.assertEqual(caught.exception.diagnostic["original_model_output"], genuine())
        self.assertNotIn("score", caught.exception.diagnostic)

    def test_retreat_to_unknown_is_allowed_but_blocks_total(self):
        retreat = scripted_repair_of_genuine(self.conv)
        next(a for a in retreat["criteria"][1]["atomic_checks"] if a["question_id"] == "05.q3")["answer"] = "unknown"
        provider = CountingRepairProvider(genuine(), retreat)
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, provider, V3, repair=self.policy)
        d = caught.exception.diagnostic
        self.assertEqual(d["repair_attempts"][0]["status"], "merged")
        self.assertEqual({r["criterion_id"]: r["state"] for r in d["criterion_reviews"]}["05"], "needs_review")
        self.assertEqual(provider.repair_calls, 1)

    def test_still_invalid_after_repair_makes_no_second_call(self):
        still_bad = scripted_repair_of_genuine(self.conv)
        still_bad["criteria"][2]["judgment"]["evidence"] = [quote(self.conv.messages[0])]  # Customer quote.
        provider = CountingRepairProvider(genuine(), still_bad)
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, provider, V3, repair=self.policy)
        self.assertEqual(provider.repair_calls, 1)
        states = {r["criterion_id"]: r["state"] for r in caught.exception.diagnostic["criterion_reviews"]}
        self.assertEqual(states["07"], "invalid_facts")
        self.assertEqual(states["03"], "accepted_derived")

    def test_review_states_and_wrong_shapes_are_never_sent_or_merged(self):
        raw = raw_fixture(self.conv, self.checklist)
        fact(raw, "05.q1")["answer"] = "unknown"
        provider = CountingRepairProvider(raw, None)
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, provider, repair=self.policy)
        self.assertEqual(caught.exception.diagnostic["repair_attempts"][0]["status"], "not_attempted")
        self.assertEqual(provider.repair_calls, 0)
        extra = scripted_repair_of_genuine(self.conv)
        extra["criteria"].append(deepcopy(genuine()["criteria"][0]))
        provider = CountingRepairProvider(genuine(), extra)
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, provider, V3, repair=self.policy)
        self.assertEqual(caught.exception.diagnostic["repair_attempts"][0]["status"], "rejected_output")

    def test_real_adapter_repair_uses_same_gates_binding_and_separate_usage(self):
        replies, calls = [genuine(), scripted_repair_of_genuine(self.conv)], []

        def transport(payload, timeout):
            calls.append(payload)
            return {"id": f"offline-{len(calls)}", "status": "completed", "model": "offline-model",
                    "usage": {"input_tokens": 100 * len(calls), "output_tokens": 10, "total_tokens": 100 * len(calls) + 10},
                    "output": [{"content": [{"type": "output_text", "text": json.dumps(replies[len(calls) - 1])}]}]}
        provider = OpenAIProvider("offline-model", api_key="offline-placeholder", transport=transport)
        config = EvaluationConfig(prompt_version="atomic-v3", external_synthetic_allowed=True)
        result = evaluate(self.conv, self.checklist, provider, config, repair=self.policy)
        self.assertEqual([c["text"]["format"]["name"] for c in calls], ["cqa_atomic_v1_2", "cqa_atomic_repair_v1"])
        self.assertEqual(result.status, "needs_review")
        self.assertEqual(result.run.usage["input_tokens"], 100)
        self.assertEqual(result.repair_attempts[0].usage["input_tokens"], 200)
        with self.assertRaises(ProviderError):
            provider.repair(self.conv, self.checklist, {"instructions": "x", "input": "{}", "schema": {}},
                            config, genuine(), result.criterion_reviews)
        from cqa.repair import attempt_repair
        try:
            process_atomic_output(genuine(), self.conv, self.checklist)
        except AtomicReviewRequired as error:
            reviews, issues = error.reviews, error.issues
        gated = EvaluationConfig(prompt_version="atomic-v3")  # External export not opted in.
        attempt, merged = attempt_repair(self.policy, provider, self.conv, self.checklist, gated, genuine(), reviews, issues)
        self.assertEqual((attempt.status, merged), ("provider_error", None))
        self.assertEqual(len(calls), 2)  # The data gate refused before any transport.


class AdversarialRegressionTests(unittest.TestCase):
    """Deterministic/metamorphic pipeline assertions; semantics still need a model and humans."""

    def setUp(self):
        self.checklist = atomic_checklist()

    def run_raw(self, conv, raw):
        return evaluate(conv, self.checklist, Scripted(raw), V3)

    def responses(self, conv, raw):
        return {d.criterion_id: d.response for d in self.run_raw(conv, raw).validated_evaluation.decisions}

    def test_c04_incorrect_versus_incomplete_advice_is_bounded_by_configured_rules(self):
        conv = record([("client", "How do I withdraw USD and what is the fee?"),
                       ("operator", "Hello, I am Sam. Use the Withdraw tab. Goodbye.")])
        schema = compile_atomic_schema(conv, self.checklist)
        raw = raw_fixture(conv, self.checklist)
        fact(raw, "04.q3")["answer"] = "no"  # Key advice incorrect: only 0 is permitted.
        for level, valid in ((0, True), (5, False), (20, False)):
            decision(raw, "04")["judgment"]["response"] = level
            self.assertEqual(entry_conforms(decision(raw, "04"), schema), valid, level)
        decision(raw, "04")["judgment"]["response"] = 10
        fact(raw, "04.q3")["answer"] = "yes"; fact(raw, "04.q2")["answer"] = "no"  # Incomplete: 0/5/10.
        self.assertTrue(entry_conforms(decision(raw, "04"), schema))
        self.assertEqual(self.responses(conv, raw)["04"], 10)
        decision(raw, "04")["judgment"]["response"] = 15
        self.assertFalse(entry_conforms(decision(raw, "04"), schema))
        with self.assertRaises(EvaluationRejected):
            self.run_raw(conv, raw)

    def test_c05_politeness_versus_empathy_truth_table(self):
        conv = record([("client", "Your app crashed twice and I lost an hour. How do I export my report?"),
                       ("operator", "Hello, I am Sam. Open Reports and press Export. Goodbye.")])
        cases = {("yes", "no", "not_applicable"): "yes", ("yes", "yes", "yes"): "yes",
                 ("yes", "yes", "no"): "no", ("no", "no", "not_applicable"): "no"}
        for (polite, complaint, addressed), expected in cases.items():
            raw = raw_fixture(conv, self.checklist)
            fact(raw, "05.q1")["answer"] = polite
            fact(raw, "05.q3").update(answer=complaint, evidence=[scope(conv)] if complaint == "no"
                                      else [quote(conv.messages[0])])
            fact(raw, "05.q2")["answer"] = addressed
            self.assertEqual(self.responses(conv, raw)["05"], expected, (polite, complaint, addressed))
        schema = compile_atomic_schema(conv, self.checklist)
        raw = raw_fixture(conv, self.checklist)
        fact(raw, "05.q3").update(answer="yes", evidence=[quote(conv.messages[0])])
        fact(raw, "05.q2")["answer"] = "not_applicable"  # Ignoring a stated complaint is not representable.
        self.assertFalse(entry_conforms(decision(raw, "05"), schema))

    def test_c07_missing_partial_and_interrupted_closing(self):
        conv = record([("client", "Where is Help?"), ("operator", "Hello, I am Sam. Open Help."),
                       ("client", "Thanks.")])
        schema = compile_atomic_schema(conv, self.checklist)
        raw = raw_fixture(conv, self.checklist)
        fact(raw, "07.q3")["answer"] = "no"  # No farewell: only "no" may be judged.
        decision(raw, "07")["judgment"]["response"] = "yes"
        self.assertFalse(entry_conforms(decision(raw, "07"), schema))
        decision(raw, "07")["judgment"]["response"] = "no"
        self.assertEqual(self.responses(conv, raw)["07"], "no")
        decision(raw, "07")["judgment"] = None  # Applicable but omitted: the genuine failure class.
        self.assertFalse(entry_conforms(decision(raw, "07"), schema))
        fact(raw, "07.q1")["answer"] = "yes"
        self.assertTrue(entry_conforms(decision(raw, "07"), schema))
        self.assertEqual(self.responses(conv, raw)["07"], "N/A")

    def test_c08_hidden_violation_in_long_dialogue_with_irrelevant_turns(self):
        noise = [("bot" if i % 2 else "client", f"Irrelevant turn {i}.") for i in range(40)]
        turns = ([("client", "Can you help with fees?"), ("operator", "Hello, I am Sam. Fees are listed in Tariffs.")]
                 + noise[:20] + [("operator", "Pay me privately by card and I will lower the fee.")] + noise[20:]
                 + [("operator", "Goodbye.")])
        conv = record(turns, "hidden-c08")
        hidden = next(m for m in conv.messages if "privately" in m.text)
        schema = compile_atomic_schema(conv, self.checklist)
        raw = raw_fixture(conv, self.checklist)
        for qid in ("08.q1", "08.q2", "08.q3"):
            fact(raw, qid)["evidence"] = [scope(conv)]
        self.assertTrue(entry_conforms(decision(raw, "08"), schema))
        self.assertEqual(self.responses(conv, raw)["08"], "no")  # A model miss is NOT caught structurally.
        fact(raw, "08.q2").update(answer="yes", evidence=[quote(hidden)])
        result = self.run_raw(conv, raw)
        self.assertEqual(result.score.violation_categories, ["paid_service_bypassing_company"])
        partial = deepcopy(raw)
        fact(partial, "08.q1")["evidence"] = [dict(scope(conv), end_message_id=hidden.message_id)]
        self.assertFalse(entry_conforms(decision(partial, "08"), schema))  # Truncated scope unrepresentable.
        with self.assertRaises(EvaluationRejected):
            self.run_raw(conv, partial)

    def test_ru_kz_en_and_irrelevant_turns_are_metamorphic_invariants(self):
        texts = {"RU": ("Где мой тариф?", "Здравствуйте! Меня зовут Алина. Откройте «Кабинет». До свидания!"),
                 "KZ": ("Тарифім қайда?", "Сәлеметсіз бе! Менің атым Алина. «Кабинет» бөлімін ашыңыз. Сау болыңыз!"),
                 "EN": ("Where is my tariff?", "Hello! My name is Alina. Open «Cabinet». Goodbye!")}
        outcomes, shapes = {}, set()
        for language, (ask, answer) in texts.items():
            for padded in (False, True):
                turns = [("client", ask)] + ([("bot", "Please wait."), ("system", "Escalated.")] * 5 if padded else []) \
                    + [("operator", answer)]
                conv = record(turns, f"{language}-{padded}", language)
                raw = raw_fixture(conv, self.checklist)
                for entry in raw["criteria"]:
                    criterion = next(c for c in self.checklist.criteria if c.criterion_id == entry["criterion_id"])
                    entry.update(full_scope_normalized(entry, criterion))
                schema = compile_atomic_schema(conv, self.checklist)
                self.assertTrue(conforms(raw, schema), (language, padded))
                result = self.run_raw(conv, raw)
                outcomes[(language, padded)] = (tuple(sorted(self.responses(conv, raw).items())), result.score.total_score)
                text = json.dumps(schema)
                shapes.add(text.replace(conv.messages[-1].message_id, "LAST"))
                stale = deepcopy(raw)  # A scope ending before inserted turns is unrepresentable.
                fact(stale, "08.q1")["evidence"] = [dict(scope(conv), end_message_id=conv.messages[0].message_id)]
                self.assertFalse(conforms(stale, schema))
        self.assertEqual(len(set(outcomes.values())), 1)
        self.assertEqual(len(shapes), 1)  # Language/turn count changes only the scope boundary.


if __name__ == "__main__":
    unittest.main()
