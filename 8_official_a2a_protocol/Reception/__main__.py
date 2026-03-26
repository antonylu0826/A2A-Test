"""
Reception - A2A Protocol v1.0 Client / Orchestrator (Port 8000)

Acts as an A2A CLIENT that:
1. Discovers sub-agents by fetching their AgentCards (/.well-known/agent-card.json)
2. Uses Gemini to route and decompose user instructions into steps
3. Dispatches tasks to sub-agents via standard A2A message/send
4. Handles streaming responses (SSE) and push notifications

This replaces the custom REST bidding system with standard A2A discovery + routing.
"""

import asyncio
import os
import json
from pathlib import Path
from dotenv import load_dotenv

import httpx
from google import genai
from pydantic import BaseModel, Field

from a2a.client import A2AClient, A2ACardResolver
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendMessageRequest,
    Part,
    TextPart,
    Message,
)
import uuid

# Load environment variables
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Known sub-agent base URLs (Discovery via AgentCard)
KNOWN_AGENT_URLS = [
    "http://127.0.0.1:8001",  # ClaudeAgent
    "http://127.0.0.1:8002",  # GoogleAgent
    "http://127.0.0.1:8003",  # HumanAgent
]

# Keywords that trigger HumanAgent routing
HIGH_RISK_KEYWORDS = [
    "退款", "授權", "發布", "付款", "宣傳費", "廣告費", "核准", "批准",
    "refund", "authorize", "publish", "payment", "approve",
]

# Keywords that suggest analysis tasks -> ClaudeAgent
ANALYSIS_KEYWORDS = [
    "分析", "摘要", "整理", "提煉", "比較", "統計", "重點", "歸納",
    "analyze", "summary", "report", "extract", "compare",
]


# --- Routing Plan Schema for structured LLM output ---
class WorkflowStep(BaseModel):
    instruction: str = Field(description="交辦給代理的具體指示")


class WorkflowPlan(BaseModel):
    is_workflow: bool = Field(description="是否為需要多步驟接力的複雜任務")
    steps: list[WorkflowStep] = Field(description="依序執行的步驟清單")
    reasoning: str = Field(description="採用此路由策略的理由")


class Reception:
    """
    A2A Client orchestrator. Discovers agents and routes tasks using standard A2A protocol.
    """

    def __init__(self):
        self.discovered_agents: dict[str, AgentCard] = {}  # name -> AgentCard
        self.gemini_client = None
        if GOOGLE_API_KEY and GOOGLE_API_KEY != "your_google_api_key_here":
            self.gemini_client = genai.Client(api_key=GOOGLE_API_KEY)

    async def discover_agents(self, http_client: httpx.AsyncClient):
        """
        Discover sub-agents by fetching their AgentCards from /.well-known/agent-card.json.
        This is the standard A2A discovery mechanism.
        """
        print("\n[Reception] 🔍 正在掃描已知子代理的 AgentCard...")
        self.discovered_agents.clear()

        for base_url in KNOWN_AGENT_URLS:
            resolver = A2ACardResolver(httpx_client=http_client, base_url=base_url)
            try:
                card = await resolver.get_agent_card()
                self.discovered_agents[card.name] = card
                print(f"  ✅ 發現：{card.name} @ {card.url}")
                print(f"     技能：{[s.name for s in card.skills]}")
            except Exception as e:
                print(f"  ❌ 無法連線至 {base_url}：{e}")

        if not self.discovered_agents:
            print("[Reception] ⚠️  沒有找到任何在線代理！請先啟動子代理。")

    def _route_to_agent(self, instruction: str) -> AgentCard | None:
        """
        Simple keyword-based routing. In production this could use LLM-based routing.
        Priority: HumanAgent > ClaudeAgent (analysis) > GoogleAgent (creative) > any
        """
        lower = instruction.lower()

        # Priority 1: High risk -> HumanAgent
        if any(k in lower for k in HIGH_RISK_KEYWORDS):
            for card in self.discovered_agents.values():
                if "Human" in card.name:
                    return card

        # Priority 2: Analysis -> ClaudeAgent
        if any(k in lower for k in ANALYSIS_KEYWORDS):
            for card in self.discovered_agents.values():
                if "Claude" in card.name:
                    return card

        # Priority 3: Default -> GoogleAgent (creative)
        for card in self.discovered_agents.values():
            if "Google" in card.name:
                return card

        # Fallback: any available agent
        return next(iter(self.discovered_agents.values()), None)

    async def plan_workflow(self, instruction: str) -> WorkflowPlan:
        """Use Gemini to decompose complex instructions into workflow steps."""
        if not self.gemini_client:
            return WorkflowPlan(
                is_workflow=False,
                steps=[WorkflowStep(instruction=instruction)],
                reasoning="[Mock 模式] 未設定 GOOGLE_API_KEY，以單步驟處理。",
            )

        prompt = f"""
你是一個多代理系統的前台指揮官 (Router)。

請根據使用者的需求，判斷是否需要拆解為多個步驟。
- 如果任務很簡單，`is_workflow` 設為 false，`steps` 只有一步。
- 如果需要先分析資料再創作，則拆解為兩步。

【安全規則】：如果需求包含高風險操作（退款、授權、付款），請確保最後一步是獨立的人工審核步驟。

使用者需求："{instruction}"

請輸出 JSON 格式的工作流規劃。
"""
        try:
            response = self.gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": WorkflowPlan,
                    "temperature": 0.1,
                },
            )
            return WorkflowPlan(**json.loads(response.text))
        except Exception as e:
            print(f"[Reception] 路由規劃失敗，改用單步模式：{e}")
            return WorkflowPlan(
                is_workflow=False,
                steps=[WorkflowStep(instruction=instruction)],
                reasoning="路由規劃例外，降級為單步模式。",
            )

    async def dispatch_task(
        self,
        step_instruction: str,
        http_client: httpx.AsyncClient,
        context_id: str,
    ) -> str:
        """
        Dispatch a single step to the appropriate agent via standard A2A message/send.
        Returns the final result text.
        """
        target_card = self._route_to_agent(step_instruction)
        if not target_card:
            return "❌ 沒有可用的代理，無法執行此步驟。"

        print(f"\n[Reception] 📤 派發任務給：{target_card.name}")
        print(f"  指令：{step_instruction[:80]}...")

        # Use new ClientFactory avoiding deprecated A2AClient
        from a2a.client import ClientFactory, ClientConfig
        config = ClientConfig(streaming=True, httpx_client=http_client)
        client = ClientFactory(config).create(target_card)

        msg = Message(
            messageId=str(uuid.uuid4()),
            role="user",
            parts=[Part(root=TextPart(text=step_instruction))],
            contextId=context_id,
        )

        try:
            # Use streaming to receive progressive responses
            result_parts = []
            print(f"[Reception] ⏳ 等待 {target_card.name} 回應（SSE 串流中）...\n")
            
            from a2a.types import TaskArtifactUpdateEvent, TaskStatusUpdateEvent

            stream = client.send_message(msg)
            async for item in stream:
                if isinstance(item, tuple) and len(item) == 2:
                    task, update = item
                    if isinstance(update, TaskArtifactUpdateEvent):
                        for part in update.artifact.parts:
                            if hasattr(part.root, 'text'):
                                result_parts.append(part.root.text)
                                print(part.root.text, end="", flush=True)
                    elif isinstance(update, TaskStatusUpdateEvent):
                        state = update.status.state
                        if state == "input-required":
                            print("\n[Reception] 🔴 等待人工審核決定...")
                        elif state in ("completed", "failed", "canceled"):
                            print(f"\n[Reception] 📊 Task 狀態由代理更新：{state}")
                elif isinstance(item, Message):
                    # non-streaming fallback
                    for part in item.parts:
                        if hasattr(part.root, 'text'):
                            result_parts.append(part.root.text)
                            print(part.root.text, end="", flush=True)
            print("")
            if result_parts:
                return "".join(result_parts)
            return f"（{target_card.name} 已完成任務，無文字產出）"

        except Exception as e:
            print(f"\n[Reception] ❌ 通訊錯誤：{e}")
            return f"❌ 與 {target_card.name} 通訊失敗：{str(e)}"


async def main():
    reception = Reception()

    print("=" * 60)
    print("  A2A Protocol v1.0 前台中樞 (Official SDK)")
    print("=" * 60)

    # 關閉超時限制 (timeout=None)，以免等待 HumanAgent 人工審核時發生 Timeout Error
    async with httpx.AsyncClient(timeout=None) as http_client:
        # Initial agent discovery
        await reception.discover_agents(http_client)

        print("\n輸入任務需求 (輸入 'q' 離開, 'refresh' 重新掃描代理)：")

        while True:
            try:
                instruction = input("\n> ").strip()

                if instruction.lower() in ("q", "quit", "exit"):
                    print("[Reception] 再見！")
                    break

                if instruction.lower() == "refresh":
                    await reception.discover_agents(http_client)
                    continue

                if not instruction:
                    continue

                # Plan the workflow
                print("\n[Reception] 🧠 分析任務並規劃工作流...")
                plan = await reception.plan_workflow(instruction)
                print(f"[Reception] 規劃理由：{plan.reasoning}")
                print(f"[Reception] 步驟數：{len(plan.steps)}")

                context_id = str(uuid.uuid4())
                final_result = None

                for i, step in enumerate(plan.steps, 1):
                    print(f"\n{'='*50}")
                    print(f"  步驟 {i}/{len(plan.steps)}：{step.instruction[:60]}...")
                    print("=" * 50)

                    result = await reception.dispatch_task(
                        step.instruction,
                        http_client,
                        context_id,
                    )
                    final_result = result

                print(f"\n{'='*60}")
                print("[Reception] 🎯 任務執行完畢！最終結果：")
                print("=" * 60)
                if final_result:
                    print(final_result)
                print("=" * 60)

            except KeyboardInterrupt:
                print("\n[Reception] 使用者中斷，程式結束。")
                break


if __name__ == "__main__":
    asyncio.run(main())
