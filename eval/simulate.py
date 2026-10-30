"""Simulated students: an LLM role-plays each persona and talks to the advisor.

    python -m eval.simulate                 # all personas, 5 turns each
    python -m eval.simulate --persona ming --turns 3

Writes one Markdown transcript per persona to eval/results/ and prints simple
automatic checks against each persona's `expect` (did the profile end up where
a human advisor would put it?). Costs real money: roughly US$0.05–0.2 per persona.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from planner.agent import Advisor
from planner.llm import STUDENT_MODEL, cost_usd, make_client
from planner.profile import StudentProfile
from planner.stage import load_stage

HERE = Path(__file__).resolve().parent

STUDENT_SYSTEM = """你在扮演一位台灣的中學生，正在和學校的 AI 學習規劃助理聊天。
你的設定：{persona}
規則：只用這個學生的口吻回答，簡短（一到三句），不要一次把設定全部講完，被問到才說。
不要扮演助理，不要加旁白。"""


def student_reply(client, persona: dict, transcript: list[dict]) -> tuple[str, float]:
    # roles are flipped: from the student's point of view the advisor is the "user"
    flipped = [{"role": "user", "content": "（你打開了學習規劃助理的聊天視窗）"}]
    flipped += [{"role": "assistant" if m["role"] == "user" else "user", "content": m["content"]}
                for m in transcript]
    resp = client.messages.create(
        model=STUDENT_MODEL,
        max_tokens=300,
        system=STUDENT_SYSTEM.format(persona=persona["persona"]),
        messages=flipped,
        output_config={"effort": "low"},
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text, cost_usd(STUDENT_MODEL, resp.usage)


def check(persona: dict, profile: StudentProfile, all_tool_calls: list[str]) -> list[str]:
    expect, out = persona.get("expect", {}), []
    if "interests_top" in expect:
        top = profile.top_interests(n=2, min_score=0.3)
        ok = any(h in top for h in expect["interests_top"])
        out.append(f"{'✅' if ok else '❌'} 興趣前兩名 {top}，預期包含 {expect['interests_top']} 之一")
    if "gap_target" in expect:
        target = load_stage(persona["stage"]).target(expect["gap_target"])
        ok = any(c.startswith("analyze_gap(") and (target.id in c or target.name in c) for c in all_tool_calls)
        out.append(f"{'✅' if ok else '❌'} 有對 {expect['gap_target']} 做差距分析")
    if "suggested_targets" in expect:
        ok = any(c.startswith(("suggest_targets", "analyze_gap", "search_targets")) for c in all_tool_calls)
        out.append(f"{'✅' if ok else '❌'} 有查詢或建議方向")
    return out


def run(persona: dict, turns: int, advisor: Advisor, client) -> tuple[str, float]:
    profile = StudentProfile(stage=persona["stage"])
    transcript: list[dict] = []
    calls: list[str] = []
    usd = 0.0
    message = persona["opening"]
    lines = [f"# 模擬學生：{persona['name']}（{persona['stage']}）", "", f"> 設定：{persona['persona']}", ""]
    for i in range(turns):
        turn = advisor.reply(message, profile, transcript)
        profile, usd = turn.profile, usd + turn.usd
        calls += turn.trace
        transcript += [{"role": "user", "content": message}, {"role": "assistant", "content": turn.text}]
        lines += [f"**學生**：{message}", "", f"**助理**：{turn.text}", "",
                  f"<sub>工具：{'; '.join(turn.trace) or '無'}</sub>", ""]
        if i < turns - 1:
            message, c = student_reply(client, persona, transcript)
            usd += c
    results = check(persona, profile, calls)
    lines += ["## 最終側寫", "```", profile.summary(), "```", "", "## 側寫變更紀錄",
              *[f"- {h}" for h in profile.history], "", "## 自動檢查", *[f"- {r}" for r in results],
              "", f"費用：US${usd:.4f}"]
    return "\n".join(lines), usd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona", help="只跑某一位（id）")
    parser.add_argument("--turns", type=int, default=5)
    args = parser.parse_args()

    personas = json.loads((HERE / "personas.json").read_text(encoding="utf-8"))
    if args.persona:
        personas = [p for p in personas if p["id"] == args.persona]
    client = make_client()
    advisor = Advisor(client)
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    total = 0.0
    for p in personas:
        md, usd = run(p, args.turns, advisor, client)
        total += usd
        path = out_dir / f"{stamp}-{p['id']}.md"
        path.write_text(md, encoding="utf-8")
        print(f"{p['name']}: {path.name}  US${usd:.4f}")
        print("\n".join("   " + line for line in md.split("## 自動檢查")[1].strip().splitlines()[:-1]))
    print(f"總費用 US${total:.4f}")


if __name__ == "__main__":
    main()
