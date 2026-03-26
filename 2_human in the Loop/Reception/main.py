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
class WorkflowStep(BaseModel):
    agent_id: str = Field(description="負責此步驟的 Agent ID。")
    instruction: str = Field(description="交辦給該 Agent 的具體指示。")

class WorkflowPlan(BaseModel):
    is_workflow: bool = Field(description="此任務是否複雜到需要多個步驟接力完成？")
    steps: list[WorkflowStep] = Field(description="依序執行的步驟清單。")
    reasoning: str = Field(description="採用此拆解與路由策略的理由。")

def route_request(user_instruction: str) -> WorkflowPlan:
    """Uses LLM to decide the workflow and route the request."""
    print("[Reception] 思考路由與工作流結構中...")
    
    if not api_key or api_key == "your_google_api_key_here":
        print("[Reception] WARNING: GOOGLE_API_KEY 未設定，將強制使用 google_writer (Mock模式)。")
        return WorkflowPlan(
            is_workflow=False,
            steps=[WorkflowStep(agent_id="google_writer", instruction=user_instruction)],
            reasoning="Fallback mock mode."
        )

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
你是一個多代理系統的前台指揮官 (Router)。請根據使用者的需求，決定是否要將任務拆解為多個步驟 (Workflow)，並從以下註冊的 Agent 中挑選最適合處理該步驟的 Agent。
如果任務很簡單（例如只要求查詢或只要求寫作），`is_workflow` 設為 false，`steps` 只有一步。
如果任務很複雜（例如要求先尋找資料、再整理、最後寫成文章），則將它拆解成多個步驟，`is_workflow` 設為 true，並在 `steps` 依序列出。
例如：第一步交給 claude_analyst 分析資料，第二步交給 google_writer 負責產出最終文章。請精準給出給各個 Agent 的具體 instruction。

【安全與授權規則】：
如果使用者的需求包含對外的行動或是高風險操作（例如發文、寄送、退款），請確保在你的 Workflow 的**最後一個步驟**加上 `human_reviewer` 來把關，並在 instruction 中說明需要授權什麼項目。

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
                'response_schema': WorkflowPlan,
                'temperature': 0.1,
            },
        )
        
        decision_dict = json.loads(response.text)
        return WorkflowPlan(**decision_dict)

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

            # 1. 決定工作流
            plan = route_request(instruction)
            if not plan: continue
            
            print(f"\n[Reception] 規劃理由: {plan.reasoning}")
            print(f"[Reception] 是否為多步工作流: {plan.is_workflow}")
            
            # 2. 依序執行步驟
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            accumulated_context = {
                "source": "Reception",
                "original_instruction": instruction
            }
            
            final_result = None

            for i, step in enumerate(plan.steps):
                print(f"\n>>> 執行步驟 {i+1}/{len(plan.steps)}: 交辦給 {step.agent_id} ...")
                
                # 從 registry 取出對應 URL
                agent_info = next((a for a in registry.get("agents", []) if a["id"] == step.agent_id), None)
                if not agent_info:
                    print(f"[Reception] 錯誤: 找不到 Agent '{step.agent_id}' 在註冊表中。")
                    break
                
                agent_url = agent_info["url"]
                
                payload = {
                    "task_id": task_id,
                    "instruction": step.instruction,
                    "context": accumulated_context
                }

                try:
                    response = requests.post(agent_url, json=payload, timeout=300)
                    response.raise_for_status()
                    
                    a2a_response = response.json()
                    step_result = a2a_response.get("result", "無結果")
                    print(f"[{step.agent_id} 的回覆]:\n{step_result}\n")
                    
                    # 將目前步驟的結果放入 context 給下一步使用
                    accumulated_context[f"step_{i+1}_{step.agent_id}_result"] = step_result
                    final_result = step_result

                except requests.exceptions.ConnectionError:
                    print(f"[Reception] 錯誤: 無法連線到 {step.agent_id} ({agent_url})。請確保子服務已在相對應的埠口啟動！")
                    break
                except Exception as e:
                    print(f"[Reception] A2A 通訊發生錯誤: {e}")
                    break

            print("="*50)
            print("[Reception] 任務執行結束。最終結果：")
            print(final_result)
            print("="*50)

        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()
