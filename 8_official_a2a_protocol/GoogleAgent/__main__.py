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
    SecurityScheme,
    HTTPAuthSecurityScheme,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
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
        security_schemes={
            "bearer": SecurityScheme(
                root=HTTPAuthSecurityScheme(
                    scheme="bearer",
                    type="http",
                    description="存取此代理需要有效的 A2A_AUTH_TOKEN。",
                )
            )
        },
        security=[{"bearer": []}],
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """
    自定義身份驗證中間件，偵測 A2A_AUTH_TOKEN。
    """

    async def dispatch(self, request, call_next):
        # 排除 /.well-known/ 路由，以便公開讀取名片
        if request.url.path.startswith("/.well-known/"):
            return await call_next(request)

        expected_token = os.getenv("A2A_AUTH_TOKEN")
        if not expected_token:
            # 如果伺服器端沒設定，則暫不強制攔截（開發安全性）
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"error": "Unauthorized: Missing or invalid Authorization header"},
                status_code=401,
            )

        token = auth_header.split(" ")[1]
        if token != expected_token:
            return JSONResponse(
                {"error": "Unauthorized: Invalid A2A_AUTH_TOKEN"},
                status_code=401,
            )

        return await call_next(request)


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

    # 注入身份驗證中間件
    app = app.build()
    app.add_middleware(AuthMiddleware)

    print("=" * 55)
    print(f"  [GoogleAgent] A2A v1.0 Server 啟動中...")
    print(f"  AgentCard: http://{HOST}:{PORT}/.well-known/agent-card.json")
    print(f"  A2A Endpoint: http://{HOST}:{PORT}/")
    print("=" * 55)

    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
