# 階段五：非同步處理與狀態回報 (Async Processing & Webhooks)

在前幾個階段中，我們的前台 Reception 派發任務給 Agent 後，是使用 `requests.post(..., timeout=300)` 來**同步阻塞等待**。
這在企業級應用中是不可行的，因為：
1. **連線逾時風險**：如果 LLM 分析一份財報需要 5 分鐘，HTTP 連線非常容易被中途的 Proxy 或防火牆切斷。
2. **單點卡死**：前台會卡在那裡發呆，無法平行分派任務給其他人。

為此，本階段我們將實作 **Webhooks (Callback) 架構**：Agent 收到要求會瞬間回覆 202 Accepted，處理完畢再主動敲你的電話把結果送回。


## Proposed Changes

### [Reception 總機]

#### [MODIFY] `Reception/main.py`
- 新增一個全域變數 `task_callbacks = {}`，用來儲存 `task_id` 與其對應的 `threading.Event()` 與 `result`。
- 新增一組開放 API：`POST /a2a/callback/{task_id}`：
  - 任何人朝這個網址發送 `{"status": "completed", "result": "..."}`。
  - 對應的 `Event` 就會被設定為完成，喚醒卡住的主流程。
- 改寫派發迴圈：
  - 送出 `requests.post()` 後不等待完成結果，它只會收到 `{"status": "processing", "task_id": "..."}`。
  - 在 Payload 中新增 `webhook_url: "http://127.0.0.1:8000/a2a/callback/{task_id}"`。
  - 在終端機印出「⏳ 任務處理中，進入等待狀態...」。
  - 呼叫 `task_event.wait()` 直到接聽電話的終端接收到訊號。

### [ClaudeAgent / GoogleAgent / HumanAgent]

#### [MODIFY] 所有子 Agent 的 `main.py`
- 更新 Pydantic Payload，新增 `webhook_url: str` 欄位。
- 改寫 `handle_task` 流程：
  - **接收端**：不再跑攏長的流程，而是透過 FastAPI 的 `BackgroundTasks`，把任務塞進背景工作佇列。然後**立刻 `return {"status": "processing"}`** 給前台。
  - **背景代碼**：真正在呼叫大模型或是卡住 `input()` 等待人類回應的函數。
  - **處理完畢**：大模型算完或人類決定完之後，主動對當初帶過來的 `webhook_url` 發出 `requests.post()` 通報結果。

## Verification Plan

### Automated/Manual
1. 啟動 `start_all.bat`，包含所有的 Agents。
2. 在 Reception 輸入任務（例如：請人類主管同意一件小事情）。
3. 觀察終端機變化：
   - Reception 將**瞬間**印出 `[預期收到: processing]`，而不是卡死。
   - Reception 印出等待符號。
   - Human Agent 此時才會跳出詢問 `input()`。
   - 人類慢吞吞地去喝杯咖啡，五分鐘後才在 HumanAgent 視窗打入 `y`。
   - Reception 馬上印出：「收到 Callback 結果：已授權通過...」。
4. 這個架構將證明我們的系統具備「非同步長時間運行任務 (Long-running async tasks)」的生存能力。
