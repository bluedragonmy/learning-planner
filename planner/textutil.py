"""Small text helpers shared by the agent and the summary."""
import re

# pictographs, symbols, flags, dingbats, variation selectors, zero-width joiner
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U0000FE0F\U0000200D\U00002B50\U00002B06\U00002934\U00002935]"
)


def strip_emoji(text: str) -> str:
    """The UI has its own drawn icons; emoji from the model clash with it, so they are removed."""
    out = _EMOJI.sub("", text)
    return re.sub(r"[ \t]+\n", "\n", re.sub(r" {2,}", " ", out)).strip()
