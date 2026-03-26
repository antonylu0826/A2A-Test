"""
GoogleAgent - A2A Protocol v1.0 Compliant Agent
Role: Creative Writing & Content Generation Specialist (Port 8002)
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

from agent_executor import GoogleAgentExecutor

# Load environment variables
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

HOST = "127.0.0.1"
PORT = 8002


def build_agent_card() -> AgentCard:
    """Build the AgentCard - the public description of this A2A agent."""
    skill = AgentSkill(
        id="creative-writing",
        name="創意寫作與內容生成",
        description=(
            "擅長原創文字創作、故事發想、行銷文案與各類內容生成。"
            "適合處理需要創意、敘事力或文字美感的任務。"
        ),
        tags=["writing", "creative", "content", "story", "marketing", "article"],
        examples=[
            "請幫我寫一篇關於 AI 趨勢的科技文章",
            "寫一個關於太空探索的短故事",
            "幫我撰寫產品的行銷文案",
        ],
        input_modes=["text/plain"],
        output_modes=["text/plain"],
    )

    return AgentCard(
        name="Google Creative Agent",
        description="專精創意寫作與內容生成的 A2A 代理，背後由 Gemini (Google) 驅動。",
        url=f"http://{HOST}:{PORT}/",
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(
            streaming=True,
            push_notifications=True,
        ),
        skills=[skill],
    )


def main():
    agent_card = build_agent_card()

    request_handler = DefaultRequestHandler(
        agent_executor=GoogleAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    print("=" * 55)
    print(f"  [GoogleAgent] A2A v1.0 Server 啟動中...")
    print(f"  AgentCard: http://{HOST}:{PORT}/.well-known/agent-card.json")
    print(f"  A2A Endpoint: http://{HOST}:{PORT}/")
    print("=" * 55)

    uvicorn.run(app.build(), host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
