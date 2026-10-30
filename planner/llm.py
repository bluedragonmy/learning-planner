"""Claude client and model choices.

The API key is read from ANTHROPIC_API_KEY, or from a `.env` file in the
project root (gitignored) containing `ANTHROPIC_API_KEY=...`.
"""
import os
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent

# One place to change models. Opus at low effort keeps a chat turn fast;
# swap to "claude-haiku-5-5" if cost matters more than conversation quality.
ADVISOR_MODEL = "claude-opus-5-5"
ADVISOR_EFFORT = "low"
# The simulated student in eval/ only needs to role-play.
STUDENT_MODEL = "claude-haiku-5-5"

# USD per million tokens (input, output)
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def make_client() -> anthropic.Anthropic:
    _load_dotenv()
    return anthropic.Anthropic()


def cost_usd(model: str, usage) -> float:
    p_in, p_out = PRICES.get(model, (0.0, 0.0))
    return usage.input_tokens * p_in / 1e6 + usage.output_tokens * p_out / 1e6
