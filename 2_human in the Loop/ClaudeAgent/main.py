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
    instruction: str
    context: dict = {}

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
        # Call Anthropic API
        prompt = f"Instruction: {request.instruction}\n\nContext: {request.context}"
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
