# Agent-to-Agent (A2A) Orchestration PoC

這是一個從零開始打造的企業級微服務「**多代理系統通訊架構 (Multi-Agent Architecture)**」概念驗證專案。
本專案的目標在於解決大語言模型代理在叢集化協作時所面臨的五大瓶頸：**服務擴展、記憶體負擔、同步堵塞、連線資安、與智慧分工**。

## 🏛 核心架構演進

本專案透過七個漸進式的階段，逐步建立起一套高併發、高安全性的 A2A 網路架構：

1. **基礎代理功能 (Base AI Script)**：從單機版的 Gemini / Claude 呼叫開始。
2. **無狀態微服務 (Stateless Microservices)**：將 Agent 包裝成 FastAPI 獨立服務，透過 HTTP 介接。
3. **動態註冊機制 (Dynamic Registry)**：總機 (Reception) 自動探索並定時巡邏子代理，取代寫死的服務清單。
4. **共享語意記憶體 (Shared Semantic Memory)**：捨棄傳統在 Payload 夾帶歷史對話的作法，改用中央記憶庫，大幅節省 Token 並提升速度。
5. **非同步信號處理 (Async Webhooks)**：利用背景任務與事件驅動 Webhook，解決長耗時任務造成的 HTTP Timeout。
6. **安全與權限管控 (Security & RBAC)**：導入 JWT (JSON Web Token) 短效通行機制與攔截器，防止內網未授權盜用 API 額度。
7. **大聲公競標市場 (Broadcast & Negotiation)**：拋棄總機的中央集權派發，改由全網子代理根據專長「自主評定信心值並出價標案」。

---

## 🚀 系統組成

系統中扮演「前台中樞」與「專業代理」的四個節點，每個節點均可獨立在一台伺服器上運行：

- **Reception 總機大腦 (`port: 8000`)**：
  負責解析使用者意圖、維護線上聯絡簿、管理中央記憶庫，並對全網進行任務拆解與大聲公外包廣播。
- **ClaudeAgent 數據分析師 (`port: 8001`)**：
  主打資料分析與摘要提煉，配置 JWT 攔截器，擁有字串光速分析的神經反射機制。
- **GoogleAgent 創意寫手 (`port: 8002`)**：
  主打原創文字與故事發想。
- **HumanAgent 人類決策閥 (`port: 8003`)**：
  這是整套系統的「核保險絲」。當指令牽涉到退款、授權、發布等高敏感行為時，會強制以 `1.0` 滿分阻斷所有自動化 AI 的競標，並拉起人工卡控終端機阻止流程。

---

## 🛠 安裝與啟動說明

### 1. 環境變數設定
請複製一份根目錄的範例金鑰檔，並替換為您自己的對稱金鑰與 API Keys：
```bash
cp .env.example .env
```
*(請特別注意，若要啟動第六階段以後的架構，請確保 `A2A_SHARED_SECRET` 字串長度超過 32 Bytes。)*

### 2. 安裝套件
請確定您具有 `fastapi`, `uvicorn`, `requests`, `anthropic`, `google-genai`, `pyjwt`, `python-dotenv` 等相依套件：
```bash
pip install -r requirements.txt # (若有準備的話)
```

### 3. 一鍵啟動 (以最先進的第七階段為例)
進入第七階段的資料夾，執行批次檔啟動四顆大腦：
```bash
cd "7_broadcast and negotiation"
./start_all.bat
```
*(Windows 環境下可直接雙擊執行腳本，腳本將自動為每個代理開啟獨立的命令提示字元)*

接著在 Reception 的終端機視窗中，下達複雜的文字指令（如：「請幫我寫一篇關於科技趨勢的文章，並且授權給我三百元宣傳費」），即可觀察整套**「廣播、競標、人類攔截、背景完成」**的迷人全過程！
