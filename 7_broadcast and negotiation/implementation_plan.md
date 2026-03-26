# 階段七：任務廣播與競標協商 (Broadcast & Negotiation)

> 這是 A2A Proof-of-Concept 的最後一個重量級階段，我們即將把這個系統推向最前沿的多代理架構。

在前幾個階段中，Reception 作為一個**「獨裁的中央大腦」**，必須依賴 Gemini 去硬性決定每個步驟該給誰做 (e.g. `agent_id: claude_analyst`)。但問題來了：假如未來系統中有 100 個專長重疊的子 Agent，Reception 根本無法準確判斷誰最合適，且把所有 Agent 清單塞進 Prompt 會直接爆掉。

為了解決這個瓶頸，我們將實作最先進的 **「自由市場競標機制 (Market Bidding)」**。

## User Review Required

> [!IMPORTANT]
> **架構顛覆預警：**
> - Reception 的 AI Router 將**不再指定任何人**。它只負責把用戶的大任務「拆解成步驟 (Steps)」，然後直接把步驟的大聲公廣播 (Broadcast) 給全網。
> - 所有子 Agent 會新增一個 `/a2a/bid` 的競標用網路端點。
> - 為了節省各個 Agent 打一次 API 來計算信心的費用與時間，我們會採用**「關鍵字演算法 (Heuristic String Matching)」**來當作他們大腦的快速反射神經，能在 0.01 秒內對任務給出 $0 \sim 1.0$ 的自信分數！

## Proposed Changes

### 1. [子 Agent 們] 實作自主評估神經 (Bidding Endpoint)
- **修改 `ClaudeAgent`, `GoogleAgent`, `HumanAgent`**：
  - 新增 `POST /a2a/bid` 路由（一樣要受 `verify_token` 保護）。
  - 當收到廣播的 `instruction` 面試題時，利用計算自己的 `capabilities` 與指令的重疊度，給出一個 `confidence_score: float` (0.00 ~ 1.00) 與 `estimated_time: int` (預估耗時)。
  - 例如：HumanAgent 看到指令中有「退款、發布、授權」，直接回覆 1.0 絕對自信；GoogleAgent 看到「寫一篇文章」，回覆 0.95 高度自信。

### 2. [Reception 總機] 廣播與開標機制
- **修改 `route_request` (AI 大腦)**：
  - 不再依賴大模型去挑人，修改 Schema，只要求大模型把任務**拆解成不同步驟的概念指令**。
- **修改 `main` (執行邏輯)**：
  - 輪到每個步驟時，對在線名單 `online_agents_registry` 發起多執行緒的平行廣播 `POST /a2a/bid` 徵詢意願。
  - 統一收集所有標單，選擇 `confidence_score` 最高的 Agent。如果最高分低於 0.3，代表根本沒有人會做這個任務，系統自動中斷並發出無法勝任的警告。
  - 將最終的正式任務 `POST /a2a/task` 發給得標的那個 Agent。

## Verification Plan

### Automated/Manual
1. 進入 `7_broadcast and negotiation` 啟動所有節點。
2. 透過 Reception 前台下達指令：*「我要寫一篇關於區塊鏈的兩千字故事小說」*。
3. 觀察這時候畫面上就不會是 Reception 指定人。而是出現有趣的競標過程：
   ```text
   [廣播開標中] 📢 尋找適合執行: "寫一篇關於區塊鏈的兩千字故事" 的 Agent...
     - [HumanAgent] 棄權 (信心: 0.0)
     - [ClaudeAgent] 躍躍欲試 (信心: 0.4 - "我可以分析資料...")
     - [GoogleAgent] 強烈建議交給我！(信心: 0.9 - "這是我的原創寫作專長！")
   🏆 得標者：GoogleAgent！開始正式派發任務...
   ```
4. 確認最終是由得分最高且最合適的代理接下這個階段。
