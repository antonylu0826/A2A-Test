# 階段三：導入動態註冊機制 (Dynamic Registry)

為了讓 A2A 系統具備真正的微服務容錯與熱插拔（Hot-pluggable）能力，本階段我們將廢棄寫死的 `agent_registry.json`，改由各個 Agent 啟動時主動「打卡報到」。

## Proposed Changes

### 1. Reception (總機大腦) 升級
- **背景伺服器**：在 `Reception/main.py` 啟動一個 `FastAPI` (Port 8000) 背景執行緒。
- **註冊與註銷 API**：
  - 新增 `POST /a2a/register` 來接收子 Agent 的能力名片。
  - 新增 `POST /a2a/deregister` 來處理子 Agent 關閉時的註銷。
  - 建立基於記憶體的 `online_agents_registry` 清單。
- **動態路由 (Function Calling)**：實作 `get_online_agents()`，讓 Gemini LLM 在每次規劃 Workflow 時，只能從目前真正「在線」的活人名單中挑選打工仔。
- **健康巡邏 (Heartbeat)**：建立背景 `health_check_loop` 每 10 秒檢查一次清單內的成員是否無預警斷線 (被強制關閉視窗)，自動剔除死掉的進程。

### 2. 子 Agent (打工仔) 升級
修改 **Claude**, **Google**, **Human** 的程式碼，加入生命週期掛鉤：
- `@app.on_event("startup")`: 啟動時自動發送自己的 ID、URL 與 Capabilities 給 Port 8000 的大腦。
- `@app.on_event("shutdown")`: 正常關閉 (Ctrl+C) 時自動發送離線訊號給大腦註銷自己。
- 設定 `log_level="warning"` 避免健康檢查的 HTTP GET 洗版。

## Verification Plan
1. 啟動最新的 `start_all.bat`。
2. 觀察 Reception 終端機是否正確跳出三條 `🎉 新夥伴加入/更新` 訊息。
3. 刻意按右上角將其中一個 Agent 的黑視窗 X 掉 (強制關閉)。
4. 等待 10 秒鐘，觀察 Reception 是否列印出 `💔 偵測到夥伴無預警斷線，已剔除` 的訊息。
5. 正常發派任務，確認 Workflow 路由不會用到已陣亡的 Agent。
