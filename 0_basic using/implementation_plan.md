# A2A Protocol 小型實作藍圖 (POC)

這個 POC 將在本地端模擬一個微型的 Agent2Agent 網路。我們的目標是證明：「**前台 Agent 如何透過統一的 A2A 協議 (HTTP + JSON)，將不同廠商 SDK 寫成的 Agent 串接起來工作。**」

## 專案結構規劃
專案將分為三個獨立的微服務資料夾，並共用根目錄的環境設定。

*   **`.env`** (根目錄：集中存放所有 API 金鑰)
*   **`Reception/`** (前台/路由 Agent，負責指揮)
*   **`ClaudeAgent/`** (負責分析的子 Agent)
*   **`GoogleAgent/`** (負責文案的子 Agent)

---

## Proposed Changes

### 1. 定義 A2A 協議標準 (Protocol Definition)
所有 Agent 都將遵循以下簡化的 A2A 通訊格式：
- **Agent Card (名片)**：紀錄 Agent 的名稱、URL、以及能處理的要求描述。
- **Task Request (任務請求)**：`POST /a2a/task`，攜帶 `{ "task_id": "...", "instruction": "...", "context": {} }`。
- **Task Response (任務回應)**：回傳 `{ "status": "completed", "result": "..." }`。

### 2. 環境變數配置

#### [NEW] `a2a_test/.env` (根目錄)
集中儲存實機調用的金鑰：
```env
ANTHROPIC_API_KEY="your_api_key_here"
GOOGLE_API_KEY="your_api_key_here"
```

### 3. 子節點實作配置

#### [NEW] `ClaudeAgent/main.py`
- **職責**：接收前台派發的分析處理任務。
- **技術**：FastAPI 開放 `/a2a/task` 接口，內部調用 `anthropic` SDK，並讀取上層的 `.env`。
- **運行埠**：`http://localhost:8001`

#### [NEW] `GoogleAgent/main.py`
- **職責**：接收前台派發的撰寫/生成任務。
- **技術**：FastAPI 開放 `/a2a/task` 接口，內部調用 `google-genai` SDK，並讀取上層的 `.env`。
- **運行埠**：`http://localhost:8002`

### 4. 前台節點實作配置

#### [NEW] `Reception/main.py` & `agent_registry.json`
- **職責**：接收使用者的自然語言需求，利用基礎 LLM (例如使用 Gemini) 判斷是要派發給 ClaudeAgent 還是 GoogleAgent，然後透過 HTTP 發送標準的 A2A Request 組件。
- **依賴檔案**：
  - `agent_registry.json`：儲存 ClaudeAgent (8001) 與 GoogleAgent (8002) 的能力描述名片。

---

## Verification Plan
1. **環境配置**：在 `a2a_test` 建立共用的 Python `.venv`，安裝 `fastapi`, `uvicorn`, `anthropic`, `google-genai`, `requests`, `python-dotenv`。
2. **啟動子節點**：分別啟動 `ClaudeAgent` (8001) 與 `GoogleAgent` (8002)。
3. **執行前台測試**：執行 `Reception/main.py`，輸入測試要求（例如：「幫我從一篇文章中摘要出重點」）。
4. **驗證路由**：觀察 Reception 是否能讀取註冊表，正確判斷並將任務轉發給真實調用 API 的子 Agent，最後取回結果。
