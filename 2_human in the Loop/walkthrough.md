# 人機協作介入 (Human-in-the-Loop) 實作總結

單純讓 AI 互相溝通有失控風險，因此我們把「人類」也抽象成了一種特殊的 A2A 節點。

## 實作亮點
1. **建立 HumanAgent**：
   - 聽起來就像一般 Agent，接收一樣的 JSON Payload，也有一個端點。
   - 但它不扣任何大模型 API，而是使用 `input()` 阻塞，成為一個標準的人類卡控節點 (Gatekeeper)。
2. **Router 修改指令**：
   - 強制 Reception 遇到退款、發布、等關鍵字眼操作時，必須在 Workflow 的最後一步安排由 `human_reviewer` 簽核。
