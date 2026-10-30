"""API input validation: every bad request must be rejected before any Claude call."""
import pytest
from fastapi.testclient import TestClient

import planner.app as app_module
from planner.textutil import strip_emoji


class NoCallAdvisor:
    """Fails the test if a request ever reaches the model."""
    @property
    def client(self):
        raise AssertionError("should have been rejected before calling Claude")

    def reply(self, *a, **k):
        raise AssertionError("should have been rejected before calling Claude")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module, "_advisor", NoCallAdvisor())
    return TestClient(app_module.app)


def error_of(resp):
    body = resp.json()
    assert "error" in body, body
    return body["error"]


@pytest.mark.parametrize("payload, expect", [
    ({"message": ""}, "訊息是空的"),
    ({"message": "   "}, "訊息是空的"),
    ({"message": "x" * 501}, "訊息"),
    ({"message": "hi", "stage": "college"}, "教育階段"),
    ({"message": "hi", "session": {"clarity_before": 9}}, "方向清楚度"),
    ({"message": "hi", "session": {"clarity_before": 0}}, "方向清楚度"),
    ({"message": "hi", "session": {"note": "x" * 301}}, "補充說明"),
    ({"message": "hi", "session": {"topics": [""]}}, "議題"),
    ({"message": "hi", "session": {"previous_actions": [{"id": "a", "text": "x", "status": "亂寫"}]}}, "上次的行動：不是允許的選項"),
    ({"message": "hi", "history": [{"role": "system", "content": "x"}]}, "對話紀錄"),
    ({"message": "hi", "profile": {"interests": "not a dict"}}, "側寫"),
])
def test_chat_rejects_bad_input(client, payload, expect):
    assert expect in error_of(client.post("/api/chat", json=payload))


@pytest.mark.parametrize("payload, expect", [
    ({"kind": "diploma", "image_b64": "A" * 200}, "資料類型"),
    ({"kind": "grades", "image_b64": "short"}, "圖片"),
    ({"kind": "grades", "image_b64": "A" * 200, "media_type": "application/pdf"}, "圖片格式"),
])
def test_extract_rejects_bad_input(client, payload, expect):
    assert expect in error_of(client.post("/api/extract", json=payload))


@pytest.mark.parametrize("grades", [{"數學": 101}, {"數學": -1}, {"": 80}, {"x" * 21: 80}])
def test_strengths_rejects_bad_grades(client, grades):
    assert "成績" in error_of(client.post("/api/strengths", json={"grades": grades}))


def test_strengths_ok(client):
    assert client.post("/api/strengths", json={"grades": {"數學": 90, "英文": 60, "國文": 75}}).json() == \
        {"strong": ["數學"], "weak": ["英文"]}


def test_summary_needs_a_chat(client):
    assert "對話" in error_of(client.post("/api/summary", json={"chat": []}))


def test_unknown_stage_profile_falls_back(client):
    assert client.get("/api/profile/new?stage=nope").json()["stage"] == "senior_high"


def test_strip_emoji_keeps_chinese_and_punctuation():
    assert strip_emoji("嗨！高一就在想選組，很棒 👍 我記下來了 👋") == "嗨！高一就在想選組，很棒 我記下來了"
    assert strip_emoji("**寫程式**：數學甲、物理（加深加廣）") == "**寫程式**：數學甲、物理（加深加廣）"
