"""Opt-in formatting equivalence, with exact source spans and original quotes.

No fuzzy matching, case folding, spelling/letter changes or cross-message search.
The strict validator is deliberately unchanged by this optional preparation step.
"""

import unicodedata

from .schemas import EvidenceRepair, ModelEvaluation

QUOTES = {"«": '"', "»": '"', "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'"}


def _mapped_normalization(text):
    characters, spans = [], []
    index = 0
    while index < len(text):
        start = index
        index += 1
        while index < len(text) and unicodedata.combining(text[index]):
            index += 1
        cluster = unicodedata.normalize("NFC", text[start:index])
        for character in cluster:
            character = QUOTES.get(character, character)
            if character.isspace():
                if characters and characters[-1] == " ":
                    spans[-1] = (spans[-1][0], index)
                    continue
                character = " "
            characters.append(character)
            spans.append((start, index))
    return "".join(characters), spans


def normalize_evidence(evaluation, conversation):
    value = evaluation.model_dump()
    messages = {m.message_id: m for m in conversation.messages}
    repairs = []
    for decision in value["decisions"]:
        references = [(f"evidence.{i}", e) for i, e in enumerate(decision["evidence"])]
        references += [(f"atomic_checks.{i}.evidence.{j}", e)
                       for i, atomic in enumerate(decision["atomic_checks"]) for j, e in enumerate(atomic["evidence"])]
        for path, reference in references:
            message = messages.get(reference["message_id"])
            quote = reference["quote"]
            if reference["kind"] != "quote" or message is None or quote in message.text:
                continue
            target = _mapped_normalization(quote)[0].strip()
            source, spans = _mapped_normalization(message.text)
            start = source.find(target) if target else -1
            if start < 0 or source.find(target, start + 1) >= 0:
                continue  # Unmatched or ambiguous references remain invalid, never guessed.
            a, b = spans[start][0], spans[start + len(target) - 1][1]
            exact = message.text[a:b]
            reference["quote"] = exact
            repairs.append(EvidenceRepair(criterion_id=decision["criterion_id"], evidence_path=path,
                                          message_id=message.message_id, original_quote=quote,
                                          source_quote=exact, source_start=a, source_end=b))
    return ModelEvaluation.model_validate(value), repairs
