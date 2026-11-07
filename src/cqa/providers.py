"""Replaceable single-pass providers; only OpenAIProvider performs network I/O."""

from dataclasses import dataclass
import json
import os
import time
from typing import Any, Protocol
import urllib.error
import urllib.request

from .io import parse_json
from .loader import require_approved_synthetic
from .schemas import Checklist, Conversation, EvaluationConfig, MODEL_OUTPUT_SCHEMA_VERSION


class ProviderError(RuntimeError):
    """Safe public errors: never contain a raw response, transcript or secret."""


@dataclass(frozen=True)
class ProviderReply:
    evaluation: Any
    model: str
    response_id: Any = None
    usage: Any = None
    latency_ms: int = 0


class Provider(Protocol):
    name: str
    model: str
    is_mock: bool

    def evaluate(self, conversation: Conversation, checklist: Checklist,
                 request: dict, config: EvaluationConfig) -> ProviderReply:
        ...


class MockProvider:
    """A wiring fixture, not a heuristic evaluator or a set of conversation answers.

    Always returns the lowest applicable level, with the entire inspected scope.
    Every decision explicitly requires review. Deterministic across all input IDs.
    """
    name = "mock"
    model = "deterministic-fixture-v1"
    is_mock = True

    def evaluate(self, conversation, checklist, request, config):
        scope = {"kind": "scope", "message_id": None, "quote": None,
                 "start_message_id": conversation.messages[0].message_id,
                 "end_message_id": conversation.messages[-1].message_id,
                 "explanation": "MOCK: scope locator fixture only; no semantic assessment performed."}
        decisions = []
        for criterion in checklist.criteria:
            decisions.append({"criterion_id": criterion.criterion_id,
                              "response": min(criterion.levels) if criterion.kind == "discrete" else "no",
                              "rationale": "MOCK: fixed lowest-level fixture, not a quality judgment.",
                              "na_reason": None, "evidence": [scope.copy()], "violation_categories": [],
                              "needs_review": True, "review_reason": "Mock provider does not assess conversations.",
                              "atomic_checks": [{"question_id": q.question_id, "answer": "unknown",
                                                 "rationale": "MOCK: atomic check not assessed.",
                                                 "evidence": [scope.copy()]} for q in criterion.questions]})
        return ProviderReply({"schema_version": MODEL_OUTPUT_SCHEMA_VERSION, "decisions": decisions}, model=self.model, usage={})


class OpenAIProvider:
    """Responses API with strict JSON Schema, no SDK, no retries, no stored response.

    A transport can be injected for offline HTTP contract tests. Default access
    remains exact approved DEV; an explicit content-bound policy can authorize
    other transcripts. Both gates run before transport.
    """
    name = "openai"
    is_mock = False
    ENDPOINT = "https://api.openai.com/v1/responses"

    def __init__(self, model, api_key=None, transport=None, input_policy=None):
        if not isinstance(model, str) or not model.strip():
            raise ProviderError("An explicit structured-output-capable model is required")
        self.model = model
        self._key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self._transport = transport or self._post
        self._input_policy = input_policy

    def _post(self, payload, timeout):
        request = urllib.request.Request(
            self.ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + self._key, "Content-Type": "application/json"},
            method="POST")
        # Reject redirects: Authorization must never follow an unexpected target.
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(request, timeout=timeout) as response:
                return parse_json(response.read())
        except urllib.error.HTTPError as error:
            raise ProviderError(f"OpenAI HTTP {error.code}; response body withheld") from None
        except (OSError, ValueError):
            raise ProviderError("OpenAI transport failed or returned invalid JSON; details withheld") from None

    def evaluate(self, conversation, checklist, request, config):
        if self._input_policy is None:
            require_approved_synthetic(conversation, config.external_synthetic_allowed)
        else:
            self._input_policy.authorize(conversation, "openai")
        if not self._key or not self._key.strip():
            raise ProviderError("OPENAI_API_KEY is not configured; no request sent")
        # Rebuild from validated inputs: a caller cannot inject a different transcript
        # into the request while presenting an approved conversation to the data gate.
        from .prompt import build_request
        expected_request, _ = build_request(conversation, checklist)
        if request != expected_request:
            raise ProviderError("Provider request does not match validated inputs")
        payload = {"model": self.model, "instructions": request["instructions"],
                   "input": request["input"], "store": False,
                   "max_output_tokens": config.max_output_tokens,
                   "text": {"format": {"type": "json_schema", "name": "cqa_evaluation_v1_1",
                                       "strict": True, "schema": request["schema"]}}}
        started = time.perf_counter()
        try:
            response = self._transport(payload, config.timeout_seconds)
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("Provider transport failed; details withheld") from None
        elapsed = round((time.perf_counter() - started) * 1000)
        try:
            if not isinstance(response, dict) or response.get("status") != "completed":
                raise ValueError("Incomplete response")
            chunks = []
            for item in response.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") == "refusal":
                        raise ValueError("Refusal")
                    if content.get("type") == "output_text":
                        chunks.append(content["text"])
            if not chunks:
                raise ValueError("No structured output")
            evaluation = parse_json("".join(chunks))
            model, response_id = response["model"], response["id"]
            if not isinstance(model, str) or not model or not isinstance(response_id, str) or not response_id:
                raise ValueError("Missing provider provenance")
            usage = response.get("usage") or {}
            counts = {key: usage[key] for key in ("input_tokens", "output_tokens", "total_tokens") if key in usage}
            for field, detail, label in (("input_tokens_details", "cached_tokens", "cached_input_tokens"),
                                         ("output_tokens_details", "reasoning_tokens", "reasoning_tokens")):
                if isinstance(usage.get(field), dict) and detail in usage[field]:
                    counts[label] = usage[field][detail]
            if any(type(v) is not int or v < 0 for v in counts.values()):
                raise ValueError("Invalid token usage")
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ProviderError("OpenAI output invalid, refused or incomplete; no score produced") from None
        return ProviderReply(evaluation, model=model, response_id=response_id, usage=counts, latency_ms=elapsed)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
