from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
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
        print("[Google 警衛] 🛑 攔截到外部未帶 JWT 憑證的惡意請求！拒絕連線！")
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            print("[Google 警衛] 🛑 攔截到異常的 Authorization 格式！")
            raise HTTPException(status_code=401, detail="Invalid Authentication Scheme")
        jwt.decode(token, A2A_SHARED_SECRET, algorithms=["HS256"])
        return authorization
    except Exception as e:
        print(f"[Google 警衛] 🛑 攔截到偽造或過期的 JWT！({e})")
        raise HTTPException(status_code=401, detail=f"Invalid Token: {str(e)}")

# Load .env from the parent directory
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

app = FastAPI(title="Google Writer Agent", description="A2A Node for Content Generation tasks")

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key or api_key == "your_google_api_key_here":
    print("WARNING: GOOGLE_API_KEY is not set or is using the default placeholder.")

# Initialize Google GenAI client
client = genai.Client(api_key=api_key) if api_key and api_key != "your_google_api_key_here" else None

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
    capabilities = ["文案撰寫", "內容生成", "故事發想", "行銷推廣", "信件回覆", "寫", "小說", "散文", "文章", "故事"]
    matches = sum([1 for cap in capabilities if cap in request.instruction])
    
    if matches > 0:
        confidence = min(0.95, 0.4 + (matches * 0.2))
        return BidResponse(confidence=confidence, reason=f"寫作與創作是我的強項，命中 {matches} 個能力標籤！")
    else:
        return BidResponse(confidence=0.1, reason="如果沒有人要做，我可以當備胎補刀。")

@app.post("/a2a/task", response_model=TaskResponse)
async def handle_task(request: TaskRequest, background_tasks: BackgroundTasks, authorization: str = Depends(verify_token)):
    print(f"[GoogleAgent] Received Task ID: {request.task_id}")
    print(f"[GoogleAgent] Instruction: {request.instruction}")
    
    # 將推論任務排入背景
    background_tasks.add_task(process_task_background, request, authorization)
    return TaskResponse(status="processing", result="請求已接收，文案醞釀生成中...")

def process_task_background(request: TaskRequest, authorization: str):
    import requests
    headers = {"Authorization": authorization}
    
    if not client:
        result_text = "API key not configured. Mock response: Generated creative content based on instructions."
    else:
        try:
            # 主動向 Reception 大腦中央調閱此任務的歷史記憶
            memory_data = requests.get(request.memory_endpoint, headers=headers, timeout=5).json()
            history = memory_data.get("history", [])

            prompt = f"你是一個專業的文案撰寫 Agent。你的任務是依照以下指令與上下文發想並撰寫內容。請用繁體中文回答。\n\nInstruction: {request.instruction}\nShared Memory History:\n{history}"
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            
            result_text = response.text
            print(f"[GoogleAgent] Task {request.task_id} Completed.")
            
        except Exception as e:
            print(f"[GoogleAgent] Error: {str(e)}")
            result_text = f"文案撰寫過程發生錯誤: {e}"

    print(f"[GoogleAgent] 正在回報結果至 Webhook...")
    try:
        requests.post(request.webhook_url, json={
            "status": "completed",
            "result": result_text
        }, headers=headers, timeout=5)
    except Exception as e:
        print(f"[GoogleAgent] ⚠️ 無法回撥 Webhook 通報前台: {e}")

@app.on_event("startup")
async def register_agent():
    print("[GoogleAgent] 啟動中... 準備向 Reception 註冊自己")
    import requests
    try:
        requests.post("http://127.0.0.1:8000/a2a/register", json={
            "id": "google_writer",
            "name": "Google Writer Agent",
            "url": "http://127.0.0.1:8002/a2a/task",
            "capabilities": ["文案撰寫", "內容生成", "故事發想", "行銷推廣", "信件回覆"],
            "description": "擅長創作與文字生成。當任務需要撰寫新的內容、回覆信件、發想創意文案或擴寫文章時，請發送給此 Agent。"
        }, timeout=5)
        print("[GoogleAgent] 成功向 Reception 報到！")
    except Exception as e:
        print(f"[GoogleAgent] 無法連線至 Reception 進行註冊，錯誤: {e}")

@app.on_event("shutdown")
async def deregister_agent():
    print("[GoogleAgent] 關閉中... 向 Reception 註銷自己")
    import requests
    try:
        requests.post("http://127.0.0.1:8000/a2a/deregister", json={"id": "google_writer"}, timeout=5)
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    # 將 log-level 設為 warning 減少 FastAPI 預設 request log 洗頻
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="warning")
