from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import anthropic
import os
from pathlib import Path

# Load .env from the parent directory
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

app = FastAPI(title="Claude Analysis Agent", description="A2A Node for Analysis tasks")

# Initialize Anthropic client
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key or api_key == "your_anthropic_api_key_here":
    print("WARNING: ANTHROPIC_API_KEY is not set or is using the default placeholder.")

client = anthropic.Anthropic(api_key=api_key)

class TaskRequest(BaseModel):
    task_id: str
    session_id: str
    memory_endpoint: str
    instruction: str

class TaskResponse(BaseModel):
    status: str
    result: str

@app.post("/a2a/task", response_model=TaskResponse)
async def handle_task(request: TaskRequest):
    print(f"[ClaudeAgent] Received Task ID: {request.task_id}")
    print(f"[ClaudeAgent] Instruction: {request.instruction}")
    
    # Check for valid API key before calling
    if not api_key or api_key == "your_anthropic_api_key_here":
        return TaskResponse(
            status="error",
            result="API key not configured. Mock response: Analysis complete based on instructions."
        )

    try:
        # 主動向 Reception 大腦中央調閱此任務的歷史記憶
        import requests
        memory_data = requests.get(request.memory_endpoint, timeout=5).json()
        history = memory_data.get("history", [])
        
        # Call Anthropic API
        prompt = f"Instruction: {request.instruction}\n\nShared Memory History:\n{history}"
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            temperature=0.2,
            system="你是一個專業的資料分析 Agent。你的任務是精確地依照指令分析提供的內容，並摘要出重點。請用繁體中文回答。",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        result_text = response.content[0].text
        print(f"[ClaudeAgent] Task Completed.")
        
        return TaskResponse(status="completed", result=result_text)
        
    except Exception as e:
        print(f"[ClaudeAgent] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def register_agent():
    print("[ClaudeAgent] 啟動中... 準備向 Reception 註冊自己")
    import requests
    try:
        requests.post("http://127.0.0.1:8000/a2a/register", json={
            "id": "claude_analyst",
            "name": "Claude Analysis Agent",
            "url": "http://127.0.0.1:8001/a2a/task",
            "capabilities": ["資料分析", "文章摘要", "重點提煉", "邏輯拆解", "資訊整理"],
            "description": "擅長分析大量文字內容，找出重點並精確總結。遇到需要理解複雜文件或要求摘要時，請發送給此 Agent。"
        }, timeout=5)
        print("[ClaudeAgent] 成功向 Reception 報到！")
    except Exception as e:
        print(f"[ClaudeAgent] 無法連線至 Reception 進行註冊，錯誤: {e}")

@app.on_event("shutdown")
async def deregister_agent():
    print("[ClaudeAgent] 關閉中... 向 Reception 註銷自己")
    import requests
    try:
        requests.post("http://127.0.0.1:8000/a2a/deregister", json={"id": "claude_analyst"}, timeout=5)
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    # 將 log-level 設為 warning 減少 FastAPI 預設 request log 洗頻
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")
