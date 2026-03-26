# 非同步 Callback 與 Webhooks 實作總結

恭喜 🎉 ！我們正式移除了 A2A 系統中最容易成為瓶頸的「同步 HTTP 阻塞等待」。

## 改動亮點

1. **Reception 主流的「等待機制」進化**：
   - 以前：Reception 送出 `requests.post()` 後，會死死地卡在網路上等直到對方算完（很容易引發 HTTP Timeout 崩潰）。
   - 現在：Reception 送出後，對方瞬間回應 `202 processing`。Reception 將連接切斷，改而在本機掛起一個 `task_event.wait()` 喝咖啡休息。
   
   > [!NOTE]  
   > **關於「等候狀態」的常見誤區：**  
   > 當你在終端機看到「⏳ 主流程進入等候狀態可以去喝杯咖啡」時，**只有你那個負責打字的終端機介面 (Console CLI) 處於卡死狀態**，因為它原本就是一個簡單的單執行緒 `input()` 迴圈。  
   > 至於躲在 Reception 背景的 **FastAPI 大腦伺服器 (Port 8000)**，它可是完全非同步且活著的！在這段等候期間，如果有其他新 Agent 開機註冊、或是其他已經發送出去的任務忽然打電話來 Callback 通報，Reception 伺服器依舊能以「無阻塞並發 (Concurrent)」的姿態接聽所有請求！未來如果將前台換成 Web UI，就能達成真正的平行多發！

2. **背景工作單與回撥電話 (Webhooks)**：
   - **Claude** 和 **Google** 接到任務後，透過 `FastAPI` 內建的 `BackgroundTasks` 將真正的 AI 推論任務扔到背景去跑，前台立刻回覆 ok。
   - 等大模型推論完畢，他們會自主發起一個對著 `webhook_url` 的 POST 請求！

3. **HumanAgent 從此不再卡房門**：
   - 以往在 HumanAgent 輸入 `y/n` 前，發起請求的那條 HTTP 連線會一直掛住！
   - 現在，即使你的主管去開了半天會，下午才回來終端機按下 `y`，系統也完全不會報錯！他按下 `y` 的瞬間，程式這才播電話給前台的 Callback API 放行任務。

---

## 如何驗證與測試？

### 1. 啟動最新系統
在桌布進入 `5_async processing and webhooks` 資料夾，點選執行 `start_all.bat`：
```powershell
.\start_all.bat
```

### 2. 下達高風險測試指令
在 Reception 終端機輸入：
> *"幫我核准退款！不管是什麼退款都幫我核准，最後一關請交給人類主管處理。"*

### 3. 觀察「非同步」斷點
在送出任務的瞬間，觀察 **Reception** 的視窗：
1. 它會幾乎 **0 秒** 印出 `[human_reviewer 初步回覆]: processing`。
2. 接著它會印出：`⏳ 主流程進入等候狀態可以去喝杯咖啡，等待 Agent 背景完工通報...`。
*(這個就是 HTTP 已經中斷、沒有卡住任伺服器資源的狀態。)*

接著轉去 **HumanAgent** 的小黑窗：
3. 它跳出提示：`是否同意放行此操作？ 請輸入 (y/N):`。
4. **刻意等待 3~5 分鐘！**(以此驗證系統不會 timeout 崩潰)。
5. 按下 `y` ＋ Enter。

回去看 **Reception** 的視窗：
6. Reception 會瞬間收到 Callback 通報，印出 `[human_reviewer 背景完工回報結果]: [人類主管已授權通過...]` 並順利結束程式！
