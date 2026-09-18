from typing import Any, Mapping, Sequence, TypeVar

T = TypeVar("T", bound=Mapping[str, Any])


def is_excluded(item: Mapping[str, Any]) -> bool:
    """Return True if a chunk/document is structurally excluded."""
    if bool(item.get("excluded")):
        return True
    tags = item.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    lowered = {str(tag).lower() for tag in tags}
    return "excluded" in lowered or "exclude" in lowered


def filter_excluded(items: Sequence[T]) -> list[T]:
    """Drop excluded items. Called inside every retrieval layer."""
    return [item for item in items if not is_excluded(item)]
