from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
import os
from pathlib import Path

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
    instruction: str

class TaskResponse(BaseModel):
    status: str
    result: str

@app.post("/a2a/task", response_model=TaskResponse)
async def handle_task(request: TaskRequest):
    print(f"[GoogleAgent] Received Task ID: {request.task_id}")
    print(f"[GoogleAgent] Instruction: {request.instruction}")
    
    # Check for valid API key before calling
    if not client:
        return TaskResponse(
            status="error",
            result="API key not configured. Mock response: Generated creative content based on instructions."
        )

    try:
        # 主動向 Reception 大腦中央調閱此任務的歷史記憶
        import requests
        memory_data = requests.get(request.memory_endpoint, timeout=5).json()
        history = memory_data.get("history", [])

        prompt = f"你是一個專業的文案撰寫 Agent。你的任務是依照以下指令與上下文發想並撰寫內容。請用繁體中文回答。\n\nInstruction: {request.instruction}\nShared Memory History:\n{history}"
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        result_text = response.text
        print(f"[GoogleAgent] Task Completed.")
        
        return TaskResponse(status="completed", result=result_text)
        
    except Exception as e:
        print(f"[GoogleAgent] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
