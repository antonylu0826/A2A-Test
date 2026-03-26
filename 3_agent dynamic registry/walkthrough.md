# 動態 API 註冊與容錯機制 實作總結

這個階段讓 A2A 從「靜態配置」走向了「微服務的熱插拔」。我們的 Agent 從此具備了加入與斷線被偵測的能力。

## 實作亮點
1. **動態註冊 (API Registration)**：
   - 廢棄寫死的 `agent_registry.json`，改用 API POST 接收。
   - 子節點掛載 `@app.on_event("startup")` 啟動主動打卡報到。
2. **優雅退出與自動註銷**：
   - 子節點掛載 `@app.on_event("shutdown")` 在按下 Ctrl+C 時主動揮手再見。
3. **心跳檢查與容錯 (Heartbeat / Health Check)**：
   - Reception 新增背景維護任務迴圈，每 10 秒去抓一次 Agent 的狀態。
   - 當 Agent 視窗被「強制關閉 X 掉」時，前台能偵測到 ConnectionError 並將陣亡的名單剃除，保障後續的 Router 不會把任務發送到死胡同中。
