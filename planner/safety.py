"""Safety guardrail for minors, checked in code BEFORE any LLM call.

A keyword list misses things, so the system prompt also tells the model to refer;
this layer guarantees the obvious cases never depend on the model.
"""
CRISIS_KEYWORDS = [
    "想死", "不想活", "活不下去", "活著沒意義", "自殺", "輕生", "自殘", "割腕",
    "傷害自己", "結束生命", "消失就好", "跳樓",
]

CRISIS_REPLY = """謝謝你願意說出來，聽起來你現在真的很辛苦。這件事比選課、升學都重要得多。

我是 AI，沒辦法好好陪你處理這麼重要的感受，請你現在就找真人聊聊：
- **安心專線 1925**（24 小時，免付費）
- **生命線 1995**
- **張老師專線 1980**
- 明天到學校時，也可以直接去**輔導室**找老師，或告訴你信任的導師、家人。

如果你現在有立即的危險，請撥 **119** 或 **110**。

你不需要一個人扛著。"""


def is_crisis(text: str) -> bool:
    compact = text.replace(" ", "")
    return any(k in compact for k in CRISIS_KEYWORDS)
