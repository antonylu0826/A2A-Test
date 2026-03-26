"""
HumanAgent - A2A Protocol v1.0 Compliant Agent
Role: Human Decision Gate (Port 8003)

This agent is the safety fuse of the system. When a task involves
high-risk operations (payments, publishing, authorizations), it
uses the 'input-required' task state to halt automation and
wait for a human to confirm via terminal.
"""

import sys
import os
from pathlib import Path

# Ensure this agent's directory is on sys.path so agent_executor can be imported
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
import uvicorn

from agent_executor import HumanAgentExecutor

# Load environment variables
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

HOST = "127.0.0.1"
PORT = 8003


def build_agent_card() -> AgentCard:
    """Build the AgentCard for the Human Gate agent."""
    skill = AgentSkill(
        id="human-approval",
        name="人類授權審核",
        description=(
            "作為系統的安全閘門，負責攔截所有高風險操作（例如付款、授權、對外發布、退款）。"
            "收到任務後會發出 input-required 狀態，等待人類主管在終端機確認後再繼續。"
        ),
        tags=["human", "approval", "authorization", "security", "review", "payment", "refund"],
        examples=[
            "請授權這筆 $300 的廣告費用",
            "確認是否要發布這篇文章",
            "審核退款申請",
        ],
        input_modes=["text/plain"],
        output_modes=["text/plain"],
    )

    return AgentCard(
        name="Human Decision Gate",
        description="系統安全核保閘門 - 攔截高敏感操作並等待人類主管確認，實作 A2A input-required 機制。",
        url=f"http://{HOST}:{PORT}/",
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(
            streaming=False,
            push_notifications=True,
        ),
        skills=[skill],
    )


def main():
    agent_card = build_agent_card()

    request_handler = DefaultRequestHandler(
        agent_executor=HumanAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    print("=" * 55)
    print(f"  [HumanAgent] A2A v1.0 安全閘門啟動中...")
    print(f"  AgentCard: http://{HOST}:{PORT}/.well-known/agent-card.json")
    print(f"  A2A Endpoint: http://{HOST}:{PORT}/")
    print("  ⚠️  此代理會在偵測到高敏感操作時要求人工確認")
    print("=" * 55)

    uvicorn.run(app.build(), host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
