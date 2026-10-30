"""Stage packs: everything that differs between 國中 and 高中 lives in data/stages/*.json.

The rest of the code only talks to StagePack, so switching level = switching file.
"""
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE_DIR = ROOT / "data" / "stages"


@dataclass(frozen=True)
class Target:
    """A destination the student can aim for: 學群 (高中) or 群科 (國中)."""
    id: str
    name: str
    holland: list[str]
    description: str
    key_subjects: list[str]
    abilities: list[str]
    recommended_courses: list[str]
    example_majors: list[str]
    careers: list[str]

    def to_text(self) -> str:
        return (f"{self.name}（id={self.id}，興趣類型 {'/'.join(self.holland)}）：{self.description}\n"
                f"  重要科目：{'、'.join(self.key_subjects)}\n"
                f"  需要的能力：{'、'.join(self.abilities)}\n"
                f"  建議修課／活動：{'、'.join(self.recommended_courses)}\n"
                f"  例如：{'、'.join(self.example_majors)}；未來可能：{'、'.join(self.careers)}")


@dataclass(frozen=True)
class StagePack:
    id: str
    name: str
    target_label: str
    decisions: str
    referral: str
    disclaimer: str
    topics: list[str]          # 會談前可以選的議題
    subjects: list[str]
    targets: list[Target]

    def target(self, target_id_or_name: str) -> Target | None:
        key = target_id_or_name.strip()
        return next((t for t in self.targets if key in (t.id, t.name)), None) \
            or next((t for t in self.targets if key and key in t.name), None)

    def search(self, query: str) -> list[Target]:
        """Keyword search; the demo pack is small enough that this beats a vector index."""
        terms = [q for q in query.replace("，", " ").replace("、", " ").split() if q]
        if not terms:
            return list(self.targets)

        def hits(t: Target) -> int:
            text = t.to_text()
            return sum(text.count(term) for term in terms)

        scored = sorted(((hits(t), t) for t in self.targets), key=lambda x: -x[0])
        return [t for score, t in scored if score > 0]


def available_stages() -> dict[str, str]:
    """{stage id: display name} for every pack in data/stages."""
    out = {}
    for path in sorted(STAGE_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out[data["id"]] = data["name"]
    return out


def load_stage(stage_id: str) -> StagePack:
    data = json.loads((STAGE_DIR / f"{stage_id}.json").read_text(encoding="utf-8"))
    data["targets"] = [Target(**t) for t in data["targets"]]
    return StagePack(**data)
