# 階段四：建立狀態共享記憶體 (Shared Semantic Memory)

為了徹底解決 A2A 原本「把前面所有人的聊天紀錄全部塞進 JSON 傳遞給下一個 Agent」所帶來的 **Token 暴增** 以及 **網路傳輸 Payload 過大** 的問題，本階段我們將在 `Reception` 實作一個輕量級的「中央共用記憶體」。

## User Review Required
> [!IMPORTANT]
> 此版本的架構變動較大，所有的子 Agent 跟 Reception 中間的交換格式會改變，請確認以下機制是否符合你的預期！

## Proposed Changes

### 1. 儲存機制核心 (Memory Store)
在 `Reception` (Port 8000) 新增一個基於雜湊字典的記憶體庫：
```python
# session_id -> { "original_instruction": "...", "history": [], "shared_results": {} }
shared_memory_store = {}
```

#### [NEW] API 端點 `/a2a/memory/{session_id}`
- **GET**: 供子 Agent 呼叫，取得該對話目前的共享記憶。
- **POST**: 供 Reception 或子 Agent 呼叫，用來追加執行結果進這塊「公佈欄」。

---

### 2. A2A Payload 大幅瘦身
改變通訊協定，從原本的：
```json
{
  "task_id": "xxx",
  "instruction": "請生成文案",
  "context": { "step1_result": "長達5千字的報告", "source": "Reception" } // <--- Token 巨獸
}
```
**全面替換為極簡格式：**
```json
{
  "task_id": "xxx",
  "session_id": "sess_abc123",
  "instruction": "請生成文案",
  "memory_endpoint": "http://127.0.0.1:8000/a2a/memory/sess_abc123"
}
```

---

### 3. 子 Agent 獲取知識的方法改變

各個子 Agent (`ClaudeAgent`, `GoogleAgent`, `HumanAgent`) 的行為準則更改：
#### [MODIFY] ClaudeAgent/main.py
#### [MODIFY] GoogleAgent/main.py
#### [MODIFY] HumanAgent/main.py

當他們收到任務時，如果需要前面的上下文（Context），他們**必須主動打 API** 到 `memory_endpoint` 去擷取自己需要的資訊，然後把它交給自己背後的 LLM，並把算出的結果 `result` 拋回給 Reception。Reception 負責把這個 `result` 印在中央記憶體的佈告欄上。

## Open Questions

> [!WARNING]
> 未來如果這塊記憶體長大到一定程度，還是會有 Token 太多的問題，進階解法將是導入 Vector Database (RAG)。但目前 POC 階段先以「統一的中央字典 (Python Dict)」為主，這樣能快速驗證「資料與命令分離」的效果。這樣可以嗎？

## Verification Plan
1. **指令重構**: 執行新的 `start_all.bat`。
2. **多步測試**: 再次透過 `Reception` 命令工作流，觀察終端機列印出來的 Payload，**確保沒有出現落落長的 context JSON，而是短巧的 session_id**。
3. **正確性驗證**: 最後接手的 GoogleAgent 依然能寫出正確的文章，證明它有成功自己調用 API 去大腦讀取 Claude 剛寫好的分析報告。
