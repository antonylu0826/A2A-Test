import json
import os
import requests
import uuid
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

# Load .env
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("GOOGLE_API_KEY")

registry_path = Path(__file__).parent / 'agent_registry.json'

with open(registry_path, 'r', encoding='utf-8') as f:
    registry = json.load(f)

# Pydantic schema for structured output
class RoutingDecision(BaseModel):
    selected_agent_id: str = Field(description="The ID of the agent chosen to handle the task.")
    selected_agent_url: str = Field(description="The URL of the chosen agent.")
    reasoning: str = Field(description="The reason why this agent was chosen.")

def route_request(user_instruction: str) -> RoutingDecision:
    """Uses LLM to decide which agent should handle the request."""
    print("[Reception] 思考路由去向中...")
    
    if not api_key or api_key == "your_google_api_key_here":
        print("[Reception] WARNING: GOOGLE_API_KEY 未設定，將強制使用 google_writer (Mock模式)。")
        return RoutingDecision(
            selected_agent_id="google_writer",
            selected_agent_url="http://127.0.0.1:8002/a2a/task",
            reasoning="Fallback mock mode."
        )

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
你是一個多代理系統的前台指揮官 (Router)。請根據使用者的需求，從以下註冊的 Agent 中挑選最適合處理該任務的 Agent。

可用 Agent 註冊表:
{json.dumps(registry, ensure_ascii=False, indent=2)}

使用者需求:
"{user_instruction}"

請嚴格依照 JSON schema 輸出你的決定。
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': RoutingDecision,
                'temperature': 0.1,
            },
        )
        
        decision_dict = json.loads(response.text)
        return RoutingDecision(**decision_dict)

    except Exception as e:
        print(f"[Reception] 發生錯誤: {e}")
        return None

def main():
    print("="*50)
    print(" A2A Protocol 前台中樞 (Reception Agent)")
    print("="*50)
    print("請輸入您的任務需求 (輸入 'q' 離開):")
    
    while True:
        try:
            instruction = input("\n> ")
            if instruction.lower() in ['q', 'quit', 'exit']:
                break
            
            if not instruction.strip():
                continue

            # 1. 決定路由
            decision = route_request(instruction)
            if not decision: continue
            
            print(f"\n[Reception] 決定交辦給: {decision.selected_agent_id}")
            print(f"[Reception] 理由: {decision.reasoning}")
            print(f"[Reception] 正在發送 A2A 請求至: {decision.selected_agent_url} ...\n")

            # 2. 構建 A2A 標準 Payload
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            payload = {
                "task_id": task_id,
                "instruction": instruction,
                "context": {
                    "source": "Reception"
                }
            }

            # 3. 發送 HTTP Request (Agent to Agent)
            try:
                response = requests.post(decision.selected_agent_url, json=payload, timeout=60)
                response.raise_for_status()
                
                a2a_response = response.json()
                print("="*50)
                print(f"[{decision.selected_agent_id} 的回覆]:")
                print(a2a_response.get("result", "無結果"))
                print("="*50)

            except requests.exceptions.ConnectionError:
                print(f"[Reception] 錯誤: 無法連線到 {decision.selected_agent_id}。請確保子服務已在相對應的埠口啟動！")
            except Exception as e:
                print(f"[Reception] A2A 通訊發生錯誤: {e}")

        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()
