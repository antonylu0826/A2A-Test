from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys

app = FastAPI(title="Human Reviewer Agent", description="A2A Node for Human-in-the-Loop tasks")

class TaskRequest(BaseModel):
    task_id: str
    instruction: str
    context: dict = {}

class TaskResponse(BaseModel):
    status: str
    result: str

@app.post("/a2a/task", response_model=TaskResponse)
async def handle_task(request: TaskRequest):
    print("="*50)
    print(f"[HumanAgent] 收到高風險操作授權請求！ ID: {request.task_id}")
    print(f"[HumanAgent] 具體指示: {request.instruction}")
    print(f"[HumanAgent] 前置相關 Context:")
    for key, value in request.context.items():
        if key != "source":
            print(f"  - {key}: {str(value)[:200]}...") # 只印出前 200 字以避免洗頻
            
    print("="*50)
    
    # 阻塞等待人類輸入
    decision = input("\n[HITL] 是否同意放行此操作？ 請輸入 (y/N): ").strip().lower()
    
    if decision == 'y':
        print("[HumanAgent] 人類已授權通過。")
        return TaskResponse(status="completed", result="[人類主管已授權通過此高風險操作，且已確認前置資料無誤。]")
    else:
        print("[HumanAgent] 人類拒絕授權！")
        return TaskResponse(status="rejected", result="[人類主管已拒絕此高風險操作，任務終止。]")


if __name__ == "__main__":
    import uvicorn
    # 將 log-level 設為 warning 減少 FastAPI 預設 request log 洗頻，讓人類介面乾淨一點
    uvicorn.run(app, host="127.0.0.1", port=8003, log_level="warning")
