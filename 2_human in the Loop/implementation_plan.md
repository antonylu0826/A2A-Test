# 階段二：人機協作介入 (Human-in-the-Loop, HITL)

本階段的目標是驗證 A2A 協議不只能串接 AI，也能把「人類」抽象化為一個標準的 Agent 節點。當需要高風險決策時，大腦能自動將流程導向人類審核員。

## Proposed Changes

### 1. 新增人類審核節點 (HumanAgent)
新增一個資料夾 `HumanAgent/`，包含 `main.py`：
- **職責**：扮演人類決策的代理伺服器。
- **技術**：FastAPI 開放 `/a2a/task` 接口。與其他呼叫 LLM 的 Agent 不同，它在收到請求後，會透過終端機 `input()` 阻塞等待真實人類的輸入（輸入同意或拒絕的指令）。
- **運行埠**：`http://localhost:8003`

### 2. 前台 (Reception) 註冊表與路由調整
- **更新註冊表**：在 `Reception/agent_registry.json` 中加入 `HumanAgent` 的能力說明 (Capabilities: "人類決策、最終授權、人工審核")，以及提示大模型何時該使用它。
- **更新 Router Prompt**：嚴格指示大模型，只要使用者的需求牽涉到「對外發布」、「付款」、「高風險決策」時，必須在 Workflow 的 **「最後一個步驟」** 強制插入交給 `human_reviewer` 審核的命令。
- **延長 Timeout**：將 A2A 的 Request 預設 Request Timeout 從短暫的幾十秒延長至 `300` 秒，以容納人類閱讀和思考的時間。

## Verification Plan
1. **啟動所有子節點**：啟動 `ClaudeAgent` (8001), `GoogleAgent` (8002), 以及全新的 `HumanAgent` (8003)。
2. **執行前台測試**：執行 `Reception/main.py`。
3. **場景 1 (一般任務)**：要求「幫我分析這篇文章」，確認 Reception 不會調用 HumanAgent。
4. **場景 2 (高風險任務)**：要求「請分析文章並幫我把最終草稿發布到 Facebook 上」。
5. **觀察與阻擋**：觀察 Reception 是不是規劃了最後一步給 HumanAgent。並跑到 HumanAgent 的終端機按下拒絕，看看 Reception 是否會正確回報任務中止。
