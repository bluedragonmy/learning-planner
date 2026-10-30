"""Build the static GitHub Pages demo into site/ (standard library only; runs in CI).

    python scripts/build_site.py

The demo is the normal front end plus web/demo.js, which answers the app's API calls
from demo/recording.json (made by scripts/record_demo.py).
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB, DEMO, OUT = ROOT / "web", ROOT / "demo", ROOT / "site"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "demo").mkdir(parents=True)
    for name in ("style.css", "app.js", "demo.js"):
        shutil.copy(WEB / name, OUT / name)

    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert '<script src="/static/app.js"></script>' in html, "index.html changed: update build_site.py"
    html = html.replace("/static/", "")   # Pages serves the site under /learning-planner/, so paths must be relative
    html = html.replace('<script src="app.js"></script>',
                        '<script src="demo/recording.js"></script>\n  <script src="demo.js"></script>\n'
                        '  <script src="app.js"></script>')
    html = html.replace("<title>小航 學習規劃</title>", "<title>小航 學習規劃｜展示版</title>")
    (OUT / "index.html").write_text(html, encoding="utf-8")

    recording = json.loads((DEMO / "recording.json").read_text(encoding="utf-8"))
    (OUT / "demo" / "recording.js").write_text(
        "window.DEMO_RECORDING = " + json.dumps(recording, ensure_ascii=False) + ";\n", encoding="utf-8")
    shutil.copy(DEMO / "sample-report.png", OUT / "demo" / "sample-report.png")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"built {OUT} ({sum(1 for _ in OUT.rglob('*') if _.is_file())} files)")


if __name__ == "__main__":
    main()
