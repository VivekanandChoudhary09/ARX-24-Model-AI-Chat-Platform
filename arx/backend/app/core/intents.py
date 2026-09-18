import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IntentRule:
    name: str
    pattern: re.Pattern[str]
    tags: tuple[str, ...]


INTENT_RULES: tuple[IntentRule, ...] = (
    IntentRule(
        name="pricing",
        pattern=re.compile(r"\b(pricing|price per|cost per|how much does|token cost)\b", re.I),
        tags=("pricing",),
    ),
    IntentRule(
        name="quota",
        pattern=re.compile(r"\b(quota|rate limit|token budget|monthly limit)\b", re.I),
        tags=("quota",),
    ),
    IntentRule(
        name="security",
        pattern=re.compile(r"\b(security perimeter|internal api key|jwt session|origin guard)\b", re.I),
        tags=("security",),
    ),
    IntentRule(
        name="rag",
        pattern=re.compile(r"\b(hybrid rag|retrieval layer|chroma|fastembed)\b", re.I),
        tags=("rag",),
    ),
    IntentRule(
        name="arx_intent_ping",
        pattern=re.compile(r"\bARX_INTENT_PING\b"),
        tags=("intent-target",),
    ),
)


def match_intent(query: str) -> IntentRule | None:
    for rule in INTENT_RULES:
        if rule.pattern.search(query):
            return rule
    return None
