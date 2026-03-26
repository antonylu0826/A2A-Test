# A2A Protocol 實作擴展方向清單

基於我們已經完成的 A2A 前台路由 (Reception) 與獨立子代理 (ClaudeAgent, GoogleAgent) 的基礎架構，以下是幾個能讓系統更接近「企業級應用」的進階擴展方向：

## 第一層級：流程與自動化升級
### 1. 實作任務串聯協作 (Chain of Agents / Workflow)
目前 Reception 只是單純的「分派任務」給單一 Agent。這個擴展將實作真正的「工作流」。
- [x] **修改 Reception 邏輯**：當接收到複雜需求時，Reception 能拆解為多個步驟。
- [x] **Context 傳遞**：Reception 先呼叫 `ClaudeAgent` 進行資料重點分析，將拿到的 `result` 自動注入到新的 `context` 中。
- [x] **接力完成**：將挾帶 Claude 分析結果的 Context 打包，再次發送給 `GoogleAgent` 進行最終的文案生成。

### 2. 人機協作介入 (Human-in-the-Loop, HITL)
在實際商業場景中，某些高風險決策（例如：退款審核、對外寄送法律聲明）不能由 AI 全權掌握。
- [x] **新建 HumanAgent**：建立一個新的 Agent 端點，連接到某個前端介面或是 Slack/Line Chatbot。
- [x] **權限阻擋**：當 Reception 判斷任務具備高風險，它會將最後的結果透過 A2A 拋給 `HumanAgent`。
- [x] **人類審批**：只有在人類點擊「Approve」後，`HumanAgent` 才會回傳 A2A 成功訊號，完成任務。

---

## 第二層級：動態與資源共享升級
### 3. 導入 MCP 動態註冊機制 (Dynamic Registry via MCP)
目前的 `agent_registry.json` 是寫死的。在真實場景中，Agent 應該能動態上線與下線。
- [x] **實作動態註冊 API**：在 Reception 新增一個 `POST /register` 端點，讓子 Agent 啟動時主動將自己的 `Agent Card` 註冊給前台。
- [x] **結合 MCP (Model Context Protocol)**：把尋找對應子 Agent 的能力包裝成一個 MCP Tool，讓 Reception 的大模型可以自己查閱目前的線上編制。
  - *(已擴充：加入背景心跳偵測 Heartbeat 與 Graceful Shutdown 離線自動註銷)*

### 4. 建立狀態共享記憶體 (Shared Semantic Memory / RAG)
目前 A2A 是透過 JSON 傳遞整個 Context，這會導致 Token 開銷暴增。
- [x] **導入共用 Redis 或向量庫**：將所有大檔案、對話歷史與分析報告存在一個中央的 Vector DB 或 Redis 記憶體中。
- [x] **ID 傳遞**：Reception 和各個子 Agent 之間不再互傳好幾萬字的 Context，而是只傳 `session_id`。
- [x] **自我檢索**：當 GoogleAgent 拿到 `session_id` 後，自己去資料庫把 Claude 剛剛寫好的報告拉出來看。

---

## 第三層級：架構與安全治理升級
### 5. 非同步處理與狀態回報 (Async Processing & Webhooks)
當前的 A2A 實作是同步的 (Synchronous HTTP)，這代表如果 Claude 分析一份 100 頁的財報需要 3 分鐘，Reception 的請求就會佔用並可能 Timeout。
- [x] **修改 A2A Response 格式**：子 Agent 收到請求後立刻回傳 `{ "status": "processing", "task_id": "..." }`。
- [x] **實作 Callback 機制**：任務請求中挾帶 `webhook_url`。子 Agent 處理完畢後，主動發送 POST 請求將結果傳回給 Reception。

### 6. 安全與權限管控 (Security & RBAC)
在企業內網中，我們不能讓任何人都能隨便用 HTTP POST 去呼叫你的 `ClaudeAgent` (因為每一次呼叫都在燒錢！)。
- [x] **實作 OAuth2 / JWT 認證**：只有前台中樞 (Reception) 握有加密的 API Token。
- [x] **權限驗證**：所有的子 Agent 端點都會先檢查請求的 Header 中是否有合法的 `Bearer Token`，阻絕未經授權的越級打怪。

### 7. 任務廣播與競標協商 (Broadcast & Negotiation)
這是最前沿的多代理研究領域。不再由前台單方面指定誰做。
- [x] **廣播任務**：Reception 將任務 "Broadcast" 給所有的在線 Agent。
- [x] **信心值回報**：所有 Agent 在分析任務後，回報他們的「信心分數 (Confidence Score)」與「預期處理耗時」。
- [x] **自主競標**：Reception 根據回報的狀況，決定把任務交給最具信心、速度最快或成本最低的 Agent。
