"""Student profile: the structured memory that makes the assistant personal.

Every change the AI makes must carry evidence (what the student actually said),
so the student can see why the AI thinks so and correct it.
The profile is plain JSON; the web UI keeps it in the student's browser.
"""
from pydantic import BaseModel, Field

# Holland (RIASEC) interest types
HOLLAND = {"R": "實用型", "I": "研究型", "A": "藝術型", "S": "社會型", "E": "企業型", "C": "事務型"}

LIST_FIELDS = {
    "strong_subjects": "擅長科目",
    "weak_subjects": "較弱科目",
    "values": "重視的價值",
    "goals": "目標",
    "taken_courses": "已修或正在修的課",
    "notes": "其他觀察",
}
SCALAR_FIELDS = {"grade": "年級"}


class Trait(BaseModel):
    score: float = 0.0              # 0–1, the AI's current estimate
    evidence: list[str] = Field(default_factory=list)


class StudentProfile(BaseModel):
    stage: str = "senior_high"
    grade: str = ""
    interests: dict[str, Trait] = Field(default_factory=lambda: {k: Trait() for k in HOLLAND})
    strong_subjects: list[str] = Field(default_factory=list)
    weak_subjects: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    taken_courses: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    # one line per change: "欄位：值 ← 「學生原話」"
    history: list[str] = Field(default_factory=list)

    # ---------- updates (called by the agent's tools) ----------

    def set_interest(self, code: str, score: float, evidence: str) -> str:
        code = code.strip().upper()[:1]
        if code not in HOLLAND:
            return f"錯誤：興趣類型必須是 {'/'.join(HOLLAND)} 其中之一。"
        if not evidence.strip():
            return "錯誤：必須附上學生說過的話當證據。"
        trait = self.interests[code]
        trait.score = max(0.0, min(1.0, score))
        trait.evidence.append(evidence.strip())
        self.history.append(f"興趣.{HOLLAND[code]}：{trait.score:.1f} ← 「{evidence.strip()}」")
        return f"已更新 {HOLLAND[code]} = {trait.score:.1f}"

    def add_item(self, field: str, value: str, evidence: str) -> str:
        if field in SCALAR_FIELDS:
            setattr(self, field, value.strip())
        elif field in LIST_FIELDS:
            items: list[str] = getattr(self, field)
            if value.strip() in items:
                return f"{LIST_FIELDS[field]}已經有「{value}」"
            items.append(value.strip())
        else:
            return f"錯誤：沒有欄位 {field}。可用：{', '.join([*LIST_FIELDS, *SCALAR_FIELDS])}"
        label = LIST_FIELDS.get(field) or SCALAR_FIELDS[field]
        self.history.append(f"{label}：{value.strip()} ← 「{evidence.strip()}」")
        return f"已記錄 {label}：{value.strip()}"

    def remove_item(self, field: str, value: str) -> str:
        items = getattr(self, field, None)
        if field not in LIST_FIELDS or value not in items:
            return f"{field} 裡沒有「{value}」"
        items.remove(value)
        self.history.append(f"{LIST_FIELDS[field]}：移除 {value}")
        return f"已移除 {LIST_FIELDS[field]}：{value}"

    # ---------- views ----------

    def top_interests(self, n: int = 2, min_score: float = 0.5) -> list[str]:
        ranked = sorted(self.interests.items(), key=lambda kv: -kv[1].score)
        return [k for k, t in ranked[:n] if t.score >= min_score]

    def is_empty(self) -> bool:
        return not (self.top_interests(min_score=0.01) or self.strong_subjects or self.goals or self.grade)

    def summary(self) -> str:
        """Compact text for the system prompt and the UI."""
        if self.is_empty():
            return "（側寫還是空的：剛開始認識這位學生）"
        interests = "、".join(f"{HOLLAND[k]} {self.interests[k].score:.1f}"
                             for k in HOLLAND if self.interests[k].score > 0)
        lines = [f"年級：{self.grade or '未知'}", f"興趣：{interests or '尚無'}"]
        for field, label in LIST_FIELDS.items():
            items = getattr(self, field)
            if items:
                lines.append(f"{label}：{'、'.join(items)}")
        return "\n".join(lines)
