"""Schema-constrained extraction. LLM output is untrusted: it is schema-validated, grounded in the
page text, sanitized, and anything unverifiable is dropped. Statuses are NOT decided here."""
import json
import re

from pydantic import ValidationError

from app.ai.client import LLMClient, complete_with_policy
from app.ai.errors import LLMOutputInvalid
from app.ai.models import ExtractedFact, ExtractionResult, WirePayload
from app.ai.prompts import PROMPT_VERSION, SCHEMA_VERSION, SYSTEM_PROMPT, build_user_prompt
from app.discovery.retry import RetryPolicy
from app.schemas.enums import ClaimType, OpportunityCategory

MAX_TEXT_CHARS = 30_000
MAX_FACTS = 30
_TAGS = re.compile(r"<[^>]*>")
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_DELIM = re.compile(r"</?\s*page_content\s*>", re.IGNORECASE)


def collapse_ws(text: str) -> str:
    return " ".join(text.split())


def sanitize(text: str, max_len: int) -> str:
    """Strip markup and control characters before the value can reach a UI."""
    return collapse_ws(_CTRL.sub("", _TAGS.sub("", text)))[:max_len]


def _wire_schema() -> dict:
    return WirePayload.model_json_schema()


async def extract_from_text(
    llm: LLMClient, page_text: str, *, source_observation_id: str,
    policy: RetryPolicy = RetryPolicy(max_attempts=3, timeout_s=60.0), sleep=None,
) -> ExtractionResult:
    text = collapse_ws(_DELIM.sub("", page_text))
    truncated = len(text) > MAX_TEXT_CHARS
    text = text[:MAX_TEXT_CHARS]
    kwargs = {"sleep": sleep} if sleep else {}
    raw = await complete_with_policy(
        llm, system=SYSTEM_PROMPT, user=build_user_prompt(text), schema=_wire_schema(),
        schema_name="opportunity_extraction", policy=policy, **kwargs)
    try:
        payload = WirePayload.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError):
        raise LLMOutputInvalid("output did not match schema") from None

    method = f"{llm.name}:{llm.model}:{PROMPT_VERSION}"
    result = ExtractionResult(truncated=truncated)
    if payload.opportunity_title:
        result.opportunity_title = sanitize(payload.opportunity_title, 300) or None
    if payload.opportunity_category:
        try:
            result.opportunity_category = OpportunityCategory(payload.opportunity_category.strip().lower())
        except ValueError:
            result.dropped.append("unknown opportunity category")

    if len(payload.facts) > MAX_FACTS:
        result.dropped.append(f"{len(payload.facts) - MAX_FACTS} facts over the limit")
    for wf in payload.facts[:MAX_FACTS]:
        kind = wf.claim_type
        excerpt = collapse_ws(wf.excerpt or "")
        value = sanitize(wf.extracted_value, 500)
        if not value:
            result.dropped.append(f"{kind}: empty value")
        elif not 0.0 <= wf.confidence <= 1.0:
            result.dropped.append(f"{kind}: confidence out of range")
        elif len(excerpt) < 3:
            result.dropped.append(f"{kind}: no supporting excerpt")
        else:
            start = text.find(excerpt)
            if start < 0:  # never keep an excerpt the page does not contain
                result.dropped.append(f"{kind}: excerpt not found in page")
                continue
            result.facts.append(ExtractedFact(
                claim_type=ClaimType(kind), extracted_value=value,
                excerpt=sanitize(excerpt, 300), evidence_locator=f"text:{start}-{start + len(excerpt)}",
                confidence=wf.confidence, source_observation_id=source_observation_id,
                extraction_method=method, schema_version=SCHEMA_VERSION))
    return result