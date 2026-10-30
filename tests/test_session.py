"""Offline tests for the session helpers (no API calls)."""
import pytest

from planner.session import Action, SessionContext, kickoff_message, normalize_interest, suggest_strengths
from planner.stage import available_stages, load_stage


def test_suggest_strengths_relative_to_own_average():
    strong, weak = suggest_strengths({"數學": 85, "英文": 62, "國文": 78, "物理": 80})
    # average 76.25 → strong ≥ 81.25, weak ≤ 71.25
    assert strong == ["數學"]
    assert weak == ["英文"]


def test_suggest_strengths_needs_two_subjects_and_flat_scores_give_nothing():
    assert suggest_strengths({"數學": 90}) == ([], [])
    assert suggest_strengths({"數學": 80, "英文": 81, "國文": 79}) == ([], [])


def test_normalize_interest():
    assert normalize_interest({"R": 50, "I": 120, "X": 3}, 100) == {"R": 0.5, "I": 1.0}
    with pytest.raises(ValueError):
        normalize_interest({"R": 1}, 0)


def test_kickoff_lists_only_unfinished_actions():
    ctx = SessionContext(topics=["選組、選修課怎麼選"], clarity_before=2, session_number=2, previous_actions=[
        Action(id="a1", text="查資訊營"),
        Action(id="a2", text="問學長", status="完成"),
    ])
    text = kickoff_message(ctx)
    assert "第 2 次" in text and "2/5" in text and "選組" in text
    assert "[a1] 查資訊營" in text and "a2" not in text


def test_first_session_kickoff_has_no_follow_up():
    assert "關心" not in kickoff_message(SessionContext(topics=[]))


@pytest.mark.parametrize("stage_id", list(available_stages()))
def test_every_stage_has_topics(stage_id):
    assert len(load_stage(stage_id).topics) >= 5
