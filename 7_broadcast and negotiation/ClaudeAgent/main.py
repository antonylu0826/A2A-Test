from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header
from pydantic import BaseModel
from dotenv import load_dotenv
import anthropic
import os
from pathlib import Path
import jwt

# Load .env from the parent directory
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

A2A_SHARED_SECRET = os.getenv("A2A_SHARED_SECRET", "super_secure_a2a_shared_secret_key_123456789")

def verify_token(authorization: str = Header(default=None)):
    """攔截未授權的連線，並回傳原有的 authorization 標頭供後續使用"""
    if not authorization:
        print("[Claude 警衛] 🛑 攔截到外部未帶 JWT 憑證的惡意請求！拒絕連線！")
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            print("[Claude 警衛] 🛑 攔截到異常的 Authorization 格式！")
            raise HTTPException(status_code=401, detail="Invalid Authentication Scheme")
        # 驗證解密，但不取出 Payload，因為只是負責通關用
        jwt.decode(token, A2A_SHARED_SECRET, algorithms=["HS256"])
        return authorization
    except Exception as e:
        print(f"[Claude 警衛] 🛑 攔截到偽造或過期的 JWT！({e})")
        raise HTTPException(status_code=401, detail=f"Invalid Token: {str(e)}")

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
    webhook_url: str
    instruction: str

class TaskResponse(BaseModel):
    status: str
    result: str

class BidRequest(BaseModel):
    instruction: str

class BidResponse(BaseModel):
    confidence: float
    reason: str

@app.post("/a2a/bid", response_model=BidResponse)
async def handle_bid(request: BidRequest, authorization: str = Depends(verify_token)):
    capabilities = ["資料分析", "文章摘要", "重點提煉", "邏輯拆解", "資訊整理", "分析", "統計", "財報", "重點"]
    matches = sum([1 for cap in capabilities if cap in request.instruction])
    
    if matches > 0:
        confidence = min(0.9, 0.4 + (matches * 0.2))
        return BidResponse(confidence=confidence, reason=f"這是我擅長的分析領域，命中 {matches} 個能力標籤！")
    else:
        return BidResponse(confidence=0.1, reason="雖然不是分析專長，但我可以勉強試試。")

@app.post("/a2a/task", response_model=TaskResponse)
async def handle_task(request: TaskRequest, background_tasks: BackgroundTasks, authorization: str = Depends(verify_token)):
    print(f"[ClaudeAgent] Received Task ID: {request.task_id}")
    print(f"[ClaudeAgent] Instruction: {request.instruction}")
    
    # 將繁重的推論任務排入 FastAPI 的背景執行緒中
    background_tasks.add_task(process_task_background, request, authorization)
    
    # 立刻放行 HTTP 連線，前台 Reception 不會被 Timeout 卡死
    return TaskResponse(status="processing", result="請求已接收，正於背景全力運算中...")

def process_task_background(request: TaskRequest, authorization: str):
    import requests
    headers = {"Authorization": authorization}
    
    # Check for valid API key before calling
    if not api_key or api_key == "your_anthropic_api_key_here":
        result_text = "API key not configured. Mock response: Analysis complete based on instructions."
    else:
        try:
            # 主動向 Reception 大腦中央調閱此任務的歷史記憶
            memory_data = requests.get(request.memory_endpoint, headers=headers, timeout=5).json()
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
            print(f"[ClaudeAgent] Task {request.task_id} Completed.")
            
        except Exception as e:
            print(f"[ClaudeAgent] Error: {str(e)}")
            result_text = f"分析過程發生例外錯誤: {e}"

    # 任務完成後，主動撥打電話聯絡前台 Reception
    print(f"[ClaudeAgent] 正在回報結果至 Webhook...")
    try:
        requests.post(request.webhook_url, json={
            "status": "completed",
            "result": result_text
        }, headers=headers, timeout=5)
    except Exception as e:
        print(f"[ClaudeAgent] ⚠️ 無法回撥 Webhook 通報前台: {e}")

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
