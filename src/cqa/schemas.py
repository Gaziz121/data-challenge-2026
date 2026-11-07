"""Version 1 contracts. Strict types and unknown-field rejection are intentional."""

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

CONTRACT_VERSION = "1.0"
MODEL_OUTPUT_SCHEMA_VERSION = "1.1"
RawResponse = Union[Literal["yes", "no", "N/A"], int]
Violation = Literal["insult", "paid_service_bypassing_company", "confidential_disclosure"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Message(Contract):
    message_id: str = Field(min_length=1)
    source_message_id: Optional[Union[str, int]]
    source_index: int = Field(ge=0)
    timestamp: str = Field(min_length=1)
    source_speaker: str = Field(min_length=1)
    role: Literal["customer", "agent", "bot", "system"]
    text: str = Field(min_length=1)


class Conversation(Contract):
    schema_version: Literal["1.0"] = CONTRACT_VERSION
    conversation_id: str = Field(min_length=1)
    channel: Literal["chat", "voice"]
    language: str = Field(min_length=1)
    dataset_group_id: str = Field(min_length=1)
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    messages: list[Message] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_messages(self):
        if len({m.message_id for m in self.messages}) != len(self.messages):
            raise ValueError("Duplicate normalized message IDs")
        if [m.source_index for m in self.messages] != list(range(len(self.messages))):
            raise ValueError("Message order must preserve every original transcript index")
        return self


class FactPolicy(Contract):
    yes_roles: list[Literal["customer", "agent", "system", "bot"]] = Field(default_factory=list)
    yes_locator: Literal["any", "first_agent"] = "any"
    full_scope_answers: list[Literal["yes", "no", "not_applicable"]] = Field(default_factory=list)


class AtomicQuestion(Contract):
    question_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    violation_category: Optional[Violation] = None
    fact_policy: Optional[FactPolicy] = None

    @model_serializer(mode="wrap")
    def preserve_legacy_serialization(self, handler):
        value = handler(self)
        if self.fact_policy is None:
            value.pop("fact_policy", None)
        return value


class IdentificationPolicy(Contract):
    need_question_id: str
    verified_question_id: str
    verification_roles: list[Literal["agent", "system"]] = Field(default_factory=lambda: ["agent", "system"], min_length=1)
    action_roles: list[Literal["agent", "system"]] = Field(default_factory=lambda: ["agent", "system"], min_length=1)


class EvidencePolicy(Contract):
    positive_roles: list[Literal["agent", "system"]] = Field(default_factory=lambda: ["agent"], min_length=1)
    positive_locator: Literal["any", "first_agent"] = "any"
    negative_coverage: Literal["decision", "decision_and_atomic"] = "decision"

    @model_serializer(mode="wrap")
    def preserve_legacy_serialization(self, handler):
        value = handler(self)
        if self.negative_coverage == "decision":
            value.pop("negative_coverage", None)
        return value


class ConditionalRequirement(Contract):
    trigger_question_id: str = Field(min_length=1)
    required_when: Literal["yes", "no"]
    requirement_question_id: str = Field(min_length=1)


class BinaryDecisionRule(Contract):
    """Explicit conjunction, optionally including one conditional obligation."""
    all_of: list[str] = Field(min_length=1)
    conditional: Optional[ConditionalRequirement] = None
    source: str = Field(min_length=1)


class ApplicabilityRule(Contract):
    question_id: str = Field(min_length=1)
    na_when: Literal["yes", "no"]


class ConsistencyRule(Contract):
    question_id: str = Field(min_length=1)
    when_answer: Literal["yes", "no", "unknown", "not_applicable"]
    permitted_responses: list[RawResponse] = Field(min_length=1)


class Criterion(Contract):
    criterion_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    kind: Literal["binary", "discrete", "critical"]
    weight: int = Field(ge=0, le=10000)
    levels: list[int]
    anchors: dict[str, str]
    na_condition: Optional[str]
    questions: list[AtomicQuestion] = Field(min_length=1)
    applicability_rule: Optional[ApplicabilityRule]
    consistency_rules: list[ConsistencyRule] = Field(default_factory=list)
    evidence_policy: EvidencePolicy = Field(default_factory=EvidencePolicy)
    decision_rule: Optional[BinaryDecisionRule] = None
    output_source: Literal["model", "atomic"] = "model"
    identification_policy: Optional[IdentificationPolicy] = None

    @model_serializer(mode="wrap")
    def preserve_legacy_serialization(self, handler):
        value = handler(self)
        if self.decision_rule is None:
            value.pop("decision_rule", None)
        if self.output_source == "model":
            value.pop("output_source", None)
        if self.identification_policy is None:
            value.pop("identification_policy", None)
        return value

    @model_validator(mode="after")
    def valid_definition(self):
        if len({q.question_id for q in self.questions}) != len(self.questions):
            raise ValueError("Duplicate atomic question IDs")
        if self.output_source == "atomic" and (self.kind == "discrete" or self.kind == "binary" and not self.decision_rule):
            raise ValueError("Atomic output requires an explicit binary rule or mapped critical categories")
        if self.output_source == "atomic" and self.kind == "critical" and any(q.violation_category is None for q in self.questions):
            raise ValueError("Atomic critical output requires complete category mappings")
        if self.identification_policy:
            p = self.identification_policy
            if (self.kind != "binary" or not self.applicability_rule
                    or self.applicability_rule.question_id != p.need_question_id or self.applicability_rule.na_when != "no"
                    or p.need_question_id == p.verified_question_id
                    or not {p.need_question_id, p.verified_question_id} <= {q.question_id for q in self.questions}):
                raise ValueError("Identification policy requires distinct need/verification questions and no -> N/A")
        if self.decision_rule:
            rule = self.decision_rule
            refs = list(rule.all_of)
            if rule.conditional:
                refs += [rule.conditional.trigger_question_id, rule.conditional.requirement_question_id]
            if (self.kind != "binary" or len(refs) != len(set(refs))
                    or not set(refs) <= {q.question_id for q in self.questions}):
                raise ValueError("Binary decision rule requires distinct configured question references")
        if self.kind != "critical" and self.evidence_policy.negative_coverage != "decision":
            raise ValueError("Full negative category coverage applies only to critical criteria")
        categories = [q.violation_category for q in self.questions if q.violation_category is not None]
        if categories and (self.kind != "critical" or len(categories) != len(set(categories))
                           or len(categories) != len(self.questions)):
            raise ValueError("Category questions require a complete unique mapping on a critical criterion")
        if (self.na_condition is None) != (self.applicability_rule is None):
            raise ValueError("N/A condition and atomic applicability rule must be configured together")
        if self.applicability_rule and self.applicability_rule.question_id not in {
                q.question_id for q in self.questions}:
            raise ValueError("Applicability rule refers to an unknown atomic question")
        for rule in self.consistency_rules:
            if rule.question_id not in {q.question_id for q in self.questions}:
                raise ValueError("Consistency rule refers to an unknown atomic question")
            permitted = (self.levels if self.kind == "discrete" else ["yes", "no"]) + (
                ["N/A"] if self.na_condition is not None else [])
            if any(response not in permitted for response in rule.permitted_responses):
                raise ValueError("Consistency rule permits a response outside the configured scale")
        if self.na_condition is not None and not self.na_condition.strip():
            raise ValueError("N/A requires a nonempty allowed condition")
        if self.kind == "discrete":
            if (not self.levels or self.levels != sorted(set(self.levels))
                    or self.levels[0] != 0 or self.levels[-1] <= 0
                    or set(self.anchors) != {str(v) for v in self.levels}):
                raise ValueError("Discrete levels need zero, a positive maximum and all anchors")
        elif self.levels or self.anchors:
            raise ValueError("Binary/critical criteria cannot define numeric levels")
        if self.kind == "critical" and (self.weight or self.na_condition is not None):
            raise ValueError("Critical flags must be unweighted and cannot be N/A")
        return self


class Checklist(Contract):
    schema_version: Literal["1.0"] = CONTRACT_VERSION
    checklist_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source: str = Field(min_length=1)
    rounding: Literal["half_up_2dp"]
    rounding_note: str = Field(min_length=1)
    criteria: list[Criterion] = Field(min_length=1)
    decision_path: Literal["legacy", "atomic_first"] = "legacy"

    @model_serializer(mode="wrap")
    def preserve_legacy_serialization(self, handler):
        value = handler(self)
        if self.decision_path == "legacy":
            value.pop("decision_path", None)
        return value

    @model_validator(mode="after")
    def unique_criteria(self):
        if len({c.criterion_id for c in self.criteria}) != len(self.criteria):
            raise ValueError("Duplicate checklist criterion IDs")
        return self


class Evidence(Contract):
    kind: Literal["quote", "scope", "omission"]
    message_id: Optional[str]
    quote: Optional[str]
    start_message_id: Optional[str]
    end_message_id: Optional[str]
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_shape(self):
        if not self.explanation.strip():
            raise ValueError("Evidence explanation cannot be whitespace")
        if self.kind == "quote":
            if not self.message_id or not self.quote or not self.quote.strip():
                raise ValueError("A quote needs an exact excerpt and message ID")
            if self.start_message_id is not None or self.end_message_id is not None:
                raise ValueError("Quotes cannot also carry a scope")
        elif (not self.start_message_id or not self.end_message_id
              or self.message_id is not None or self.quote is not None):
            raise ValueError("Scope/omission requires two boundaries, without a fabricated quote")
        return self


class AtomicCheck(Contract):
    question_id: str = Field(min_length=1)
    answer: Literal["yes", "no", "unknown", "not_applicable"]
    rationale: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)


class EventEvidence(Contract):
    kind: Literal["protected_request", "protected_action", "verification"]
    message_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class AtomicObservation(AtomicCheck):
    events: list[EventEvidence]


class ApplicableJudgment(Contract):
    response: Union[Literal["yes", "no"], int]
    rationale: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    violation_categories: list[Violation]
    needs_review: bool
    review_reason: Optional[str]


class AtomicCriterionOutput(Contract):
    criterion_id: str = Field(min_length=1)
    atomic_checks: list[AtomicObservation] = Field(min_length=1)
    judgment: Optional[ApplicableJudgment]


class AtomicEvaluation(Contract):
    schema_version: Literal["1.2"]
    criteria: list[AtomicCriterionOutput] = Field(min_length=1)


def decision_metadata_issues(values):
    """Independent metadata constraints, shared by acceptance and diagnostics."""
    issues = []
    if "rationale" in values and not values["rationale"].strip():
        issues.append("Rationale cannot be whitespace")
    if "response" in values and "na_reason" in values:
        if values["response"] == "N/A":
            if not values["na_reason"] or not values["na_reason"].strip():
                issues.append("N/A requires a nonempty reason")
        elif values["na_reason"] is not None:
            issues.append("Applicable decisions must use null for na_reason")
    if "needs_review" in values and "review_reason" in values:
        if values["needs_review"]:
            if not values["review_reason"] or not values["review_reason"].strip():
                issues.append("Review marker requires a reason")
        elif values["review_reason"] is not None:
            issues.append("Unflagged decisions must use null for review_reason")
    if "violation_categories" in values and len(set(values["violation_categories"])) != len(values["violation_categories"]):
        issues.append("Duplicate critical categories")
    return issues


class Decision(Contract):
    criterion_id: str = Field(min_length=1)
    atomic_checks: list[AtomicCheck] = Field(min_length=1)
    response: RawResponse
    rationale: str = Field(min_length=1)
    na_reason: Optional[str] = Field(description=(
        'Must be JSON null unless response is exactly "N/A". If response is "N/A", '
        'provide a nonempty explanation of the configured N/A condition. '
        'For yes, no, or any numeric score use null, never an applicability explanation.'))
    evidence: list[Evidence] = Field(min_length=1)
    violation_categories: list[Violation]
    needs_review: bool
    review_reason: Optional[str]

    @model_validator(mode="after")
    def valid_reason(self):
        issues = decision_metadata_issues({name: getattr(self, name) for name in type(self).model_fields})
        if issues:
            raise ValueError("; ".join(issues))
        return self


class ModelEvaluation(Contract):
    schema_version: Literal["1.0", "1.1"]
    decisions: list[Decision] = Field(min_length=1)


class ApplicabilityConstraint(Contract):
    criterion_id: str
    na_allowed: bool
    allowed_condition: Optional[str]
    rule: Optional[ApplicabilityRule]


class PreEvaluationFacts(Contract):
    extractor_version: Literal["structural-v1"] = "structural-v1"
    message_count: int
    role_counts: dict[str, int]
    first_agent_message_id: Optional[str]
    last_agent_message_id: Optional[str]
    applicability_constraints: list[ApplicabilityConstraint]


class CheckFinding(Contract):
    code: str = Field(min_length=1)
    severity: Literal["info", "review", "block"]
    criterion_ids: list[str]
    explanation: str = Field(min_length=1)


class CheckOutcome(Contract):
    check_name: str = Field(min_length=1)
    check_version: str = Field(min_length=1)
    phase: Literal["pre_evaluation", "post_validation"]
    findings: list[CheckFinding]


class AuditEvent(Contract):
    stage: str
    component_version: str
    outcome: Literal["passed", "review", "blocked"]
    artifact_sha256: str


class CheckInput(Contract):
    conversation: Conversation
    checklist: Checklist
    facts: PreEvaluationFacts
    evaluation: Optional[ModelEvaluation]


class CriterionScore(Contract):
    criterion_id: str
    applicable: bool
    base_weight: int
    effective_weight: str
    earned_points: str


class OverallScore(Contract):
    total_score: Optional[str]
    total_exact_numerator: Optional[int]
    total_exact_denominator: Optional[int]
    applicable_weight: int
    critical_violation: bool
    violation_categories: list[Violation]
    criteria: list[CriterionScore]
    rounding: Literal["half_up_2dp"]


class EvaluationConfig(Contract):
    strategy: Literal["single_pass"] = "single_pass"
    prompt_version: Literal["baseline-v1", "baseline-v2", "baseline-v3", "baseline-v4", "atomic-v1", "atomic-v2", "atomic-v3"] = "baseline-v4"
    max_output_tokens: int = Field(default=8000, ge=256, le=32000)
    timeout_seconds: int = Field(default=90, ge=1, le=300)
    external_synthetic_allowed: bool = False
    quote_policy: Literal["exact", "normalize_formatting"] = "exact"


class EvidenceRepair(Contract):
    criterion_id: str
    evidence_path: str
    message_id: str
    original_quote: str
    source_quote: str
    source_start: int
    source_end: int
    policy: Literal["formatting-v1"] = "formatting-v1"


class InputAuthorization(Contract):
    policy_version: Literal["1.0"] = "1.0"
    data_class: Literal["synthetic_test", "organizer_control", "organizer_dev"]
    source: Literal["approved_dev", "local_manifest"]
    conversation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorization_reference: str
    permission: Literal["local_evaluation", "external_openai"]


class RunMetadata(Contract):
    engine_version: str
    python_version: str
    pydantic_version: str
    provider: str
    model_requested: str
    model_returned: str
    is_mock: bool
    started_at: str
    latency_ms: int = Field(ge=0)
    provider_latency_ms: int = Field(ge=0)
    response_id: Optional[str]
    usage: dict[str, int]
    prompt_sha256: str
    checklist_sha256: str
    configuration: EvaluationConfig
    input_authorization: Optional[InputAuthorization] = None


class DecisionRevision(Contract):
    """Future explicit revisions: proposed changes never silently replace the maker."""
    revision_id: str
    actor: str
    source: Literal["checker", "human"]
    created_at: str
    reason: str = Field(min_length=1)
    original: Decision
    proposed: Decision
    state: Literal["proposed", "accepted", "rejected"]


class DecisionRuleAssessment(Contract):
    criterion_id: str
    rule_source: str
    model_response: Optional[RawResponse]
    derived_response: Optional[Literal["yes", "no", "N/A"]]
    status: Literal["agreed", "disagreed", "undetermined"]
    issues: list[str]


class CoverageProof(Contract):
    """Locator coverage, not proof of model attention or semantic correctness."""
    criterion_id: str
    evidence_path: list[Union[str, int]]
    conversation_sha256: str
    messages_sha256: str
    required_message_ids: list[str]
    covered_message_ids: list[str]
    missing_message_ids: list[str]
    invalid_scope_indices: list[int]
    complete: bool


class CriterionReview(Contract):
    criterion_id: str
    state: Literal["accepted_derived", "accepted_model", "needs_review", "invalid_facts", "schema_invalid", "conflict"]
    decision_origin: Literal["derived", "model"]
    response: Optional[RawResponse] = None
    original_judgment: Optional[dict] = None
    issues: list[str] = Field(default_factory=list)
    rule_source: Optional[str] = None
    atomic_answers: dict[str, str] = Field(default_factory=dict)


class RepairPolicy(Contract):
    """Explicit opt-in for ONE bounded criterion repair call. Absent means disabled."""
    authorization: str = Field(min_length=1)
    max_additional_calls: Literal[1] = 1

    @model_validator(mode="after")
    def explicit(self):
        if not self.authorization.strip():
            raise ValueError("Repair requires an explicit authorization reference")
        return self


class RepairAttempt(Contract):
    """Full audit of one repair attempt; the primary reply is never modified."""
    prompt_version: str
    base_prompt_version: str
    authorization: str
    status: Literal["merged", "rejected_output", "provider_error", "not_attempted"]
    criterion_ids: list[str]
    original_issues: list[dict]
    pinned_answers: dict[str, str] = Field(default_factory=dict)
    answer_changes: list[dict] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    request_sha256: Optional[str] = None
    repair_output: Optional[Any] = None
    merged_output: Optional[dict] = None
    model_returned: Optional[str] = None
    response_id: Optional[str] = None
    usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: int = Field(default=0, ge=0)


class EvaluationResult(Contract):
    schema_version: Literal["1.0"] = CONTRACT_VERSION
    evaluation_id: str
    status: Literal["mock_only", "needs_review", "structurally_valid"]
    conversation: Conversation
    checklist: Checklist
    model_evaluation: ModelEvaluation
    validated_evaluation: Optional[ModelEvaluation] = None
    evidence_repairs: list[EvidenceRepair] = Field(default_factory=list)
    score: OverallScore
    run: RunMetadata
    facts: PreEvaluationFacts
    check_outcomes: list[CheckOutcome]
    audit: list[AuditEvent]
    revision_history: list[DecisionRevision]
    decision_rule_checks: list[DecisionRuleAssessment] = Field(default_factory=list)
    coverage_proofs: list[CoverageProof] = Field(default_factory=list)
    decision_path: Literal["legacy", "atomic_first"] = "legacy"
    original_provider_output: Optional[dict] = None
    criterion_reviews: list[CriterionReview] = Field(default_factory=list)
    repair_attempts: list[RepairAttempt] = Field(default_factory=list)
