"""DEMO web server: a JSON API plus the hand-written front end in web/.

    python -m planner.app                # http://127.0.0.1:7861
    python -m planner.app --port 8000

The student profile and sessions live in the browser (localStorage) and are sent
with every request; the server keeps nothing between requests.
Every request body is validated; errors come back as {"error": "<中文說明>"}.
"""
import argparse
from typing import Annotated, Literal

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator

from planner.agent import Advisor
from planner.extract import extract
from planner.profile import HOLLAND, StudentProfile
from planner.session import ACTION_STATUSES, SessionContext, kickoff_message, suggest_strengths
from planner.stage import ROOT, available_stages, load_stage
from planner.summary import summarize

WEB = ROOT / "web"
MAX_MESSAGE_CHARS = 500
MAX_HISTORY = 20       # messages sent back to the model; older ones live only in the profile
MAX_IMAGE_B64 = 8_000_000     # ~6 MB image; the browser shrinks photos before upload

EXAMPLES = {
    "senior_high": ["老師說要開始想選組了，可是我不知道要選什麼",
                    "我想讀心理系，還要準備什麼？",
                    "我很喜歡寫程式，資訊學群適合我嗎？"],
    "junior_high": ["我爸媽要我讀普通高中，但我比較喜歡畫畫",
                    "我不知道高職跟高中差在哪",
                    "我很喜歡動手修東西"],
}

app = FastAPI(title="AI 學習規劃助理 DEMO")
_advisor: Advisor | None = None


def advisor() -> Advisor:
    global _advisor
    if _advisor is None:
        _advisor = Advisor()
    return _advisor


# ---------- request bodies ----------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)
    hidden: bool = False


class ChatRequest(BaseModel):
    message: str = Field("", max_length=MAX_MESSAGE_CHARS)
    stage: str = "senior_high"
    profile: dict | None = None
    history: list[ChatMessage] = Field(default_factory=list, max_length=200)
    session: SessionContext | None = None
    kickoff: bool = False          # open a session: the server writes the (hidden) first user turn

    @field_validator("stage")
    @classmethod
    def known_stage(cls, v: str) -> str:
        if v not in available_stages():
            raise ValueError(f"不認得的教育階段：{v}")
        return v


class ExtractRequest(BaseModel):
    kind: Literal["grades", "interest"]
    image_b64: str = Field(min_length=100, max_length=MAX_IMAGE_B64)
    media_type: Literal["image/jpeg", "image/png", "image/webp"] = "image/jpeg"


Subject = Annotated[str, Field(min_length=1, max_length=20)]


class GradesRequest(BaseModel):
    grades: dict[Subject, Annotated[float, Field(ge=0, le=100)]] = Field(max_length=30)


class SummaryRequest(BaseModel):
    chat: list[ChatMessage] = Field(min_length=1, max_length=200)
    profile: dict | None = None
    topics: list[Annotated[str, Field(max_length=50)]] = Field(default_factory=list, max_length=12)


FIELD_NAMES = {"message": "訊息", "stage": "教育階段", "clarity_before": "方向清楚度", "note": "補充說明",
               "topics": "議題", "image_b64": "圖片", "media_type": "圖片格式", "kind": "資料類型",
               "grades": "成績", "chat": "對話", "history": "對話紀錄", "previous_actions": "上次的行動",
               "session_number": "會談次數", "profile": "側寫"}
PROBLEMS = {"string_too_long": "太長了", "string_too_short": "不能是空的", "too_long": "項目太多",
            "too_short": "不能是空的", "greater_than_equal": "超出範圍", "less_than_equal": "超出範圍",
            "greater_than": "超出範圍", "less_than": "超出範圍", "literal_error": "不是允許的選項",
            "missing": "沒有填", "int_parsing": "要是整數", "float_parsing": "要是數字", "value_error": ""}


@app.exception_handler(RequestValidationError)
def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0]
    # name the most specific field we have a Chinese name for (e.g. a row inside 成績 → 成績)
    where = next((FIELD_NAMES[p] for p in reversed(first["loc"]) if isinstance(p, str) and p in FIELD_NAMES), "輸入")
    problem = PROBLEMS.get(first["type"])
    if problem is None:
        problem = "格式不正確"
    elif not problem:   # our own validators already speak Chinese
        problem = str(first.get("ctx", {}).get("error", "格式不正確"))
    return JSONResponse({"error": f"{where}：{problem}"}, status_code=422)


def parse_profile(data: dict | None) -> StudentProfile:
    try:
        return StudentProfile.model_validate(data) if data else StudentProfile()
    except ValidationError as ex:
        raise ValueError("側寫資料格式不正確，請按「全部清除」重新開始。") from ex


# ---------- endpoints ----------

@app.get("/api/stages")
def stages() -> dict:
    out = []
    for sid in available_stages():
        pack = load_stage(sid)
        out.append({"id": pack.id, "name": pack.name, "decisions": pack.decisions,
                    "disclaimer": pack.disclaimer, "topics": pack.topics, "subjects": pack.subjects,
                    "examples": EXAMPLES.get(sid, [])})
    return {"stages": out, "holland": HOLLAND, "action_statuses": ACTION_STATUSES}


@app.get("/api/profile/new")
def new_profile(stage: str = "senior_high") -> dict:
    return StudentProfile(stage=stage if stage in available_stages() else "senior_high").model_dump()


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    # sync endpoint: FastAPI runs it in a worker thread, so one slow turn doesn't block others
    message = kickoff_message(req.session or SessionContext()) if req.kickoff else req.message.strip()
    if not message:
        return {"error": "訊息是空的"}
    try:
        profile = parse_profile(req.profile)
    except ValueError as ex:
        return {"error": str(ex)}
    profile.stage = req.stage
    history = [{"role": m.role, "content": m.content} for m in req.history][-MAX_HISTORY:]
    while history and history[0]["role"] != "user":      # the API requires a user turn first
        history.pop(0)
    try:
        turn = advisor().reply(message, profile, history, req.session)
    except Exception as ex:  # surface API/key problems in the UI instead of a silent 500
        return {"error": f"{type(ex).__name__}: {ex}"}
    return {"reply": turn.text, "profile": turn.profile.model_dump(), "trace": turn.trace,
            "usd": round(turn.usd, 4), "seconds": round(turn.seconds, 1),
            "action_updates": turn.action_updates,
            "user_message": message}   # for kickoff the client stores this as a hidden turn


@app.post("/api/extract")
def extract_photo(req: ExtractRequest) -> dict:
    try:
        data, usd = extract(advisor().client, req.kind, req.image_b64, req.media_type)
    except Exception as ex:
        return {"error": f"{type(ex).__name__}: {ex}"}
    out = {"data": data, "usd": round(usd, 4)}
    if req.kind == "grades":
        # keep only plausible rows; the student still reviews everything
        data["items"] = [i for i in data.get("items", []) if i.get("subject", "").strip() and 0 <= i.get("score", -1) <= 100]
        grades = {i["subject"]: i["score"] for i in data["items"]}
        out["strong"], out["weak"] = suggest_strengths(grades)
    return out


@app.post("/api/strengths")
def strengths(req: GradesRequest) -> dict:
    """Suggestion for typed or corrected grades (same rule as for photos)."""
    strong, weak = suggest_strengths(req.grades)
    return {"strong": strong, "weak": weak}


@app.post("/api/summary")
def session_summary(req: SummaryRequest) -> dict:
    try:
        profile = parse_profile(req.profile)
        summary, usd = summarize(advisor().client, [m.model_dump() for m in req.chat], profile, req.topics)
    except Exception as ex:
        return {"error": f"{type(ex).__name__}: {ex}" if not isinstance(ex, ValueError) else str(ex)}
    return {"summary": summary, "usd": round(usd, 4)}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


app.mount("/static", StaticFiles(directory=WEB), name="static")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7861)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
