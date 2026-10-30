"""Offline tests: stage packs, profile updates, planning engine, safety. No API calls."""
import pytest

from planner.planning import gap_analysis, interest_fit, rank_targets
from planner.profile import StudentProfile
from planner.safety import is_crisis
from planner.stage import available_stages, load_stage


@pytest.mark.parametrize("stage_id", list(available_stages()))
def test_stage_packs_are_complete(stage_id):
    pack = load_stage(stage_id)
    assert pack.targets and pack.disclaimer and pack.referral
    for t in pack.targets:
        assert t.holland and all(h in "RIASEC" for h in t.holland)
        assert set(t.key_subjects) <= set(pack.subjects), f"{t.name} 的重要科目不在科目表"


def test_stage_lookup_and_search():
    pack = load_stage("senior_high")
    assert pack.target("info").name == "資訊學群"
    assert pack.target("資訊學群").id == "info"
    assert pack.target("資訊").id == "info"
    assert pack.search("軟體工程師")[0].id == "info"


def test_profile_requires_evidence_and_valid_fields():
    p = StudentProfile()
    assert "錯誤" in p.set_interest("I", 0.8, "")
    assert "錯誤" in p.set_interest("X", 0.8, "我喜歡")
    assert "錯誤" in p.add_item("favorite_food", "拉麵", "我愛拉麵")
    p.set_interest("i", 1.7, "我很喜歡解數學難題")
    assert p.interests["I"].score == 1.0
    assert p.history and "解數學難題" in p.history[-1]


def test_profile_list_fields_dedupe_and_remove():
    p = StudentProfile()
    p.add_item("goals", "資訊學群", "我想讀資工")
    assert "已經有" in p.add_item("goals", "資訊學群", "還是資工")
    p.remove_item("goals", "資訊學群")
    assert p.goals == []
    assert p.is_empty()


def make_coder() -> StudentProfile:
    p = StudentProfile(strong_subjects=["數學"], weak_subjects=["物理"], taken_courses=["數學甲"])
    p.set_interest("I", 0.8, "我喜歡想清楚原理")
    p.set_interest("R", 0.5, "我喜歡組電腦")
    return p


def test_interest_fit_weights_first_type_more():
    p, pack = make_coder(), load_stage("senior_high")
    # info = I(1.0)*0.8 + R(0.6)*0.5 over 1.6
    assert interest_fit(p, pack.target("info")) == round((0.8 + 0.3) / 1.6, 2)
    assert interest_fit(p, pack.target("management")) == 0.0


def test_gap_analysis():
    report = gap_analysis(make_coder(), load_stage("senior_high").target("info"))
    assert report.matching_strengths == ["數學"]
    assert report.weak_key_subjects == ["物理"]
    assert report.unknown_key_subjects == ["資訊科技"]
    assert report.courses_done == ["數學甲"]
    assert "數學甲" not in report.courses_todo
    assert "資訊學群" in report.to_markdown()


def test_rank_targets_puts_best_fit_first():
    ranked = rank_targets(make_coder(), load_stage("senior_high"))
    assert ranked[0][0].id == "info"


@pytest.mark.parametrize("text, expected", [
    ("我最近壓力好大，有點不想活了", True),
    ("有時候覺得 活不下去", True),
    ("數學好難，考試考到想死", True),      # false positive is acceptable: referral is cheap
    ("我想讀醫學系救人", False),
    ("物理實驗要測自由落體", False),
])
def test_crisis_detection(text, expected):
    assert is_crisis(text) is expected
