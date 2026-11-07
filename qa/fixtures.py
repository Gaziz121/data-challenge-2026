"""Small hand-written synthetic fixtures for independent QA.

These are not DEV conversations, not official Ground Truth and not human
benchmark labels. They only build structurally valid inputs and outputs that
isolate one adversarial change at a time.
"""

from copy import deepcopy

from cqa.io import digest
from cqa.loader import normalize_record
from cqa.providers import ProviderReply
from cqa.schemas import ModelEvaluation

GROUP = "QA_SYNTHETIC"

# Answers that describe a fully compliant conversation for the official-v1
# atomic questions. Any question not listed is answered "yes".
GOOD_ATOMIC = {"02.q1": "no", "06.q2": "no", "07.q1": "no",
               "08.q1": "no", "08.q2": "no", "08.q3": "no"}

# A compliant EN chat: bot first, system handover, operator greets and
# introduces, identity verified by a SYSTEM event before disclosure, farewell.
GATES_EN = [
    ("client", "Hello, I need my account balance and the fee for my plan."),
    ("bot", "Hello! I'm AIM, the Freedom Broker AI assistant."),
    ("system", "Chat transferred to an agent."),
    ("operator", "Hello, I'm Sam from support. To check the balance I need to verify your identity."),
    ("client", "Sure."),
    ("system", "Customer identity verified."),
    ("operator", "Thank you. Your balance is 100 USD and your plan is «Standard» with no monthly fee."),
    ("client", "Great, thanks."),
    ("operator", "Is there anything else I can help with? Goodbye!"),
]

# The first operator reply has no greeting; the greeting arrives one turn later.
LATE_INTRO_EN = [
    ("client", "How do I enable two-factor authentication?"),
    ("bot", "Hello! I'm AIM, the Freedom Broker AI assistant."),
    ("system", "Chat transferred to an agent."),
    ("operator", "Please open Settings first."),
    ("operator", "Hello, I'm Sam from support."),
    ("client", "Done."),
    ("operator", "Then choose Security and switch on two-factor authentication. Anything else? Goodbye!"),
]

GATES_RU = [
    ("client", "Здравствуйте, как узнать комиссию по моему тарифу?"),
    ("bot", "Здравствуйте! Я AIM, AI-ассистент Freedom Broker."),
    ("system", "Эскалация на оператора."),
    ("operator", "Здравствуйте, меня зовут Роман. Комиссия указана в разделе «Тарифы» приложения."),
    ("client", "Нашёл, спасибо."),
    ("operator", "Рад помочь. Могу ли я ещё чем-то помочь? До свидания!"),
]

GATES_KZ = [
    ("client", "Сәлеметсіз бе, шотқа ақша қалай саламын?"),
    ("bot", "Сәлеметсіз бе! Мен AIM, Freedom Broker AI-көмекшісімін."),
    ("system", "Чат операторға жіберілді."),
    ("operator", "Сәлеметсіз бе, менің атым Айгерім. Қолданбада «Толықтыру» бөлімін ашыңыз."),
    ("client", "Рақмет, таптым."),
    ("operator", "Тағы сұрақтарыңыз бар ма? Сау болыңыз!"),
]


def make_record(turns, conversation_id="qa-fixture", language="EN", channel="agent chat"):
    return {"conversation_id": conversation_id, "channel": channel, "language": language,
            "transcript": [{"speaker": s, "timestamp": f"00:{i:02d}", "text": t}
                           for i, (s, t) in enumerate(turns)],
            "audio_url": None}


def make_conversation(turns, conversation_id="qa-fixture", language="EN", channel="agent chat"):
    record = make_record(turns, conversation_id, language, channel)
    return normalize_record(record, GROUP, digest(record))


def quote(message, text=None, why="QA fixture evidence."):
    return {"kind": "quote", "message_id": message.message_id,
            "quote": message.text if text is None else text,
            "start_message_id": None, "end_message_id": None, "explanation": why}


def scope(conv, why="QA fixture: entire conversation inspected."):
    return {"kind": "scope", "message_id": None, "quote": None,
            "start_message_id": conv.messages[0].message_id,
            "end_message_id": conv.messages[-1].message_id, "explanation": why}


def valid_raw(conv, checklist, evidence_index=None):
    """A structurally valid, fully compliant evaluation for official-v1.

    `evidence_index` maps criterion_id -> source index of the agent message cited
    as positive evidence. Criterion 01 defaults to the FIRST agent reply and all
    others to the LAST agent reply, so the baseline stays valid if stricter
    locator rules are later added.
    """
    agents = [m for m in conv.messages if m.role == "agent"]
    evidence_index = evidence_index or {}
    decisions = []
    for criterion in checklist.criteria:
        cid = criterion.criterion_id
        critical = criterion.kind == "critical"
        if critical:
            evidence = [scope(conv)]
            response = "no"
        else:
            default = agents[0] if cid == "01" else agents[-1]
            message = conv.messages[evidence_index[cid]] if cid in evidence_index else default
            evidence = [quote(message)]
            response = max(criterion.levels) if criterion.kind == "discrete" else "yes"
        decisions.append({
            "criterion_id": cid, "response": response,
            "rationale": "QA fixture rationale.", "na_reason": None,
            "evidence": deepcopy(evidence), "violation_categories": [],
            "needs_review": False, "review_reason": None,
            "atomic_checks": [{"question_id": q.question_id,
                               "answer": GOOD_ATOMIC.get(q.question_id, "yes"),
                               "rationale": "QA fixture atomic rationale.",
                               "evidence": deepcopy(evidence)} for q in criterion.questions]})
    return {"schema_version": "1.0", "decisions": decisions}


def decision(raw, criterion_id):
    return next(d for d in raw["decisions"] if d["criterion_id"] == criterion_id)


def set_atomic(raw, question_id, answer):
    criterion_id = question_id.split(".")[0]
    atomic = next(a for a in decision(raw, criterion_id)["atomic_checks"]
                  if a["question_id"] == question_id)
    atomic["answer"] = answer
    return atomic


def as_model(raw):
    return ModelEvaluation.model_validate(deepcopy(raw))


class ScriptedProvider:
    """Offline test double returning a fixed evaluation. Never semantic evidence."""
    name = "qa-scripted"
    model = "qa-scripted-fixture"
    is_mock = False          # exercises the non-mock status path only
    is_test_double = True    # the QA harness never gives a test double semantic credit

    def __init__(self, raw):
        self.raw = raw

    def evaluate(self, conversation, checklist, request, config):
        return ProviderReply(deepcopy(self.raw), model=self.model)
