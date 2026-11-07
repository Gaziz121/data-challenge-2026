"""Internal ingress and content-bound approvals, provisioned by the local owner.

No HTTP request can create an approval. A manifest is an owner's authorization
record, not independent proof of organizer permission. Unknown/private input is
denied. Audio is neither fetched nor included in the normalized export.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from .io import digest, parse_json
from .loader import normalize_record, require_approved_synthetic
from .schemas import Contract, InputAuthorization


class AccessDenied(ValueError):
    pass


class ConversationInput(Contract):
    dataset_group_id: str = Field(min_length=1, max_length=256)
    record: dict[str, Any]

    def normalize(self):
        cid = self.record.get("conversation_id")
        if not isinstance(cid, str) or not cid.strip() or cid != cid.strip():
            raise ValueError("Invalid conversation ID")
        return normalize_record(self.record, self.dataset_group_id,
                                digest(self.model_dump(mode="json")))


def conversation_fingerprint(conversation):
    # File/envelope byte hashes may vary on re-import. All normalized messages,
    # group, source-record hash, source IDs/order/timestamps remain bound.
    return digest(conversation.model_dump(mode="json", exclude={"dataset_sha256"}))


class InputGrant(Contract):
    conversation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_class: Literal["synthetic_test", "organizer_control", "organizer_dev"]
    authorization_reference: str = Field(min_length=1, max_length=512)
    external_providers: list[Literal["openai"]] = Field(default_factory=list)
    expires_at: str

    @model_validator(mode="after")
    def valid_grant(self):
        expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        if expiry.tzinfo is None or not self.authorization_reference.strip():
            raise ValueError("Approval needs an aware expiry and a nonempty reference")
        if len(set(self.external_providers)) != len(self.external_providers):
            raise ValueError("Duplicate provider permission")
        return self


class AuthorizationManifest(Contract):
    schema_version: Literal["1.0"] = "1.0"
    grants: list[InputGrant]

    @model_validator(mode="after")
    def unique_grants(self):
        if len({g.conversation_sha256 for g in self.grants}) != len(self.grants):
            raise ValueError("Duplicate content approval")
        return self


class InputPolicy:
    def __init__(self, manifest=None, *, allow_external=False):
        self._manifest = AuthorizationManifest.model_validate(
            (manifest or AuthorizationManifest(grants=[])).model_dump()).model_copy(deep=True)
        self.allow_external = allow_external

    @classmethod
    def from_path(cls, path=None, *, allow_external=False):
        manifest = AuthorizationManifest.model_validate(parse_json(Path(path).read_bytes())) if path else None
        return cls(manifest, allow_external=allow_external)

    def authorize(self, conversation, provider="mock"):
        fingerprint = conversation_fingerprint(conversation)
        grant = next((g for g in self._manifest.grants if g.conversation_sha256 == fingerprint), None)
        if grant is None:
            raise AccessDenied("Unapproved/private input: no matching local authorization")
        if datetime.fromisoformat(grant.expires_at.replace("Z", "+00:00")) <= datetime.now(timezone.utc):
            raise AccessDenied("Input authorization expired")
        if provider != "mock" and (not self.allow_external or provider not in grant.external_providers):
            raise AccessDenied("External export is not authorized for this content and provider")
        return InputAuthorization(data_class=grant.data_class, source="local_manifest",
                                  conversation_sha256=fingerprint,
                                  authorization_reference=grant.authorization_reference,
                                  permission="local_evaluation" if provider == "mock" else "external_openai")


def dev_authorization(conversation):
    require_approved_synthetic(conversation, True)
    return InputAuthorization(data_class="synthetic_test", source="approved_dev",
                              conversation_sha256=conversation_fingerprint(conversation),
                              authorization_reference="reviewed-dev-synthetic-60",
                              permission="local_evaluation")


class ExportPolicy:
    """Preserve the exact DEV gate; extend it only via explicit owner grants."""
    def __init__(self, input_policy, allow_dev=False):
        self.input_policy, self.allow_dev = input_policy, allow_dev

    def authorize(self, conversation, provider="openai"):
        if self.allow_dev:
            try:
                receipt = dev_authorization(conversation)
            except ValueError:
                pass
            else:
                return receipt.model_copy(update={"permission": "external_openai"})
        return self.input_policy.authorize(conversation, provider)


def main():
    parser = argparse.ArgumentParser(description="Fingerprint an internal ConversationInput JSON; does not grant approval")
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        value = ConversationInput.model_validate(parse_json(args.input.read_bytes())).normalize()
        print(json.dumps({"conversation_sha256": conversation_fingerprint(value)}))
    except (OSError, ValueError, TypeError, KeyError):
        parser.exit(1, "Invalid or unavailable local conversation input; details withheld\n")


if __name__ == "__main__":
    main()
