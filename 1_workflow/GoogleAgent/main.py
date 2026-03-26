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
    instruction: str
    context: dict = {}

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
        prompt = f"你是一個專業的文案撰寫 Agent。你的任務是依照以下指令與上下文發想並撰寫內容。請用繁體中文回答。\n\nInstruction: {request.instruction}\nContext: {request.context}"
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
