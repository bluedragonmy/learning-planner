"""Advising sessions, modeled on NTU's 學習規劃辦公室 flow:

    會談前：選議題、方向清楚度（1–5）、可上傳成績單／興趣測驗
    會談中：對話；若有上次的行動，先關心進度
    會談後：學生自己寫下一步行動 → 自評表（填完才能開下一次）→ 會談紀錄

Sessions themselves are stored in the browser; this module holds the parts the
server needs: what the agent should know at the start, and pure helpers.
"""
from statistics import mean
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from planner.profile import HOLLAND

ACTION_STATUSES = ["還沒開始", "進行中", "完成", "不做了"]


class Action(BaseModel):
    """A next step the student wrote themselves at the end of a session."""
    id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=80)
    status: Literal["還沒開始", "進行中", "完成", "不做了"] = "還沒開始"
    note: str = Field("", max_length=200)


class SessionContext(BaseModel):
    topics: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(default_factory=list, max_length=12)
    note: str = Field("", max_length=300)                    # 學生補充想談的事
    clarity_before: int | None = Field(None, ge=1, le=5)
    session_number: int = Field(1, ge=1, le=999)
    previous_actions: list[Action] = Field(default_factory=list, max_length=30)


def kickoff_message(ctx: SessionContext) -> str:
    """The hidden first user turn that opens a session (the API needs a user turn first)."""
    lines = [f"【第 {ctx.session_number} 次會談開始】"]
    lines.append(f"學生選的議題：{'、'.join(ctx.topics) or '（沒有選）'}")
    if ctx.note:
        lines.append(f"學生補充：{ctx.note}")
    if ctx.clarity_before:
        lines.append(f"學生自評目前方向清楚度：{ctx.clarity_before}/5")
    pending = [a for a in ctx.previous_actions if a.status in ("還沒開始", "進行中")]
    if pending:
        lines.append("上次會談學生自己訂的下一步行動：")
        lines += [f"- [{a.id}] {a.text}（目前：{a.status}）" for a in pending]
        lines.append("請先溫和地關心這些行動的進度（一次問一個），聽到結果就用 update_action 記錄，再進入今天的議題。")
    else:
        lines.append("請打招呼，簡短回應學生選的議題，然後問第一個問題。")
    return "\n".join(lines)


# ---------- grades & interest tests (from photos or manual input) ----------

def suggest_strengths(grades: dict[str, float], margin: float = 5.0) -> tuple[list[str], list[str]]:
    """Suggest strong / weak subjects relative to the student's own average.

    Only a suggestion: the student confirms in the UI (a high score is not the same as liking a subject).
    """
    if len(grades) < 2:
        return [], []
    avg = mean(grades.values())
    ordered = sorted(grades.items(), key=lambda kv: -kv[1])
    strong = [s for s, v in ordered if v >= avg + margin]
    weak = [s for s, v in reversed(ordered) if v <= avg - margin]
    return strong, weak


def normalize_interest(scores: dict[str, float], scale_max: float) -> dict[str, float]:
    """Raw interest-test scores → 0–1 for the profile. Unknown codes are dropped."""
    if scale_max <= 0:
        raise ValueError("滿分必須大於 0")
    return {k: round(max(0.0, min(1.0, v / scale_max)), 2) for k, v in scores.items() if k in HOLLAND}
