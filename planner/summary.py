"""Turn a finished session's chat into the 會談紀錄 the student keeps and can show a teacher.

The summary never proposes next actions: per the user's design decision the
student writes those themselves.
"""
import json

from planner.llm import ADVISOR_MODEL, cost_usd
from planner.profile import StudentProfile
from planner.textutil import strip_emoji

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "talked_about": {"type": "array", "items": {"type": "string"},
                         "description": "今天聊了什麼，3–5 點，每點一句"},
        "discoveries": {"type": "array", "items": {"type": "string"},
                        "description": "學生今天對自己的新發現，用學生的角度寫（「你發現…」），1–3 點"},
        "questions_for_teacher": {"type": "array", "items": {"type": "string"},
                                  "description": "建議學生帶去問課諮師／輔導老師的問題，1–3 個"},
    },
    "required": ["talked_about", "discoveries", "questions_for_teacher"],
    "additionalProperties": False,
}

SYSTEM = """你負責把中學生和 AI 學習規劃助理「小航」的一次會談，整理成會談紀錄。
- 只根據對話內容，不要加入對話裡沒有的事。
- 口吻溫和、簡短，對象是學生本人。不要使用表情符號（emoji）。
- 不要替學生訂下一步行動（學生會自己寫）。
- 對話中若有危機訊息，talked_about 寫「有聊到心情與壓力，已建議找輔導室」，不要寫細節。"""


def summarize(client, chat: list[dict], profile: StudentProfile, topics: list[str],
              model: str = ADVISOR_MODEL) -> tuple[dict, float]:
    transcript = "\n".join(f"{'學生' if m['role'] == 'user' else '小航'}：{m['content']}"
                           for m in chat if not m.get("hidden"))
    user = (f"學生選的議題：{'、'.join(topics) or '無'}\n\n"
            f"會談後的學生側寫：\n{profile.summary()}\n\n對話：\n{transcript}")
    response = client.beta.messages.create(
        model=model,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SUMMARY_SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    usd = cost_usd(model, response.usage)
    if response.stop_reason == "refusal":
        return {"talked_about": ["（這次會談無法自動整理）"], "discoveries": [], "questions_for_teacher": []}, usd
    data = json.loads(next(b.text for b in response.content if b.type == "text"))
    return {k: [strip_emoji(x) for x in v] for k, v in data.items()}, usd
