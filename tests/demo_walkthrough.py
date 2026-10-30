"""Click through the static GitHub Pages demo in Edge (no API key, no cost).

    python scripts/build_site.py
    python tests/demo_walkthrough.py https://bluedragonmy.github.io/learning-planner/ [--out DIR]
"""
import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
results: list[tuple[bool, str]] = []


def check(ok, what: str) -> None:
    results.append((bool(ok), what))
    print(("PASS " if ok else "FAIL ") + what, flush=True)


def wait_bot(page, count_before: int) -> None:
    page.wait_for_function(f"document.querySelectorAll('.msg.bot:not(#typing)').length > {count_before}", timeout=30_000)
    page.wait_for_selector("#typing", state="detached", timeout=30_000)


def run(url: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        errors, bad = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("response", lambda r: r.status >= 400 and bad.append(f"{r.status} {r.url}"))
        page.on("dialog", lambda d: d.accept())

        page.goto(url)
        page.wait_for_selector("#startBtn")
        check("預先錄製" in page.inner_text(".demo-banner"), "標示：最上方寫明是預先錄製的展示版")
        check("小羽" in page.inner_text("#view"), "首頁：說明會扮演示範學生")
        page.screenshot(path=str(out / "demo-01-lobby.png"))

        page.click("#startBtn")
        check(page.locator(".topic.on").count() == 2, "議題：已預先選好 2 個")
        page.locator(".topic").first.click()
        check(page.locator(".topic.on").count() == 2, "議題：展示版不能改")
        page.click("#next1")
        check(page.locator(".clarity-opt.on").count() == 1, "清楚度：已預先選好")
        page.click("#next2")
        page.click("[data-demo-photo=grades]")
        page.wait_for_selector("table.grades", timeout=15_000)
        check(page.locator("input[data-k=subject]").count() == 7, "成績單：顯示 AI 讀出的 7 科")
        check(page.locator(".ed-preview").is_visible(), "成績單：旁邊附原始照片可以對照")
        page.screenshot(path=str(out / "demo-02-grades.png"))
        page.click("#edOk")
        check(page.locator(".import-card.done").count() == 1, "成績單：確認後加入側寫")

        page.click("#startSession")
        wait_bot(page, 0)
        check(page.locator("#input").is_disabled(), "會談：展示版不能自由打字")
        for i in range(3):
            line = page.get_attribute("#demoSay", "data-line")
            page.click("#demoSay")
            wait_bot(page, i + 1)
            check(line in page.inner_text("#messages"), f"會談：第 {i + 1} 句送出並收到錄製的回答")
        page.screenshot(path=str(out / "demo-03-session.png"))
        check("對話到這裡結束" in page.inner_text(".composer"), "會談：句子用完後提示結束會談")
        check(page.locator("#facts .tag").count() >= 3, "會談：右側側寫有內容")

        page.click("#endBtn")
        page.wait_for_selector(".block-title", timeout=15_000)
        page.locator(".action-input").nth(0).fill("寒假參加一次設計營隊")
        page.click("#toSurvey")
        page.locator(".clarity-opt[data-name=after]").nth(3).click()
        page.locator(".scale-opt").nth(3).click()
        page.fill("#reflection", "我發現喜歡設計不代表不能升學")
        page.click("#submitSurvey")
        page.wait_for_selector("#record")
        check("進步 2" in page.inner_text("#record"), "紀錄：顯示方向清楚度進步")
        page.screenshot(path=str(out / "demo-04-record.png"))
        with page.expect_download(timeout=30_000) as dl:
            page.click("#saveImg")
        check(dl.value.suggested_filename.endswith(".png"), "紀錄：可以下載圖片")

        page.click("#backHome")
        check(page.locator("#startBtn").is_disabled(), "首頁：展示版只能體驗一次，按鈕停用並說明")
        check(not errors, f"沒有 JavaScript 錯誤 {errors[:3]}")
        check(not bad, f"沒有載入失敗的檔案 {bad[:3]}")

        phone = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        mp = phone.new_page()
        mp.goto(url)
        mp.wait_for_selector("#startBtn")
        check(not mp.evaluate("document.documentElement.scrollWidth > window.innerWidth"), "手機：沒有左右捲動")
        mp.screenshot(path=str(out / "demo-05-phone.png"))
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--out", default=str(ROOT / "eval" / "results" / f"demo-{time.strftime('%Y%m%d-%H%M')}"))
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        run(args.url, Path(args.out))
    except Exception as ex:
        import traceback
        traceback.print_exc()
        results.append((False, f"腳本中斷：{type(ex).__name__}: {str(ex)[:200]}"))
    failed = [w for ok, w in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed; screenshots in {args.out}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
