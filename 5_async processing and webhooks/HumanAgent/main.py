from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import sys

app = FastAPI(title="Human Reviewer Agent", description="A2A Node for Human-in-the-Loop tasks")

class TaskRequest(BaseModel):
    task_id: str
    session_id: str
    memory_endpoint: str
    webhook_url: str
    instruction: str

class TaskResponse(BaseModel):
    status: str
    result: str

@app.post("/a2a/task", response_model=TaskResponse)
async def handle_task(request: TaskRequest, background_tasks: BackgroundTasks):
    print("="*50)
    print(f"[HumanAgent] 🔔 收到高風險操作授權請求！ ID: {request.task_id}")
    print(f"               (請求已透過 Webhook 模式接收，前台不會發生超時)")
    print("="*50)
    
    # 讓堵塞終端機的 input 動作退居背景執行緒
    background_tasks.add_task(process_task_background, request)
    return TaskResponse(status="processing", result="請求已接聽，等待人類主管做出最終決策中...")

def process_task_background(request: TaskRequest):
    print(f"\n[Human Agent 工作介面]")
    print(f"任務 ID: {request.task_id}")
    print(f"具體指示: {request.instruction}")
    
    # 主動去記憶體庫把歷史紀錄撈回來給人類看
    import requests
    try:
        memory_data = requests.get(request.memory_endpoint, timeout=5).json()
        print(f"\n[大腦記憶體上下文 (Context)]")
        for item in memory_data.get("history", []):
            print(f"  - [{item['source']}]: {str(item['content'])[:200]}...")
    except Exception as e:
        print(f"[HumanAgent] 無法取得共享記憶: {e}")
            
    # 這裡的 input 是卡住這個背景執行緒，完全不用擔心 Timeout
    decision = input("\n[HITL] 是否同意放行此操作？ 請輸入 (y/N): ").strip().lower()
    
    if decision == 'y':
        result_text = "[人類主管已授權通過此高風險操作，且已確認前置資料無誤。]"
        print("[HumanAgent] 人類已授權通過。")
    else:
        result_text = "[人類主管已拒絕此高風險操作，任務終止。]"
        print("[HumanAgent] 人類拒絕授權！")

    print(f"[HumanAgent] 正在回報決策至 Webhook...")
    try:
        requests.post(request.webhook_url, json={
            "status": "completed",
            "result": result_text
        }, timeout=5)
    except Exception as e:
        print(f"[HumanAgent] ⚠️ 無法回撥 Webhook 通報前台: {e}")


@app.on_event("startup")
async def register_agent():
    print("[HumanAgent] 啟動中... 準備向 Reception 註冊自己")
    import requests
    try:
        requests.post("http://127.0.0.1:8000/a2a/register", json={
            "id": "human_reviewer",
            "name": "Human Reviewer Agent",
            "url": "http://127.0.0.1:8003/a2a/task",
            "capabilities": ["人類審核", "最終授權", "高風險操作確認"],
            "description": "當任務包含發布、付款、對外寄信等高風險決策時，必須將最後一個步驟指派給此 Agent 進行人類授權。"
        }, timeout=5)
        print("[HumanAgent] 成功向 Reception 報到！")
    except Exception as e:
        print(f"[HumanAgent] 無法連線至 Reception 進行註冊，錯誤: {e}")

@app.on_event("shutdown")
async def deregister_agent():
    print("[HumanAgent] 關閉中... 向 Reception 註銷自己")
    import requests
    try:
        requests.post("http://127.0.0.1:8000/a2a/deregister", json={"id": "human_reviewer"}, timeout=5)
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    # 將 log-level 設為 warning 減少 FastAPI 預設 request log 洗頻，讓人類介面乾淨一點
    uvicorn.run(app, host="127.0.0.1", port=8003, log_level="warning")
