# A2A Protocol v1.0 正式實作文件 (8_official_a2a_protocol)

本文件詳述了 `8_official_a2a_protocol` 的架構設計與實作細節。此專案已完全過渡至官方 **A2A Protocol v1.0** 規範，確保與其他遵循此協議的代理系統具備互操作性。

---

## 核心架構變更

### 1. 官方 SDK 整合
- **選擇**：全面採用官方 `a2a-sdk` Python Kit。
- **優點**：自動處理 JSON-RPC 2.0 封裝、Task 狀態機邏輯、以及符合規格的 HTTP/SSE 傳輸。

### 2. 路由與發現機制 (Discovery)
- **移除舊有註冊制**：捨棄了子代理向總機主動 POST 註冊的私有協定。
- **標準 AgentCard 發現**：每個 Agent 均實作 `/.well-known/agent-card.json` 端點。Reception 啟動時會主動拉取此名片，根據 `skills` 與 `capabilities` 進行任務分派。
- **路由策略**：由 Reception 使用 Gemini 2.0 Flash 進行智慧路由，取代了舊版的競標機制，提升了複雜任務的拆解與接力能力。

### 3. 非同步與串流支援 (Async & SSE)
- **全面非同步運作**：所有 Agent Executor 均已修正為 `AsyncAnthropic` 或 `google.genai.aio`，確保高併發下不阻塞 Event Loop。
- **SSE 串流**：實作了 `TaskArtifactUpdateEvent` 增量推送，讓使用者能即時看到 Claude 或 Gemini 產出的文字。

---

## 實作細節

### 目錄結構
- `Reception/`: A2A Client，職責為任務編排與智慧路由。
- `ClaudeAgent/`: 專業分析代理，整合 Anthropic API。
- `GoogleAgent/`: 創意內容代理，整合 Google Gemini API。
- `HumanAgent/`: 安全閘門，利用 `input-required` 狀態實現人工審核。
- `agent_executor.py`: 各目錄下的核心邏輯，繼承自 `a2a.server.agent_execution.AgentExecutor`。

### 關鍵端點
- **AgentCard**: `http://<host>:<port>/.well-known/agent-card.json`
- **A2A Endpoint**: `http://<host>:<port>/` (處理 JSON-RPC 請求)

---

## 安全機制：Human-in-the-Loop
- **攔截觸發**：當指令包含「授權」、「發布」、「退款」等敏感關鍵字時，Reception 會優先導向 `HumanAgent`。
- **狀態流轉**：`HumanAgent` 會將任務狀態設為 `input-required`，此時 A2A 連線保持開啟但不結束。
- **人工決策**：在 `HumanAgent` 選項終端機輸入 `approve` 或 `deny` 後，狀態才會轉為 `completed` 或 `failed`，並回傳至 Reception。

---

## 已解決的技術難題 (Troubleshooting)
1. **ModuleNotFoundError**: 透過在 `__main__.py` 注入 `sys.path` 解決了 `agent_executor` 模組導不進來的問題。
2. **Deprecation Warnings**: 將所有 `agent.json` 的參照更新為最新的 `agent-card.json`。
3. **Async Blocking**: 將同步的 LLM 客戶端全部更換為 `Async` 版本，修復了串流卡死的問題。
4. **Timeout Error**: 在 Reception 的 `httpx` 客戶端關閉了超時限制，確保有足夠時間等待人工操作。
