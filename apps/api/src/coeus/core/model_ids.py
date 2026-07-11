import re
from collections.abc import Iterable

MODEL_ID_MIN_LENGTH = 2
MODEL_ID_MAX_LENGTH = 80
MAX_MODELS_PER_SOURCE = 200
MODEL_ID_PATTERN = r"^[A-Za-z0-9._:/-]+$"
_MODEL_ID_RE = re.compile(MODEL_ID_PATTERN)


def is_valid_model_id(value: str) -> bool:
    return (
        MODEL_ID_MIN_LENGTH <= len(value) <= MODEL_ID_MAX_LENGTH
        and _MODEL_ID_RE.fullmatch(value) is not None
    )


def clean_model_ids(values: Iterable[object], *, limit: int = MAX_MODELS_PER_SOURCE) -> list[str]:
    """Return a deterministic, bounded list of safe provider model IDs."""
    cleaned = {
        candidate
        for value in values
        if isinstance(value, str)
        if (candidate := value.strip()) and is_valid_model_id(candidate)
    }
    return sorted(cleaned)[:limit]
