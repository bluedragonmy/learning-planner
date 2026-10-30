# 小航：AI 學習規劃助理（DEMO）

給中學生用的 AI 學習規劃助理，從課業出發，向未來接軌。

流程參考[臺大學習規劃辦公室](https://aaoffice.ntu.edu.tw/Service)的「會談 → 學生自己決定下一步 → 自評 → 追蹤」：
AI「小航」透過對話認識學生、建立**個人側寫**，再依側寫做**差距分析**；重要決定仍交給學生與課諮師、輔導老師。

> **DEMO 專案**：學群、群科資料是手寫的示意資料，尚未對照 ColleGo! 或教育部資料查證，請勿當作正式升學建議。

## 功能

| 流程 | 內容 |
|---|---|
| 會談前 | 選想談的議題（國中、高中各 9 項）→ 方向清楚度 1–5 → 成績單、興趣測驗可**拍照讓 AI 讀取**或手動輸入，學生確認後才寫入側寫 |
| 會談 | 與小航對話：自動記錄側寫、查學群資料、做差距分析；若上次有訂下一步，會先關心進度 |
| 會談後 | AI 整理重點 → 學生**自己**寫下一步 → 自評表（填完才能開下一次）→ 會談紀錄可匯出 PDF、圖片給老師 |
| 個人化 | 側寫包含 Holland 興趣雷達圖、強弱科、目標；**每一筆都附學生原話**，學生看得到、可以更正 |
| 安全 | 危機字詞由程式在呼叫 AI 前攔截，直接轉介 1925 安心專線與輔導室 |
| 隱私 | 側寫與會談紀錄只存在學生的瀏覽器（localStorage），伺服器不保存 |

會談前後各問一次「方向清楚度」，差值就是這次會談的效果，可以拿來評估系統。

## 架構

- **後端**：Python + FastAPI（`planner/`）
  - Claude Opus 5.5 負責對話（Agent，7 個工具）、讀取照片（結構化輸出）、整理會談紀錄
  - 興趣契合度、差距分析、強弱科建議由**純程式**計算，AI 只負責解釋
- **前端**：純 HTML/CSS/JS（`web/`），溫暖療癒風
- **教育階段包**：國中、高中的差異都放在 `data/stages/*.json`，核心程式不用改

詳細的設計決定，以及和臺大做法的對照，請見 [docs/architecture.md](docs/architecture.md)。

## 安裝與執行

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

在專案根目錄建立 `.env`（已列在 .gitignore）：

```
ANTHROPIC_API_KEY=sk-ant-...
```

```powershell
.venv\Scripts\python.exe -m planner.app                       # 網頁：http://127.0.0.1:7861
.venv\Scripts\python.exe -m planner.agent "我很喜歡寫程式"      # 命令列單輪測試
```

可以拿 `data/demo/假成績單.png` 測試拍照上傳。每輪對話大約花 US$0.03–0.05 的 API 費用。

## 測試

```powershell
.venv\Scripts\python.exe -m pytest -q                 # 42 個離線測試（不呼叫 API），含所有輸入驗證
.venv\Scripts\python.exe tests\e2e_walkthrough.py     # 用 Edge 自動操作完整流程、故意輸入錯誤值，約 US$0.3
.venv\Scripts\python.exe -m eval.simulate             # 讓 AI 扮演 3 位虛構學生跑完整對話
```

`e2e_walkthrough.py` 需要 `pip install playwright`，並先啟動伺服器。

## 目錄

| 路徑 | 內容 |
|---|---|
| `planner/agent.py` | Agent：Claude 自己決定呼叫哪些工具 |
| `planner/session.py` | 會談：開場、上次行動追蹤、強弱科建議、興趣測驗換算 |
| `planner/extract.py` | 拍照上傳的成績單、興趣測驗 → 表格 |
| `planner/summary.py` | 會談結束時整理會談紀錄 |
| `planner/profile.py` | 學生側寫：每筆變更附學生原話 |
| `planner/planning.py` | 規劃引擎（純程式）：興趣契合度、差距分析 |
| `planner/safety.py` | 危機字詞攔截與轉介 |
| `planner/app.py` | FastAPI API 與輸入驗證 |
| `web/` | 前端 |
| `data/stages/` | 教育階段包：`senior_high.json`（學群）、`junior_high.json`（群科） |
| `eval/` | 模擬學生評估 |
| `tests/` | 離線測試與瀏覽器自動測試 |

## 還沒做

- 價值觀卡牌（臺大會談使用的工具）
- 資源庫：營隊、大學先修、科展、志工、職場體驗
- 同儕顧問、專家顧問的媒合
- 自主學習計畫書引導（對應臺大的校學士）
- 換成查證過的真實學群資料

## 換模型

修改 `planner/llm.py` 的 `ADVISOR_MODEL`。預設是 Claude Opus 5.5（effort low）；想省錢可以改成 `claude-haiku-5-5`，改完跑一次 `eval.simulate` 比較效果。
