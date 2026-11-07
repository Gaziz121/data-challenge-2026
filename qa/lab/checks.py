"""Label-free deterministic checks over one saved model output (INV-* in label_registry.json).

Independent of the engine's validator: it reads plain JSON (the checklist and
conversation embedded in each saved artifact, verified against the source), so
an engine change cannot relax the lab's yardstick. It never changes a decision.
"""

from fractions import Fraction
from types import SimpleNamespace
import unicodedata

from qa.decision_rules import derive_response

_QUOTES = {"«": '"', "»": '"', "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'"}


def fold_formatting(text):
    """NFC, typographic quotes and whitespace only; no case folding or letter changes."""
    text = unicodedata.normalize("NFC", text)
    return " ".join("".join(_QUOTES.get(c, c) for c in text).split())


def quote_status(quote, source_text):
    if not isinstance(quote, str) or not any(c.isalnum() for c in quote):
        return "invalid"
    if quote in source_text:
        return "exact"
    folded = fold_formatting(quote)
    return "formatting_only" if folded and folded in fold_formatting(source_text) else "invalid"


def permitted(criterion):
    values = list(criterion["levels"]) if criterion["kind"] == "discrete" else ["yes", "no"]
    return values + (["N/A"] if criterion.get("na_condition") is not None else [])


def favorability(criterion, response):
    """Order used by INV-CF-MONO; None when not comparable (N/A or invalid)."""
    if criterion["kind"] == "discrete" and type(response) is int:
        return response
    if criterion["kind"] == "binary" and response in ("yes", "no"):
        return int(response == "yes")
    if criterion["kind"] == "critical" and response in ("yes", "no"):
        return int(response == "no")  # no violation is the favorable outcome
    return None


def _as_rule_criterion(criterion):
    rule = criterion.get("applicability_rule")
    return SimpleNamespace(criterion_id=criterion["criterion_id"], kind=criterion["kind"],
                           applicability_rule=SimpleNamespace(**rule) if rule else None)


def _references(decision):
    refs = [r for r in decision.get("evidence") or [] if isinstance(r, dict)]
    for atomic in decision.get("atomic_checks") or []:
        if isinstance(atomic, dict):
            refs += [r for r in atomic.get("evidence") or [] if isinstance(r, dict)]
    return refs


def check_decision(decision, criterion, messages):
    """messages: list of source-verified dicts with message_id, source_index, role, text."""
    by_id = {m["message_id"]: m for m in messages}
    issues = []

    def add(invariant, message):
        issues.append({"invariant": invariant, "message": message})

    response = decision.get("response")
    if response not in permitted(criterion) or (type(response) is int) != (criterion["kind"] == "discrete"):
        add("INV-RESP", f"Response {response!r} is not permitted")
    answers = {a.get("question_id"): a.get("answer") for a in decision.get("atomic_checks") or []
               if isinstance(a, dict)}
    rule = criterion.get("applicability_rule")
    if rule and answers.get(rule["question_id"]) is not None:
        if (answers[rule["question_id"]] == rule["na_when"]) != (response == "N/A"):
            add("INV-APPL", "Response contradicts the model's own applicability answer")
    for r in criterion.get("consistency_rules") or []:
        if answers.get(r["question_id"]) == r["when_answer"] and response not in r["permitted_responses"]:
            add("INV-ATOM", f"Contradicts consistency rule on {r['question_id']}={r['when_answer']}")
    derived = derive_response(_as_rule_criterion(criterion), answers)
    if derived in ("yes", "no") and response in ("yes", "no") and derived != response:
        add("INV-ATOM", f"All-of rule derives {derived} from the model's own atomic answers")

    evidence = {"quotes": 0, "exact": 0, "formatting_only": 0, "invalid": 0, "scope_invalid": 0}
    for ref in _references(decision):
        if ref.get("kind") == "quote":
            evidence["quotes"] += 1
            message = by_id.get(ref.get("message_id"))
            status = quote_status(ref.get("quote"), message["text"]) if message else "invalid"
            evidence[status] += 1
        else:
            start, end = by_id.get(ref.get("start_message_id")), by_id.get(ref.get("end_message_id"))
            if start is None or end is None or start["source_index"] > end["source_index"]:
                evidence["scope_invalid"] += 1
    if evidence["invalid"]:
        add("INV-EVID", f"{evidence['invalid']} quote(s) not found in the cited message")
    if evidence["scope_invalid"]:
        add("INV-EVID", f"{evidence['scope_invalid']} invalid scope reference(s)")

    top = [r for r in decision.get("evidence") or [] if isinstance(r, dict)]
    supporting = [r for r in top if r.get("kind") == "quote" and r.get("message_id") in by_id
                  and quote_status(r.get("quote"), by_id[r["message_id"]]["text"]) != "invalid"]
    if criterion["kind"] == "critical":
        if response == "no" and not any(
                r.get("kind") == "scope" and r.get("start_message_id") == messages[0]["message_id"]
                and r.get("end_message_id") == messages[-1]["message_id"] for r in top):
            add("INV-CRIT", "08=no does not cite the full conversation scope")
        if response == "yes":
            if not any(by_id[r["message_id"]]["role"] == "agent" for r in supporting):
                add("INV-CRIT", "08=yes does not quote an operator utterance")
            mapped = {q["question_id"]: q.get("violation_category") for q in criterion["questions"]}
            asserted = {mapped[q] for q, a in answers.items() if a == "yes" and mapped.get(q)}
            if set(decision.get("violation_categories") or []) != asserted:
                add("INV-CRIT", "Categories differ from the yes-answered category questions")
    elif response == "yes" or (type(response) is int and response > 0):
        policy = criterion.get("evidence_policy") or {"positive_roles": ["agent"], "positive_locator": "any"}
        allowed = [r for r in supporting if by_id[r["message_id"]]["role"] in policy["positive_roles"]]
        if not allowed:
            add("INV-POLICY", "Positive response lacks a quote from an allowed role")
        if policy.get("positive_locator") == "first_agent":
            first = next((m["message_id"] for m in messages if m["role"] == "agent"), None)
            if not any(r["message_id"] == first for r in allowed):
                add("INV-POLICY", "Positive response does not cite the first human operator reply")
    return {"response": response, "applicability": "N/A" if response == "N/A" else "applicable",
            "derived": derived, "evidence": evidence, "issues": issues}


def exact_total(responses, checklist):
    """Independent CQA_SCORING_SPEC section 4 formula; None if no weighted criterion applies."""
    weighted = [c for c in checklist["criteria"] if c["kind"] != "critical"]
    weight = sum(c["weight"] for c in weighted if responses.get(c["criterion_id"]) != "N/A")
    if not weight:
        return None
    total = Fraction(0)
    for c in weighted:
        response = responses.get(c["criterion_id"])
        if response == "N/A":
            continue
        ratio = Fraction(response, max(c["levels"])) if c["kind"] == "discrete" else Fraction(int(response == "yes"))
        total += Fraction(100 * c["weight"], weight) * ratio
    return total


def round_half_up(value):
    """Two decimals, half away from zero (display of totals and of signed differences)."""
    hundredths = abs(value) * 100
    rounded = (2 * hundredths.numerator + hundredths.denominator) // (2 * hundredths.denominator)
    sign = "-" if value < 0 and rounded else ""
    return f"{sign}{rounded // 100}.{rounded % 100:02d}"
