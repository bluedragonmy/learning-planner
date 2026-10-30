"""The advisor agent: one student turn in, one reply out, profile updated along the way.

    python -m planner.agent "我很喜歡寫程式，但不知道要選哪一組" --stage senior_high

Claude decides which tools to call; the tools are plain code over the stage pack,
the student profile, and the planning engine.
"""
import argparse
import time
from dataclasses import dataclass, field

from anthropic import beta_tool

from planner.llm import ADVISOR_EFFORT, ADVISOR_MODEL, cost_usd, make_client
from planner.planning import gap_analysis, rank_targets
from planner.profile import HOLLAND, StudentProfile
from planner.safety import CRISIS_REPLY, is_crisis
from planner.session import ACTION_STATUSES, Action, SessionContext
from planner.stage import StagePack, load_stage
from planner.textutil import strip_emoji

MAX_STEPS = 8          # model turns per student message; bounds cost and latency

SYSTEM_PROMPT = """你是「小航」，中學生的 AI 學習規劃助理，角色參考大學的「學習規劃師」：陪學生認識自己、連結課程與未來方向。

原則：
- 你引導，學生自己做決定。不要替學生選組、選志願；提供選項、理由與下一步。
- 說話對象是中學生：口語、簡短、一次只問一個問題。不要使用表情符號（emoji）。
- 學生透露任何關於自己的資訊（興趣、擅長或較弱的科目、在意的事、目標、修過的課、年級），就用工具記到側寫，並附上學生的原話當證據。不要記錄你自己猜的、學生沒說過的事。
- 學群、科系、修課建議只能根據工具查到的資料，不可自己編。資料是 DEMO 示意資料，給建議時提醒一次即可。
- 差距分析的數字由工具計算，直接引用，不要自己算。
- 重要決定（選組、選志願、轉換跑道）一律建議學生帶著這次整理的內容，去找{referral}討論。
- 如果學生提到想傷害自己、活不下去等，停止規劃話題，關心學生並請他立刻找輔導室、家人或撥 1925 安心專線。

三種模式，依情況自己切換：
1. 探索：側寫還很空或學生不確定方向 → 問問題認識學生（喜歡做什麼、哪科有成就感、在意什麼），隨時記錄側寫；累積一些資訊後可以用 suggest_targets 提出「可以了解看看」的方向。
2. 規劃：學生有想去的{target_label} → 用 analyze_gap 做差距分析，解釋結果，提出具體下一步（修課、活動、要補的能力）。
3. 追蹤：學生回報修了什麼課、做了什麼、想法改變 → 更新側寫，再回頭檢查計畫。

這是一次「會談」：學生開始前選了議題，結束由學生自己按「結束會談」，你不用主動結束。
會談結束後學生會自己寫下一步行動，所以不要替學生訂計畫；可以提供想法讓學生參考。
如果上次會談有學生自己訂的行動，學生回報進度時用 update_action 記錄。

目前的教育階段：{stage_name}；主要決定：{decisions}。
不要在回答中描述你用了哪些工具。"""


@dataclass
class Turn:
    text: str
    profile: StudentProfile
    trace: list[str] = field(default_factory=list)
    usd: float = 0.0
    seconds: float = 0.0
    action_updates: list[dict] = field(default_factory=list)   # {id, status, note}


class Advisor:
    def __init__(self, client=None, model: str = ADVISOR_MODEL):
        self.client = client or make_client()
        self.model = model

    # ---------- tools (bound to one turn's profile and trace) ----------

    def _tools(self, pack: StagePack, profile: StudentProfile, trace: list[str],
               actions: list[Action], action_updates: list[dict]):
        @beta_tool
        def search_targets(query: str) -> str:
            """搜尋目前教育階段的升學方向資料（學群或群科）：介紹、興趣類型、重要科目、需要的能力、建議修課、未來出路。

            Args:
                query: 關鍵字，例如「程式」「醫生」「設計」「心理」；留空列出全部。
            """
            trace.append(f"search_targets({query})")
            hits = pack.search(query)
            if not hits:
                return f"沒有符合的{pack.target_label}。全部有：{'、'.join(t.name for t in pack.targets)}"
            return "\n\n".join(t.to_text() for t in hits) + f"\n\n（{pack.disclaimer}）"

        @beta_tool
        def update_interest(code: str, score: float, evidence: str) -> str:
            """更新學生某個 Holland 興趣類型的分數（0 到 1）。學生的話顯示出對某類活動的喜好或排斥時使用。
            R 實用型（動手做、機械、戶外）、I 研究型（思考、解謎、科學）、A 藝術型（創作、表達）、
            S 社會型（助人、教學、合作）、E 企業型（領導、說服、經營）、C 事務型（整理、規則、細節）。

            Args:
                code: R、I、A、S、E、C 其中一個字母。
                score: 新的估計分數，0 到 1；只有一點跡象就給 0.3–0.5，學生明確表達才給 0.7 以上。
                evidence: 學生說過的原話（直接引用）。
            """
            trace.append(f"update_interest({code}, {score})")
            return profile.set_interest(code, score, evidence)

        @beta_tool
        def record_info(field_name: str, value: str, evidence: str) -> str:
            """把學生透露的資訊記到側寫。

            Args:
                field_name: 欄位名稱：grade（年級）、strong_subjects（擅長科目）、weak_subjects（較弱科目）、
                    values（重視的價值）、goals（目標）、taken_courses（已修或正在修的課）、notes（其他觀察）。
                value: 要記錄的內容，簡短，例如「數學」「想讀資工」「高一」。
                evidence: 學生說過的原話（直接引用）。
            """
            trace.append(f"record_info({field_name}, {value})")
            return profile.add_item(field_name, value, evidence)

        @beta_tool
        def remove_info(field_name: str, value: str) -> str:
            """學生更正或改變想法時，從側寫的清單欄位移除一項。

            Args:
                field_name: 欄位名稱，例如 goals、strong_subjects。
                value: 要移除的內容，必須和側寫中的文字完全一樣。
            """
            trace.append(f"remove_info({field_name}, {value})")
            return profile.remove_item(field_name, value)

        @beta_tool
        def suggest_targets() -> str:
            """依目前側寫的興趣分數，列出興趣契合度最高的幾個方向。只用來擴展探索，不是推薦學生去讀。"""
            trace.append("suggest_targets()")
            if not profile.top_interests(min_score=0.3):
                return "側寫的興趣資訊還不夠，先多認識學生再用。"
            ranked = rank_targets(profile, pack)
            lines = [f"- {t.name}：契合度 {fit:.2f}（偏 {'、'.join(HOLLAND[h] for h in t.holland)}）" for t, fit in ranked]
            return "興趣契合度前幾名（僅供探索）：\n" + "\n".join(lines)

        @beta_tool
        def analyze_gap(target: str) -> str:
            """針對學生想去的一個方向，比對側寫做差距分析：興趣契合度、重要科目強弱、建議修課完成與否。

            Args:
                target: 方向的 id 或名稱，例如「info」「資訊學群」「設計群」。
            """
            trace.append(f"analyze_gap({target})")
            t = pack.target(target)
            if t is None:
                return f"找不到「{target}」。可用：{'、'.join(f'{x.name}({x.id})' for x in pack.targets)}"
            return gap_analysis(profile, t).to_markdown() + \
                f"\n\n（以上由程式計算，請直接引用。{pack.disclaimer}）"

        @beta_tool
        def update_action(action_id: str, status: str, note: str = "") -> str:
            """記錄學生上次自己訂的下一步行動目前的進度。學生回報做了、正在做、還沒做或不想做了時使用。

            Args:
                action_id: 行動的編號（會談開始時列出的 [編號]）。
                status: 還沒開始、進行中、完成、不做了 其中之一。
                note: 學生說的情況，簡短，例如「報名了資訊營，下個月去」。
            """
            trace.append(f"update_action({action_id}, {status})")
            if status not in ACTION_STATUSES:
                return f"錯誤：status 必須是 {'、'.join(ACTION_STATUSES)} 其中之一。"
            action = next((a for a in actions if a.id == action_id), None)
            if action is None:
                return f"找不到行動 {action_id}。有：{'、'.join(f'[{a.id}] {a.text}' for a in actions) or '無'}"
            action.status, action.note = status, note
            action_updates.append({"id": action_id, "status": status, "note": note})
            return f"已記錄：{action.text} → {status}"

        return [search_targets, update_interest, record_info, remove_info, suggest_targets, analyze_gap,
                update_action]

    # ---------- one turn ----------

    def reply(self, message: str, profile: StudentProfile, history: list[dict] | None = None,
              session: SessionContext | None = None) -> Turn:
        start = time.perf_counter()
        profile = profile.model_copy(deep=True)
        session = session.model_copy(deep=True) if session else SessionContext()
        if is_crisis(message):
            profile.notes.append("曾表達危機訊息，已轉介")
            return Turn(CRISIS_REPLY, profile, ["safety: crisis keywords → fixed referral, no LLM call"],
                        seconds=time.perf_counter() - start)

        pack = load_stage(profile.stage)
        trace: list[str] = []
        action_updates: list[dict] = []
        system = SYSTEM_PROMPT.format(referral=pack.referral, target_label=pack.target_label,
                                      stage_name=pack.name, decisions=pack.decisions)
        # profile changes every turn, so it rides on the user message, not the cached system prompt
        context = f"【目前的學生側寫】\n{profile.summary()}\n\n【學生說】\n{message}"
        messages = [m for m in (history or []) if m["role"] in ("user", "assistant") and isinstance(m["content"], str)]
        messages.append({"role": "user", "content": context})

        runner = self.client.beta.messages.tool_runner(
            model=self.model,
            max_tokens=4000,
            system=system,
            tools=self._tools(pack, profile, trace, session.previous_actions, action_updates),
            messages=messages,
            output_config={"effort": ADVISOR_EFFORT},
            # if a safety classifier declines, the API retries on a fallback model in the same call
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        final, usd = None, 0.0
        for step, msg in enumerate(runner, 1):
            usd += cost_usd(self.model, msg.usage)
            final = msg
            if step >= MAX_STEPS:
                break
        if final is not None and final.stop_reason == "refusal":
            text = "（這個問題我沒辦法回答，可以換個方式問，或找輔導室老師聊聊。）"
        else:
            text = "".join(b.text for b in final.content if b.type == "text") if final else ""
            if not text or final.stop_reason == "tool_use":
                text = text or "（我整理資料花太多步驟了，可以把問題說得具體一點嗎？）"
        return Turn(strip_emoji(text), profile, trace, usd, time.perf_counter() - start, action_updates)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("message")
    parser.add_argument("--stage", default="senior_high")
    args = parser.parse_args()

    turn = Advisor().reply(args.message, StudentProfile(stage=args.stage))
    print("工具呼叫：")
    for t in turn.trace:
        print("  ", t)
    print("\n" + turn.text)
    print("\n側寫：\n" + turn.profile.summary())
    print(f"\n({turn.seconds:.1f}s, US${turn.usd:.4f})")


if __name__ == "__main__":
    main()
