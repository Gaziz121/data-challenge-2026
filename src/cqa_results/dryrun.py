"""Offline submission dry run with clearly labelled synthetic inputs. No network.

    PYTHONPATH=src python3 -m cqa_results.dryrun --out outputs/submission-dryrun/run1

DEV-65 dry run = the 60 reviewed synthetic DEV chats (shared, identical to the
organizer chats) + 5 INVENTED voice stand-ins (IDs SYNTH-VOICE-00n). They are not
the real organizer calls. PROD-10 dry run = 10 INVENTED chats (IDs SIM-PROD-0nn);
they are not organizer control data. A scripted fixture provider drives the
UNCHANGED engine (validation, coverage, exact scoring), including genuine engine
rejections and provider failures. Outputs stay under ignored outputs/.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from cqa.io import load_checklist, parse_json
from cqa.loader import SHARED
from cqa.providers import ProviderError, ProviderReply
from cqa.schemas import MODEL_OUTPUT_SCHEMA_VERSION

from .batch import run_batch
from .export import build_submission, write_submission
from .validate import validate_file

FIXTURE_MODEL = "scripted-dryrun-fixture-v1"
LEGACY_CHECKLIST = Path(__file__).resolve().parents[1] / "cqa/checklists/official-v3.json"

# Internal criterion responses per scenario (official order 01..08).
SCENARIOS = {
    "all_positive": {"01": "yes", "02": "yes", "03": "yes", "04": 20, "05": "yes", "06": 10, "07": "yes", "08": "no"},
    "appendix_like": {"01": "yes", "02": "N/A", "03": "N/A", "04": 15, "05": "yes", "06": 7, "07": "yes", "08": "no"},
    "critical": {"01": "yes", "02": "yes", "03": "no", "04": 10, "05": "no", "06": 4, "07": "no", "08": "yes"},
    "all_negative": {"01": "no", "02": "no", "03": "no", "04": 0, "05": "no", "06": 0, "07": "no", "08": "no"},
    "na_heavy": {"01": "yes", "02": "N/A", "03": "N/A", "04": "N/A", "05": "yes", "06": 7, "07": "N/A", "08": "no"},
}
ROTATION = ("all_positive", "appendix_like", "critical", "all_negative", "na_heavy")


class ScriptedProvider:
    """Deterministic fixture that emits schema-valid legacy (v3) decisions.

    It is a test driver for the export path, not an evaluator: responses are
    chosen by rotation, never from conversation meaning. `reject_ids` receive a
    deliberately non-exact quote (a genuine engine rejection); `fail_ids` raise a
    ProviderError (a genuine provider failure); `scenario_for` overrides rotation.
    """
    name = "scripted-dryrun"
    model = FIXTURE_MODEL
    is_mock = True

    def __init__(self, reject_ids=(), fail_ids=(), scenario_for=None):
        self.reject_ids, self.fail_ids = set(reject_ids), set(fail_ids)
        self.scenario_for = dict(scenario_for or {})

    def scenario(self, conversation):
        if conversation.conversation_id in self.scenario_for:
            return self.scenario_for[conversation.conversation_id]
        if not any(m.role == "agent" for m in conversation.messages):
            return "all_negative"  # Positive answers need a quoted operator turn.
        digest = hashlib.sha256(conversation.conversation_id.encode("utf-8")).digest()
        return ROTATION[digest[0] % len(ROTATION)]

    def evaluate(self, conversation, checklist, request, config):
        cid = conversation.conversation_id
        if cid in self.fail_ids:
            raise ProviderError("Simulated provider timeout (dry-run fixture); no response received")
        if checklist.decision_path != "legacy":
            raise ProviderError("Scripted dry-run provider supports only the legacy checklist path")
        messages = conversation.messages
        agent = next((m for m in messages if m.role == "agent"), None)
        scope = {"kind": "scope", "message_id": None, "quote": None,
                 "start_message_id": messages[0].message_id, "end_message_id": messages[-1].message_id,
                 "explanation": "DRY-RUN: full inspected scope."}
        responses = SCENARIOS[self.scenario(conversation)]
        decisions = []
        for criterion in checklist.criteria:
            response = responses[criterion.criterion_id]
            positive = response == "yes" or type(response) is int and response > 0
            if positive and agent is not None:
                evidence = [{"kind": "quote", "message_id": agent.message_id, "quote": agent.text,
                             "start_message_id": None, "end_message_id": None,
                             "explanation": "DRY-RUN: first operator turn."}]
                if criterion.kind == "critical":
                    evidence.append(dict(scope))
            else:
                evidence = [dict(scope)]
            if cid in self.reject_ids and criterion.criterion_id == "04":
                evidence = [{"kind": "quote", "message_id": messages[0].message_id,
                             "quote": "DRY-RUN text that does not occur in the transcript",
                             "start_message_id": None, "end_message_id": None,
                             "explanation": "DRY-RUN: deliberately invalid quote."}]
            answers = {q.question_id: "unknown" for q in criterion.questions}
            if response == "N/A":
                answers[criterion.applicability_rule.question_id] = criterion.applicability_rule.na_when
            categories = []
            if criterion.kind == "critical" and response == "yes":
                question = next(q for q in criterion.questions if q.violation_category == "insult")
                answers[question.question_id], categories = "yes", ["insult"]
            decisions.append({
                "criterion_id": criterion.criterion_id, "response": response,
                "rationale": "DRY-RUN scripted fixture (%s); not a quality judgment." % self.scenario(conversation),
                "na_reason": "DRY-RUN: scripted N/A condition." if response == "N/A" else None,
                "evidence": evidence, "violation_categories": categories,
                "needs_review": True, "review_reason": "DRY-RUN fixture; no semantic assessment.",
                "atomic_checks": [{"question_id": q, "answer": a, "rationale": "DRY-RUN fixture.",
                                   "evidence": [dict(scope)]} for q, a in answers.items()]})
        return ProviderReply({"schema_version": MODEL_OUTPUT_SCHEMA_VERSION, "decisions": decisions},
                             model=self.model, usage={})


def _ts(n):
    return "2026-01-01T10:%02d:%02dZ" % (n // 60, n % 60)


def synthetic_voice_record(n):
    """INVENTED voice stand-in; not derived from any organizer call."""
    turns = [("system", "Синтетическая запись: звонок начат."),
             ("operator", "Здравствуйте! Вас приветствует служба поддержки, меня зовут Тестовый Оператор."),
             ("client", "Добрый день. Хочу узнать, как пополнить брокерский счёт."),
             ("operator", "Для проверки назовите, пожалуйста, кодовое слово.")]
    for k in range(n):
        turns += [("client", "Уточняющий вопрос номер %s по синтетическому сценарию." % (k + 1)),
                  ("operator", "Отвечаю на уточняющий вопрос по синтетическому сценарию.")]
    turns += [("operator", "Пополнить счёт можно в приложении в разделе пополнения."),
              ("client", "Понятно, спасибо."),
              ("operator", "Могу ли я ещё чем-то помочь? Хорошего дня!"),
              ("system", "Синтетическая запись: звонок завершён.")]
    return {"conversation_id": "SYNTH-VOICE-%03d" % n, "channel": "voice call", "language": "ru",
            "audio_url": "", "transcript": [{"timestamp": _ts(i), "speaker": s, "text": t}
                                            for i, (s, t) in enumerate(turns)]}


def simulated_control_record(n):
    """INVENTED control-like chat; not organizer control data."""
    turns = [("bot", "Синтетический бот: здравствуйте! Опишите ваш вопрос."),
             ("client", "Синтетический клиент: не проходит вывод средств, вопрос %d." % n),
             ("system", "Синтетическое событие: чат передан оператору.")]
    if n % 5 != 0:  # Every fifth simulated control is bot-only (no human operator turn).
        turns += [("operator", "Здравствуйте! Меня зовут Синтетический Оператор, сейчас проверю."),
                  ("client", "Спасибо, жду.")]
        turns += [("operator", "Шаг проверки %d выполнен по синтетическому сценарию." % k) for k in range(1, n % 4 + 2)]
        turns += [("operator", "Готово, вывод обработан. Остались ли вопросы?"), ("client", "Нет, спасибо.")]
    else:
        turns += [("bot", "Синтетический бот: оператор недоступен, попробуйте позже.")]
    return {"conversation_id": "SIM-PROD-%03d" % n, "channel": "agent chat", "language": "ru", "audio_url": None,
            "transcript": [{"timestamp": _ts(i), "speaker": s, "text": t} for i, (s, t) in enumerate(turns)]}


def envelope(records, group):
    return {"isSuccess": True, "error": "",
            "data": {"dataset_group_id": group, "total_records": len(records), "records": records}}


def dev65_dryrun_dataset():
    shared = parse_json(Path(SHARED).read_bytes())["data"]["records"]
    if len(shared) != 60:
        raise ValueError("Reviewed synthetic DEV file must contain 60 chats")
    return envelope(shared + [synthetic_voice_record(n) for n in range(1, 6)],
                    "DRYRUN-DEV65-SYNTHETIC-60-CHATS-PLUS-5-INVENTED-VOICE-STANDINS")


def prod10_dryrun_dataset():
    return envelope([simulated_control_record(n) for n in range(1, 11)], "DRYRUN-PROD10-SIMULATED-NOT-ORGANIZER")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def run_dryrun(out, log=print):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Dry-run directory must be new or empty")
    checklist = load_checklist(LEGACY_CHECKLIST)
    summary = {}
    for set_name, dataset, rejects, fails in (
            ("dev", dev65_dryrun_dataset(), {"SYNTH-VOICE-003"}, {"SYNTH-VOICE-005"}),
            ("prod", prod10_dryrun_dataset(), {"SIM-PROD-004"}, {"SIM-PROD-007"})):
        data_path = write_json(out / set_name / "dataset.json", dataset)
        provider = ScriptedProvider(reject_ids=rejects, fail_ids=fails)
        counts = run_batch(data_path, out / set_name / "run", provider, checklist=checklist, log=lambda *_: None)
        submission, report = build_submission(data_path, out / set_name / "run", "DRY-RUN TEAM (not a submission)",
                                              set_name, allow_mock=True)
        target = out / set_name / "results.json"
        write_submission(submission, target, data_path, set_name, allow_mock=True)
        validation = validate_file(target, data_path, set_name)
        summary[set_name] = {"batch": counts, "export": report, "validation": validation["summary"],
                             "valid": validation["valid"], "file": str(target)}
        log("%s: %s" % (set_name.upper(), json.dumps(summary[set_name], ensure_ascii=False)))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, type=Path, help="New directory under outputs/")
    args = parser.parse_args(argv)
    try:
        summary = run_dryrun(args.out)
    except (OSError, ValueError) as error:
        print("Dry run failed: %s" % error, file=sys.stderr)
        return 1
    return 0 if all(s["valid"] for s in summary.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
