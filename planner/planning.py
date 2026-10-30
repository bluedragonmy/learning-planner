"""Planning engine: plain code, no LLM.

The numbers here must be reproducible and testable, so the LLM only explains them.
"""
from dataclasses import dataclass, field

from planner.profile import HOLLAND, StudentProfile
from planner.stage import StagePack, Target

# first listed Holland type of a target counts more than the second
HOLLAND_WEIGHTS = (1.0, 0.6)


@dataclass
class GapReport:
    target: Target
    interest_fit: float                        # 0–1
    matching_strengths: list[str] = field(default_factory=list)
    weak_key_subjects: list[str] = field(default_factory=list)
    unknown_key_subjects: list[str] = field(default_factory=list)
    courses_done: list[str] = field(default_factory=list)
    courses_todo: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        t = self.target
        fit_word = "高" if self.interest_fit >= 0.6 else "中" if self.interest_fit >= 0.3 else "低／資料不足"
        lines = [
            f"### {t.name}",
            f"- 興趣契合度：{self.interest_fit:.2f}（{fit_word}；{t.name}偏 {'、'.join(HOLLAND[h] for h in t.holland)}）",
            f"- 重要科目中你擅長的：{'、'.join(self.matching_strengths) or '無'}",
            f"- 重要科目中你較弱的：{'、'.join(self.weak_key_subjects) or '無'}",
            f"- 還不知道你表現如何的重要科目：{'、'.join(self.unknown_key_subjects) or '無'}",
            f"- 建議修課／活動，已完成：{'、'.join(self.courses_done) or '無'}",
            f"- 建議修課／活動，還沒做：{'、'.join(self.courses_todo) or '無'}",
            f"- 需要的能力：{'、'.join(t.abilities)}",
        ]
        return "\n".join(lines)


def interest_fit(profile: StudentProfile, target: Target) -> float:
    pairs = list(zip(target.holland, HOLLAND_WEIGHTS))
    total = sum(w for _, w in pairs)
    return round(sum(profile.interests[h].score * w for h, w in pairs) / total, 2)


def _taken(course: str, taken: list[str]) -> bool:
    # "數學甲" matches "數學甲"; "物理（加深加廣）" matches "物理"
    base = course.split("（")[0]
    return any(base in t or t in course for t in taken)


def gap_analysis(profile: StudentProfile, target: Target) -> GapReport:
    strong, weak = set(profile.strong_subjects), set(profile.weak_subjects)
    done = [c for c in target.recommended_courses if _taken(c, profile.taken_courses)]
    return GapReport(
        target=target,
        interest_fit=interest_fit(profile, target),
        matching_strengths=[s for s in target.key_subjects if s in strong],
        weak_key_subjects=[s for s in target.key_subjects if s in weak],
        unknown_key_subjects=[s for s in target.key_subjects if s not in strong | weak],
        courses_done=done,
        courses_todo=[c for c in target.recommended_courses if c not in done],
    )


def rank_targets(profile: StudentProfile, pack: StagePack, n: int = 3) -> list[tuple[Target, float]]:
    """Targets ordered by interest fit; used in exploration mode to widen, not decide."""
    ranked = sorted(((t, interest_fit(profile, t)) for t in pack.targets), key=lambda x: -x[1])
    return ranked[:n]
