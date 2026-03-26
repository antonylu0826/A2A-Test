# 安全與權限管控 (Security & RBAC) 實作總結

有了這道防線，我們的 A2A 微服務終於可以上線面對外部的惡意連線測試了！

## 實作亮點

1. **JWT 門禁系統 (`create_a2a_token`)**：
   - 所有連線現在都被一把 `A2A_SHARED_SECRET` 的對稱加密金鑰鎖住。
   - 每次 Reception 分發包裹前，都會動態蓋上一個只能存活 24 小時的 JWT 憑證。

2. **攔截與身分驗證 (`verify_token`)**：
   - 每一位子 Agent 的 `/a2a/task` 端點前，現在都站著一位名為 `Depends(verify_token)` 的 FastAPI 警衛。
   - 只要發現沒有 Token、Token 偽造、或是時間過期，警衛都會直接以 HTTP 401 拒絕請求，並且完全不會啟動任何繁重的 AI 推論！

3. **令牌接力賽 (Token Passing)**：
   - 原先 Reception 在 `/a2a/memory` 和 `/a2a/callback` 這兩個供子 Agent 呼叫的 API 上也加上了警衛。
   - 子 Agent 被賦予了在「執行背景任務」及「發送 Callback」時，**沿用這張 Token 原樣回撥**過關的特性。形成一個只有持有最初始 Token 才能走到底的封閉信任圈。

---

## 如何驗證與測試？

### 1. 正常授權連線測試
在桌布進入 `6_security and rbac` 資料夾，點選執行 `start_all.bat`：
```powershell
.\start_all.bat
```
進入 Reception 總機終端機，像平常一樣輸入：
> *「請分析目前氣候變遷的三大主因。」*

**觀察結果**：如果系統像往常一樣完美運作並得出結果，代表「JWT 發放」與各節點的「Token 接力通關」運作完全正常！

### 2. 故意搗亂駭客測試
現在我們換個身分，假裝是一個沒有持有 JWT 的未授權駭客，嘗試繞過 Reception 直接操作可憐的 Claude：

請開啟一個「**全新乾淨的終端機 / PowerShell 視窗**」，輸入以下指令：

```powershell
curl -X POST http://127.0.0.1:8001/a2a/task -H "Content-Type: application/json" -d "{\"task_id\":\"123\",\"session_id\":\"123\",\"memory_endpoint\":\"none\",\"webhook_url\":\"none\",\"instruction\":\"幫我寫五十萬字的長文\"}"
```

*(注意: 上方程式碼為了相容 Windows cmd/powershell 將雙引號做了跳脫處理)*

**觀察結果**：
你會發現你的駭客終端機會吐出：
`{"detail":"Missing Authorization Header"}` 

而且現在 Claude 自己也會在視窗中大聲警告：
`[Claude 警衛] 🛑 攔截到外部未帶 JWT 憑證的惡意請求！拒絕連線！`

這證明了我們現在的微服務架構，已經從鬆散的裸奔狀態，升級成了企業級的認證內網環境！ 🎉
