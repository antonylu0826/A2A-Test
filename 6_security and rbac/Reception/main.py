import json
import os
import requests
import uuid
import threading
import time
import uvicorn
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field
from fastapi import FastAPI, Depends, Header, HTTPException
import jwt
import datetime

# --- 環境變數與設定 ---
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)
api_key = os.getenv("GOOGLE_API_KEY")
A2A_SHARED_SECRET = os.getenv("A2A_SHARED_SECRET", "super_secret_token_123")

# --- 動態註冊機制 (Dynamic Registry) ---
# 用於儲存在線 Agent 的記憶體清單
online_agents_registry = []

# --- 共享狀態記憶體 (Shared Semantic Memory) ---
# session_id -> { "original_instruction": "...", "history": [] }
shared_memory_store = {}

# --- 非同步處理 Callback (Webhooks) ---
task_callbacks = {} # task_id -> {"event": threading.Event(), "result": None}

app = FastAPI(title="Reception Dynamic Registry", description="A2A 前台大腦的註冊端點")

# ---------- JWT 驗證與簽發區塊 ----------
def create_a2a_token(session_id: str) -> str:
    """產生一張時效 24 小時的 JWT 憑證，這張憑證可用於互相溝通"""
    payload = {
        "role": "reception",
        "session_id": session_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, A2A_SHARED_SECRET, algorithm="HS256")

def verify_token(authorization: str = Header(default=None)):
    """攔截器：驗證傳入的 HTTP Header 中是否帶有合法的 Bearer Token"""
    if not authorization:
        print("[Reception 警衛] 🛑 攔截到未帶通行證的惡意請求！")
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            print("[Reception 警衛] 🛑 攔截到通行證格式錯誤的請求！")
            raise HTTPException(status_code=401, detail="Invalid Authentication Scheme")
        
        # 解碼驗證 JWT
        payload = jwt.decode(token, A2A_SHARED_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        print("[Reception 警衛] 🛑 攔截到過期的通行證！")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        print(f"[Reception 警衛] 🛑 攔截到無效的通行證：{e}")
        raise HTTPException(status_code=401, detail=f"Invalid Token: {str(e)}")
    except ValueError:
        print("[Reception 警衛] 🛑 攔截到異常的 Headers！")
        raise HTTPException(status_code=401, detail="Invalid Authorization Header Format")

class AgentRegistration(BaseModel):
    id: str
    name: str
    url: str
    capabilities: list[str]
    description: str

@app.post("/a2a/register")
def register_agent(agent: AgentRegistration):
    # 檢查是否已存在，若是則更新，否則加入
    existing = next((a for a in online_agents_registry if a["id"] == agent.id), None)
    if existing:
        online_agents_registry.remove(existing)
    
    online_agents_registry.append(agent.model_dump())
    print(f"\n[Reception 總機] 🎉 新夥伴加入/更新：{agent.name} ({agent.id})")
    return {"status": "registered", "agent_id": agent.id}

class AgentDeregistration(BaseModel):
    id: str

@app.post("/a2a/deregister")
def deregister_agent(agent: AgentDeregistration):
    # 尋找並移除
    existing = next((a for a in online_agents_registry if a["id"] == agent.id), None)
    if existing:
        online_agents_registry.remove(existing)
        print(f"\n[Reception 總機] 👋 夥伴已離線/註銷：({agent.id})")
        return {"status": "deregistered"}
    return {"status": "not_found"}

@app.get("/a2a/memory/{session_id}")
def get_memory(session_id: str, token_payload: dict = Depends(verify_token)):
    """供子 Agent 呼叫，取得該對話目前的共享記憶"""
    if session_id not in shared_memory_store:
        raise HTTPException(status_code=404, detail="Session not found")
    return shared_memory_store[session_id]

class MemoryAppend(BaseModel):
    source: str
    content: str

@app.post("/a2a/memory/{session_id}")
def append_memory(session_id: str, data: MemoryAppend, token_payload: dict = Depends(verify_token)):
    """供 Reception 或子 Agent 呼叫，用來追加執行結果進這塊公佈欄"""
    if session_id not in shared_memory_store:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")
    
    shared_memory_store[session_id]["history"].append({
        "source": data.source,
        "content": data.content
    })
    
    # 紀錄異動訊息到終端機
    print(f"\n[Reception 記憶庫] 📝 收到來自 [{data.source}] 的狀態更新！(紀錄長度約 {len(data.content)} 字)")
    print("> ", end="", flush=True)  # 重新印出提示字元
    
    return {"status": "success"}

class CallbackPayload(BaseModel):
    status: str
    result: str

@app.post("/a2a/callback/{task_id}")
def receive_callback(task_id: str, payload: CallbackPayload, token_payload: dict = Depends(verify_token)):
    """接聽各個子 Agent 處理完畢打回來的結果通報"""
    if task_id in task_callbacks:
        task_callbacks[task_id]["result"] = payload.result
        # 觸發 Event，喚醒主執行緒繼續往下跑
        task_callbacks[task_id]["event"].set()
        return {"status": "acknowledged"}
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Task not found or already processed")

def run_server():
    """在背景執行 FastAPI 伺服器，讓子 Agent 可以發送 POST 註冊自己"""
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

def health_check_loop():
    """定期巡邏，如果發現 Agent 的視窗被暴力關閉導致無法連線，將其強制剔除。"""
    while True:
        time.sleep(10)  # 每 10 秒檢查一次
        # 複製一份名單來迭代，避免修改導致錯誤
        for agent in list(online_agents_registry):
            try:
                # 嘗試發送一個輕量的 GET 請求 (即使回應 405 Method Not Allowed 也代表伺服器還活著)
                requests.get(agent["url"], timeout=1)
            except requests.exceptions.ConnectionError:
                # 如果連線被拒，代表終端機已經被直接關閉 (進程死亡)
                if agent in online_agents_registry:
                    online_agents_registry.remove(agent)
                    print(f"\n[Reception 總機] 💔 偵測到夥伴無預警斷線，已剔除：({agent['id']})")
                    print("\n> ", end="", flush=True) # 重新印出提示字元
            except Exception:
                pass

# --- A2A 智能路由與工作流 (Router & Workflow) ---
class WorkflowStep(BaseModel):
    agent_id: str = Field(description="負責此步驟的 Agent ID。")
    instruction: str = Field(description="交辦給該 Agent 的具體指示。")

class WorkflowPlan(BaseModel):
    is_workflow: bool = Field(description="此任務是否複雜到需要多個步驟接力完成？")
    steps: list[WorkflowStep] = Field(description="依序執行的步驟清單。")
    reasoning: str = Field(description="採用此拆解與路由策略的理由。")

def get_online_agents() -> list[dict]:
    """取得目前線上活躍的 Agent 清單 (模擬 MCP Tool 提供內容)"""
    return online_agents_registry

def route_request(user_instruction: str) -> WorkflowPlan:
    print("[Reception] 查詢目前線上兵力，並思考路由與工作流結構中...")
    
    current_agents = get_online_agents()
    if not current_agents:
        print("[Reception] ⚠️ 警告：目前沒有任何線上 Agent，我無法分派任何任務！請先啟動其它子 Agent。")
        return None

    if not api_key or api_key == "your_google_api_key_here":
        print("[Reception] WARNING: GOOGLE_API_KEY 未設定，將強制使用 google_writer (Mock模式)。")
        return WorkflowPlan(
            is_workflow=False,
            steps=[WorkflowStep(agent_id="google_writer", instruction=user_instruction)],
            reasoning="Fallback mock mode."
        )

    try:
        client = genai.Client(api_key=api_key)
        
        # 為了保持結構化輸出的穩定性，我們將結果 (get_online_agents) 動態注入 Prompt 中
        prompt = f"""
你是一個多代理系統的前台指揮官 (Router)。請根據使用者的需求，決定是否要將任務拆解為多個步驟 (Workflow)，並從以下動態註冊的有效 Agent 中挑選最適合的人選。
如果任務很簡單（例如只要求查詢或只要求寫作），`is_workflow` 設為 false，`steps` 只有一步。
如果任務很複雜（例如要求先尋找資料、再整理、最後寫成文章），則將它拆解成多個步驟，`is_workflow` 設為 true，並在 `steps` 依序列出。
例如：第一步交給 claude_analyst 分析資料，第二步交給 google_writer 負責產出最終文章。請精準給出給各個 Agent 的具體 instruction。

【安全與授權規則】：
如果使用者的需求包含對外的行動或是高風險操作（例如發布、寄送、退款），請確保在你的 Workflow 的**最後一個步驟**加上 `human_reviewer` 來把關，並在 instruction 中說明需要授權什麼項目。

可用且目前「在線」的 Agent 註冊表:
{json.dumps(current_agents, ensure_ascii=False, indent=2)}

使用者需求:
"{user_instruction}"

請盡可能只調用「在線」的 Agent。並嚴格依照 JSON schema 輸出你的決定。
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
    # 啟動背景註冊伺服器
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # 啟動健康狀態巡邏 (Heartbeat)
    health_thread = threading.Thread(target=health_check_loop, daemon=True)
    health_thread.start()

    print("="*50)
    print(" A2A Protocol 前台中樞 (Dynamic Registry Enabled)")
    print("背景註冊伺服器已在 port 8000 啟動，等待子 Agent 報到中...")
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
            session_id = f"sess_{uuid.uuid4().hex[:8]}"
            
            # 初始化共享記憶體
            shared_memory_store[session_id] = {
                "original_instruction": instruction,
                "history": []
            }
            
            # 建立 memory endpoint 的 URL (供本地子 Agent 存取)
            memory_endpoint = f"http://127.0.0.1:8000/a2a/memory/{session_id}"
            
            final_result = None

            for i, step in enumerate(plan.steps):
                print(f"\n>>> 執行步驟 {i+1}/{len(plan.steps)}: 交辦給 {step.agent_id} ...")
                
                # 從記憶體的 registry 取出對應 URL
                agent_info = next((a for a in online_agents_registry if a["id"] == step.agent_id), None)
                if not agent_info:
                    print(f"[Reception] 錯誤: 找不到 Agent '{step.agent_id}' 在目前的線上名單中。")
                    break
                
                agent_url = agent_info["url"]
                
                # 全新極簡 Webhook Payload
                webhook_url = f"http://127.0.0.1:8000/a2a/callback/{task_id}"
                payload = {
                    "task_id": task_id,
                    "session_id": session_id,
                    "memory_endpoint": memory_endpoint,
                    "webhook_url": webhook_url,
                    "instruction": step.instruction
                }

                # 準備接收 callback 的等候 Event
                task_event = threading.Event()
                task_callbacks[task_id] = {
                    "event": task_event,
                    "result": None
                }

                try:
                    # 發配邊疆前，蓋上通行證章
                    a2a_token = create_a2a_token(session_id)
                    headers = {
                        "Authorization": f"Bearer {a2a_token}",
                        "Content-Type": "application/json"
                    }

                    # 這裡將不會卡死！子 Agent 會立刻回覆 HTTP 202 (status: processing)
                    response = requests.post(agent_url, json=payload, headers=headers, timeout=5)
                    response.raise_for_status()
                    
                    a2a_response = response.json()
                    print(f"[{step.agent_id} 初步回覆]: {a2a_response.get('status')}")
                    print("[Reception] ⏳ 主流程進入等候狀態可以去喝杯咖啡，等待 Agent 背景完工通報...\n")
                    
                    # 主迴圈在此卡住，釋放了 HTTP connections 的壓力
                    task_event.wait()
                    
                    # 等 task_event.set() 被呼叫後才會醒來走到這裡
                    step_result = task_callbacks[task_id]["result"]
                    print(f"[{step.agent_id} 背景完工回報結果]:\n{step_result}\n")
                    
                    # 將目前步驟的結果發佈到中央記憶體中，讓下一個人去拿
                    requests.post(memory_endpoint, json={
                        "source": step.agent_id,
                        "content": step_result
                    }, headers=headers, timeout=5)
                    
                    # 任務結束，清理 callback store
                    del task_callbacks[task_id]
                    
                    final_result = step_result

                except requests.exceptions.ConnectionError:
                    print(f"[Reception] 錯誤: 無法連線到 {step.agent_id} ({agent_url})。請確保子服務已啟動！")
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
