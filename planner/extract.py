"""Read a photo of a report card or an interest-test result with Claude vision.

The output is only a draft: the UI shows it as an editable table and nothing
reaches the profile until the student confirms.
"""
import json

from planner.llm import ADVISOR_MODEL, cost_usd

GRADES_SCHEMA = {
    "type": "object",
    "properties": {
        "readable": {"type": "boolean", "description": "圖片是否為看得懂的成績單"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"subject": {"type": "string"}, "score": {"type": "number"}},
                "required": ["subject", "score"],
                "additionalProperties": False,
            },
        },
        "notes": {"type": "string", "description": "看不清楚或不確定的地方"},
    },
    "required": ["readable", "items", "notes"],
    "additionalProperties": False,
}

INTEREST_SCHEMA = {
    "type": "object",
    "properties": {
        "readable": {"type": "boolean", "description": "圖片是否為看得懂的興趣測驗結果"},
        "scores": {
            "type": "object",
            "properties": {k: {"type": "number"} for k in "RIASEC"},
            "required": list("RIASEC"),
            "additionalProperties": False,
        },
        "scale_max": {"type": "number", "description": "分數的滿分，例如百分等級為 100"},
        "notes": {"type": "string", "description": "看不清楚或不確定的地方、量表名稱"},
    },
    "required": ["readable", "scores", "scale_max", "notes"],
    "additionalProperties": False,
}

PROMPTS = {
    "grades": "這是一張台灣中學生的成績單照片。列出每個科目和分數（學期總成績；若有多個學期取最新一學期）。"
              "科目名稱照成績單上寫的，不要自己改名。看不清楚的科目不要猜，寫在 notes。",
    "interest": "這是一張興趣測驗（Holland 何倫碼：R 實用、I 研究、A 藝術、S 社會、E 企業、C 事務）的結果。"
                "讀出六個類型的分數與滿分（百分等級滿分是 100）。量表名稱與不確定的地方寫在 notes。",
}
SCHEMAS = {"grades": GRADES_SCHEMA, "interest": INTEREST_SCHEMA}


def extract(client, kind: str, image_b64: str, media_type: str, model: str = ADVISOR_MODEL) -> tuple[dict, float]:
    if kind not in SCHEMAS:
        raise ValueError(f"不支援的類型：{kind}")
    response = client.beta.messages.create(
        model=model,
        max_tokens=4000,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
            {"type": "text", "text": PROMPTS[kind]},
        ]}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMAS[kind]}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    usd = cost_usd(model, response.usage)
    if response.stop_reason == "refusal":
        raise RuntimeError("AI 無法讀取這張圖片，請改用手動輸入。")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text), usd
