"""Token estimation without external deps.

Haiku/Claude tokenizers average ~3.6 chars/token for mixed EN/PT prose
with markdown. Good enough for budget enforcement; swap in a real
tokenizer later if exact counts matter.
"""

CHARS_PER_TOKEN = 3.6


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / CHARS_PER_TOKEN))
