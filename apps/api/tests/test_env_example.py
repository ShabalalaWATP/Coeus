import re
from pathlib import Path

from coeus.core.config import Settings

ROOT = Path(__file__).resolve().parents[3]
ENV_KEY = re.compile(r"^(?:#\s*)?(COEUS_[A-Z0-9_]+)=")


def test_env_example_covers_every_supported_setting() -> None:
    documented = {
        match.group(1)
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if (match := ENV_KEY.match(line))
    }
    supported = {f"COEUS_{name.upper()}" for name in Settings.model_fields}

    assert documented == supported
