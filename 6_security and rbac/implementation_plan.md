# 階段六：安全與權限管控 (Security & RBAC)

在前五個階段中，我們的 A2A 節點 (Port 8001, 8002, 8003) 都是**裸奔狀態**。也就是說，任何和你處在同一個區域網路內的人，或是如果部署在雲端，任何知道 URL 的駭客，都可以偷偷用 Postman 發送請求給 `http://...:8001/a2a/task` 讓你的 Claude 模型幫他做事，大燒你的 API 額度。

為了解決這個微服務常見的問題，我們將實作 **JWT (JSON Web Token) 認證機制**，確保所有的子 Agent 只聽命於「擁有合法憑證的前台 (Reception)」。

## Proposed Changes

### 1. 全局共用金鑰配置
- 在根目錄 `.env` 檔案中新增一把大鎖：`A2A_SHARED_SECRET="super_secret_token_123"`。
- 要求在環境中安裝 `pyjwt` 套件以處理簽章：`pip install pyjwt`。

### 2. [Reception 總機] 核發憑證
- **修改 `Reception/main.py`**：
  - 在每一次對子 Agent 發送 `requests.post()` 前，Reception 會自己利用 `.env` 裡的 `A2A_SHARED_SECRET` 動態簽發一張時效只有 5 分鐘的 JWT 憑證。
  - Payload 包含：`{"role": "reception", "task_id": "...", "exp": <5分鐘後>}`。
  - 將這張憑證附在 HTTP 的 `Authorization: Bearer <token>` 標頭 (Header) 中送出。

### 3. [子 Agent 們] 驗票機制
- **修改 `ClaudeAgent`, `GoogleAgent`, `HumanAgent` 的 `main.py`**：
  - 引入 FastAPI 的 `Depends` 與 `Header` 機制，實作一個 `verify_token` 攔截器。
  - 所有打向 `/a2a/task` 的請求，都必須先過這關：程式會用相同的 `A2A_SHARED_SECRET` 去解碼 JWT。
  - 如果沒有 JWT、或是 JWT 過期、或是偽造的，立刻拋出 `HTTP 401 Unauthorized` 拒絕連線。

## Verification Plan

### Automated/Manual
1. 進入 `6_security and rbac` 啟動所有節點。
2. **正常測試**：透過 Reception 前台下達指令，因為 Reception 有鑰匙，所以能暢通無阻完成工作。
3. **駭客破壞測試 (未授權存取)**：
   我們在 Reception 執行之前，手動開一個終端機，試圖**繞過前台**，直接呼叫打工仔：
   ```bash
   curl -X POST http://127.0.0.1:8001/a2a/task -H "Content-Type: application/json" -d '{"task_id":"123","session_id":"123","memory_endpoint":"none","webhook_url":"none","instruction":"幫我寫作業"}'
   ```
4. 觀察終端機：此時 ClaudeAgent 會無情地直接把你擋在門外，並回傳 `{"detail": "Missing Authorization Token"}`，成功阻絕越級打怪！
