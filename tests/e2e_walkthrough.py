"""Click through the whole session flow in a real browser (Edge), like a student would,
including deliberately wrong inputs. Uses the real Claude API (about US$0.3 per run).

    python -m planner.app                       # in another terminal
    python tests/e2e_walkthrough.py [--headed] [--out DIR]

Prints PASS/FAIL per check and saves screenshots. Not collected by pytest on purpose (it costs money).
"""
import argparse
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:7861"
FAKE_REPORT = ROOT / "data" / "demo" / "假成績單.png"
AI_TIMEOUT = 120_000
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")

results: list[tuple[bool, str]] = []


def check(ok: bool, what: str) -> None:
    results.append((bool(ok), what))
    print(("PASS " if ok else "FAIL ") + what, flush=True)


def visible_text(page: Page, sel: str) -> str:
    loc = page.locator(sel)
    return loc.inner_text() if loc.count() and loc.first.is_visible() else ""


def shot(page: Page, out: Path, name: str) -> None:
    page.screenshot(path=str(out / f"{name}.png"), full_page=False)


def wait_bot_reply(page: Page, count_before: int) -> str:
    page.wait_for_function(f"document.querySelectorAll('.msg.bot:not(#typing)').length > {count_before}",
                           timeout=AI_TIMEOUT)
    page.wait_for_selector("#typing", state="detached", timeout=AI_TIMEOUT)
    return page.locator(".msg.bot:not(#typing) .bubble").last.inner_text()


def intake(page: Page, topic_index: int = 0, clarity: int = 2) -> None:
    page.click("#startBtn")
    page.locator(".topic").nth(topic_index).click()
    page.click("#next1")
    page.locator(".clarity-opt").nth(clarity - 1).click()
    page.click("#next2")


def run(out: Path, headed: bool) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=not headed)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True, locale="zh-TW")
        page = ctx.new_page()
        console_errors: list[str] = []
        page.on("pageerror", lambda e: console_errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and console_errors.append(m.text))
        page.on("dialog", lambda d: d.accept())      # confirm() dialogs: always answer yes

        page.goto(BASE)
        page.wait_for_selector("#startBtn")
        check("嗨，我是小航" in page.inner_text("#view"), "首頁：第一次使用顯示歡迎")
        shot(page, out, "01-lobby")

        # ---------- 會談前 step 1 ----------
        page.click("#startBtn")
        page.click("#next1")
        check("至少選一個議題" in visible_text(page, "#err1"), "議題：什麼都沒選 → 擋下並顯示錯誤")
        page.fill("#noteInput", "   ")
        page.click("#next1")
        check("至少選一個議題" in visible_text(page, "#err1"), "議題：只填空白 → 擋下")
        page.fill("#noteInput", "a")
        page.click("#next1")
        check("至少選一個議題" in visible_text(page, "#err1"), "議題：只填 1 個字 → 擋下")
        page.fill("#noteInput", "")
        page.locator(".topic").nth(1).click()
        check(not visible_text(page, "#err1"), "議題：選了之後錯誤訊息消失")
        shot(page, out, "02-intake-topics")
        page.click("#next1")

        # ---------- step 2 ----------
        page.click("#next2")
        check("請選一個" in visible_text(page, "#err2"), "清楚度：沒選 → 擋下")
        check(page.locator(".clarity-opt svg").count() == 5, "清楚度：5 個選項都是畫的臉（不是 emoji）")
        page.locator(".clarity-opt").nth(1).click()
        check(not visible_text(page, "#err2"), "清楚度：選了之後錯誤消失")
        shot(page, out, "03-intake-clarity")
        page.click("#next2")

        # ---------- step 3: manual grades with bad values ----------
        page.click("[data-import=grades][data-mode=manual]")
        rows = page.locator("table.grades tbody tr:not(.row-err)")
        page.click("#edOk")
        check("至少要填一個科目" in visible_text(page, "#edErr"), "成績：全空 → 擋下")

        rows.nth(2).locator("input[data-k=score]").fill("105")      # 數學
        page.click("#edOk")
        check("0 到 100" in page.inner_text("#editor"), "成績：105 分 → 擋下並標出該列")
        rows.nth(2).locator("input[data-k=score]").fill("abc")
        page.click("#edOk")
        check("要是數字" in page.inner_text("#editor"), "成績：輸入文字 → 擋下")
        rows.nth(2).locator("input[data-k=score]").fill("-3")
        page.click("#edOk")
        check("0 到 100" in page.inner_text("#editor"), "成績：負數 → 擋下")
        rows.nth(2).locator("input[data-k=score]").fill("91")
        rows.nth(1).locator("input[data-k=score]").fill("62")       # 英文
        rows.nth(0).locator("input[data-k=score]").fill("78")       # 國文
        page.click("#addRow")
        rows.last.locator("input[data-k=score]").fill("88")
        page.click("#edOk")
        check("請填科目名稱" in page.inner_text("#editor"), "成績：有分數沒科目 → 擋下")
        rows.last.locator("input[data-k=subject]").fill("數學")
        page.click("#edOk")
        check("重複" in page.inner_text("#editor"), "成績：科目重複 → 擋下")
        rows.last.locator("input[data-k=subject]").fill("資訊科技")
        rows.nth(3).locator("button[data-tag=strong]").click()     # 物理: tagged but no score
        page.click("#edOk")
        check("要填分數才能標" in page.inner_text("#editor"), "成績：沒分數卻標擅長 → 擋下")
        rows.nth(3).locator("button[data-tag='']").click()
        shot(page, out, "04-grades-errors-fixed")
        page.click("#suggest")
        page.wait_for_timeout(800)
        check(rows.nth(2).locator("button.on").inner_text() == "擅長", "成績：小航建議數學為擅長")
        check(rows.nth(1).locator("button.on").inner_text() == "吃力", "成績：小航建議英文為吃力")
        blank_it = rows.nth(10)                                     # the pre-filled, score-less 資訊科技 row
        check(blank_it.locator("button.on").inner_text() == "普通", "成績：沒分數的同名科目不會被建議標記")
        page.click("#edOk")
        check(page.locator(".import-card.done").count() == 1, "成績：確認後卡片變成已加入")
        check("數學" in page.inner_text("#facts"), "成績：側寫的擅長出現數學")

        # ---------- interest test with bad values ----------
        page.click("[data-import=interest][data-mode=manual]")
        page.fill("input[data-h=I]", "120")
        page.click("#edOk")
        check("不能超過滿分" in visible_text(page, "#edErr"), "興趣：超過滿分 → 擋下")
        page.fill("#hMax", "0")
        page.click("#edOk")
        check("滿分要是" in visible_text(page, "#edErr"), "興趣：滿分 0 → 擋下")
        page.fill("#hMax", "100")
        page.fill("input[data-h=I]", "80")
        page.fill("input[data-h=R]", "-5")
        page.click("#edOk")
        check("0 以上" in visible_text(page, "#edErr"), "興趣：負數 → 擋下")
        page.fill("input[data-h=R]", "55")
        page.click("#edOk")
        check(page.locator(".import-card.done").count() == 2, "興趣：確認後兩張卡都已加入")
        check("0.8" in (page.locator("#radar").text_content() or ""), "興趣：雷達圖出現研究 0.8")

        # ---------- photo upload ----------
        txt = out / "not-an-image.txt"
        txt.write_text("hello", encoding="utf-8")
        page.set_input_files("input[data-file=grades]", str(txt))
        check("請選擇圖片檔" in page.inner_text("#editor"), "上傳：選到文字檔 → 擋下")
        page.click("#edClose")
        page.set_input_files("input[data-file=grades]", str(FAKE_REPORT))
        page.wait_for_selector("table.grades", timeout=AI_TIMEOUT)
        subjects = [i.input_value() for i in page.locator("input[data-k=subject]").all()]
        scores = [i.input_value() for i in page.locator("input[data-k=score]").all()]
        check(subjects[:3] == ["國文", "英文", "數學"] and scores[:3] == ["78", "62", "91"],
              f"上傳：AI 讀出假成績單 {list(zip(subjects, scores))}")
        shot(page, out, "05-photo-read")
        page.click("#edOk")
        shot(page, out, "06-intake-ready")

        # ---------- session ----------
        page.click("#startSession")
        first = wait_bot_reply(page, 0)
        check(len(first) > 10, "會談：小航開場")
        check(not EMOJI.search(first), "會談：開場沒有 emoji")
        n_before = page.locator(".msg").count()
        page.fill("#input", "    ")
        page.press("#input", "Enter")
        page.wait_for_timeout(500)
        check(page.locator(".msg").count() == n_before, "會談：只輸入空白 → 不送出")
        check(page.locator("#input").get_attribute("maxlength") == "500", "會談：訊息上限 500 字")
        page.fill("#input", "我高一，最喜歡寫程式，看到程式跑出正確結果很有成就感")
        page.press("#input", "Enter")
        reply = wait_bot_reply(page, 1)
        check(not EMOJI.search(reply), "會談：回覆沒有 emoji")
        check(page.locator("#facts .tag").count() >= 2, "會談：側寫有更新")
        check(page.locator(".msg.new").count() == 1 and page.locator(".msg.bot").first.get_attribute("class").find("new") < 0,
              "會談：只有最新的訊息有進場動畫（舊訊息不會一直閃）")
        shot(page, out, "07-session")

        # ---------- end → wrap-up ----------
        page.click("#endBtn")
        page.wait_for_selector(".panel h3.block-title", timeout=AI_TIMEOUT)
        summary = page.inner_text("#view")
        check("今天聊了" in summary and not EMOJI.search(summary), "整理：出現會談整理，沒有 emoji")
        acts = page.locator(".action-input")
        acts.nth(0).fill("a")
        page.click("#toSurvey")
        check("太短" in visible_text(page, "#actErr"), "下一步：只寫 1 個字 → 擋下")
        acts.nth(0).fill("寒假前查好兩個資訊營")
        acts.nth(1).fill("寒假前查好兩個資訊營")
        page.click("#toSurvey")
        check("重複" in visible_text(page, "#actErr"), "下一步：重複 → 擋下")
        acts.nth(1).fill("問表哥資工系在學什麼")
        shot(page, out, "08-wrapup")
        page.click("#toSurvey")

        # ---------- survey ----------
        page.wait_for_selector("#submitSurvey")
        page.click("#submitSurvey")
        check(visible_text(page, "#q1Err") and visible_text(page, "#q3Err") and visible_text(page, "#q5Err"),
              "自評表：全空 → 三題都顯示錯誤")
        page.locator(".clarity-opt[data-name=after]").nth(3).click()
        page.locator(".scale-opt").nth(3).click()
        page.fill("#reflection", "嗯")
        page.click("#submitSurvey")
        check("至少 4 個字" in visible_text(page, "#q5Err"), "自評表：反思太短 → 擋下")
        page.fill("#reflection", "我發現我喜歡的是解決問題")
        shot(page, out, "09-survey")
        page.click("#submitSurvey")

        # ---------- record ----------
        page.wait_for_selector("#record")
        rec = page.inner_text("#record")
        check("進步 2" in rec and "寒假前查好兩個資訊營" in rec, "紀錄：方向清楚度 2→4、下一步都在")
        shot(page, out, "10-record")
        with page.expect_download(timeout=30_000) as dl:
            page.click("#saveImg")
        img_path = out / dl.value.suggested_filename
        dl.value.save_as(img_path)
        check(img_path.stat().st_size > 20_000, f"紀錄：下載圖片成功（{img_path.name}）")
        page.emulate_media(media="print")
        page.pdf(path=str(out / "record.pdf"))
        check(not page.locator(".topbar").is_visible() and not page.locator("#profile").is_visible(),
              "紀錄：列印／PDF 時只印紀錄本身")
        page.screenshot(path=str(out / "11-print-view.png"), full_page=True)
        page.emulate_media(media="screen")

        # ---------- second session: follow-up and the survey gate ----------
        page.reload()
        page.wait_for_selector("#startBtn")
        check("寒假前查好兩個資訊營" in page.inner_text("#view"), "第二次：首頁提到上次的下一步")
        intake(page, topic_index=7, clarity=3)
        page.click("#startSession")
        opening = wait_bot_reply(page, 0)
        check("資訊營" in opening, "第二次：小航開場先關心上次的行動")
        page.fill("#input", "資訊營我已經報名了一個，表哥那邊還沒問")
        page.press("#input", "Enter")
        wait_bot_reply(page, 1)
        acts_panel = page.inner_text("#actionsPanel")
        check("完成" in acts_panel or "進行中" in acts_panel, f"第二次：行動狀態被更新（{acts_panel!r}）")
        shot(page, out, "12-followup")
        page.click("#endBtn")
        page.wait_for_selector("#toSurvey:not([disabled])", timeout=AI_TIMEOUT)
        page.click("#toSurvey")            # no actions this time → confirm() → accepted
        page.wait_for_selector("#submitSurvey")
        page.reload()
        page.wait_for_selector("#submitSurvey")
        check(page.locator("#startBtn").count() == 0, "門檻：自評表沒填，重新整理後還是停在自評表")
        page.click("#brandHome" if page.locator("#brandHome").count() else "#homeBtn")
        check(page.locator("#submitSurvey").count() == 1, "門檻：按首頁也離不開自評表")

        check(not console_errors, f"瀏覽器沒有 JavaScript 錯誤 {console_errors[:3]}")

        # ---------- phone ----------
        phone = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        mp = phone.new_page()
        mp.goto(BASE)
        mp.wait_for_selector("#startBtn")
        overflow = mp.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        check(not overflow, "手機：沒有左右捲動")
        mp.click("#startBtn")
        mp.locator(".topic").first.click()
        mp.click("#next1")
        mp.screenshot(path=str(out / "13-phone-clarity.png"))
        overflow = mp.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        check(not overflow, "手機：清楚度頁沒有左右捲動")
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--out", default=str(ROOT / "eval" / "results" / f"walkthrough-{time.strftime('%Y%m%d-%H%M')}"))
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        run(Path(args.out), args.headed)
    except Exception as ex:          # a crash is a failure too; show where it happened
        import traceback
        traceback.print_exc()
        results.append((False, f"腳本中斷：{type(ex).__name__}: {str(ex)[:200]}"))
    finally:
        failed = [w for ok, w in results if not ok]
        print(f"\n{len(results) - len(failed)}/{len(results)} passed; screenshots in {args.out}")
        sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
