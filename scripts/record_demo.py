"""Record one real session for the static GitHub Pages demo.

    python scripts/record_demo.py

Runs the real pipeline once (photo reading → session with the agent → summary) as a
fictional student and saves every response to demo/recording.json. The Pages demo
replays these, so visitors can click through without a server or an API key.
Costs about US$0.2 per run.
"""
import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from planner.agent import Advisor                      # noqa: E402
from planner.app import stages as stages_endpoint      # noqa: E402
from planner.extract import extract                    # noqa: E402
from planner.profile import StudentProfile             # noqa: E402
from planner.session import SessionContext, kickoff_message, suggest_strengths  # noqa: E402
from planner.summary import summarize                  # noqa: E402

DEMO = ROOT / "demo"
FONT = "C:/Windows/Fonts/msjh.ttc"

PERSONA = {
    "name": "小羽",
    "stage": "junior_high",
    "topics": ["選高中還是高職、五專", "跟家人的想法不一樣"],
    "note": "爸媽希望我讀普通高中，但我比較想讀設計",
    "clarity_before": 2,
    "grades": [("國文", 84), ("英文", 76), ("數學", 58), ("自然", 65), ("社會", 79), ("藝術", 96), ("科技", 88)],
    "lines": [
        "我國二，美術課是我最有成就感的課，平常也會自己畫插畫、剪影片",
        "數學一直不太好，爸媽覺得讀普通高中以後選擇比較多",
        "如果去讀設計群的高職，以後還可以上大學嗎？",
    ],
}


def make_report_card(path: Path) -> bytes:
    font, small = ImageFont.truetype(FONT, 30), ImageFont.truetype(FONT, 22)
    img = Image.new("RGB", (900, 640), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 28), "示範國中 114學年度第1學期 成績單", fill="black", font=font)
    d.text((40, 76), "（展示用假資料）  姓名：林小羽   班級：802", fill="#555", font=small)
    for i, (subject, score) in enumerate(PERSONA["grades"]):
        y = 140 + i * 62
        d.rectangle((40, y, 620, y + 54), outline="black")
        d.text((64, y + 10), subject, fill="black", font=font)
        d.text((460, y + 10), str(score), fill="black", font=font)
    img.save(path)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    DEMO.mkdir(exist_ok=True)
    jpeg = make_report_card(DEMO / "sample-report.png")
    advisor = Advisor()
    total = 0.0

    data, usd = extract(advisor.client, "grades", base64.b64encode(jpeg).decode(), "image/jpeg")
    total += usd
    grades = {i["subject"]: i["score"] for i in data["items"]}
    strong, weak = suggest_strengths(grades)
    print("extract:", grades, strong, weak)

    # what the browser does when the student accepts the suggestions
    profile = StudentProfile(stage=PERSONA["stage"])
    for s in strong:
        profile.add_item("strong_subjects", s, f"成績單照片：{s} {grades[s]:g}")
    for s in weak:
        profile.add_item("weak_subjects", s, f"成績單照片：{s} {grades[s]:g}")

    session = SessionContext(topics=PERSONA["topics"], note=PERSONA["note"],
                             clarity_before=PERSONA["clarity_before"], session_number=1)
    turns, history = [], []
    for message in [kickoff_message(session), *PERSONA["lines"]]:
        turn = advisor.reply(message, profile, history, session)
        profile, total = turn.profile, total + turn.usd
        history += [{"role": "user", "content": message}, {"role": "assistant", "content": turn.text}]
        turns.append({"reply": turn.text, "profile": profile.model_dump(), "trace": turn.trace,
                      "usd": round(turn.usd, 4), "seconds": round(turn.seconds, 1),
                      "action_updates": turn.action_updates, "user_message": message})
        print(f"\n[{len(turns)}] {turn.trace}\n{turn.text[:160]}")

    chat = [{"role": m["role"], "content": m["content"], "hidden": i == 0} for i, m in enumerate(history)]
    summary, usd = summarize(advisor.client, chat, profile, PERSONA["topics"])
    total += usd
    print("\nsummary:", json.dumps(summary, ensure_ascii=False, indent=1))

    recording = {
        "persona": {k: v for k, v in PERSONA.items() if k != "grades"},
        "stages": stages_endpoint(),
        "profile_new": StudentProfile(stage=PERSONA["stage"]).model_dump(),
        "extract": {"data": data, "strong": strong, "weak": weak, "usd": 0},
        "turns": turns,
        "summary": {"summary": summary, "usd": 0},
    }
    (DEMO / "recording.json").write_text(json.dumps(recording, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nsaved demo/recording.json  (US${total:.3f})")


if __name__ == "__main__":
    main()
