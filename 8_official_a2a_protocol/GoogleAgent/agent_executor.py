"""
GoogleAgent - AgentExecutor
Handles A2A message/send and message/stream requests.
Uses Google Gemini API with SSE streaming support.
"""

import os

from google import genai
from google.genai import types as genai_types

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from a2a.types import (
    TaskArtifactUpdateEvent,
    TaskStatus,
    TaskStatusUpdateEvent,
    Part,
    TextPart,
    Artifact,
)


class GoogleAgentExecutor(AgentExecutor):
    """
    A2A-compliant AgentExecutor for the Google Creative Agent.

    Implements both synchronous (message/send) and streaming (message/stream)
    request handling via the EventQueue pattern.
    Uses Gemini's streaming API to progressively emit content.
    """

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key or api_key == "your_google_api_key_here":
            print("[GoogleAgent] ⚠️  GOOGLE_API_KEY 未設定，將使用 Mock 模式。")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)

    def _extract_text(self, context: RequestContext) -> str:
        """Extract plain text instruction from the A2A RequestContext."""
        try:
            for part in context.message.parts:
                if hasattr(part.root, 'text'):
                    return part.root.text
        except Exception:
            pass
        return "（無法解析訊息內容）"

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Handle both message/send and message/stream requests.
        Uses Gemini streaming API to progressively push TaskArtifactUpdateEvents.
        """
        instruction = self._extract_text(context)
        print(f"\n[GoogleAgent] ▶ 收到任務: {instruction[:80]}...")

        # Signal that we are now working on this task
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                status=TaskStatus(state="working"),
                final=False,
                task_id=context.task_id,
                context_id=context.context_id,
            )
        )

        if self.client is None:
            # Mock mode
            mock_response = (
                f"[Mock 模式] GoogleAgent 收到指令：「{instruction}」\n"
                "由於 GOOGLE_API_KEY 未設定，此為模擬回應。"
            )
            await event_queue.enqueue_event(new_agent_text_message(mock_response, context_id=context.context_id, task_id=context.task_id))
            return

        try:
            # Use Gemini async streaming to progressively emit creative content
            full_text = ""
            response = await self.client.aio.models.generate_content_stream(
                model="gemini-2.0-flash",
                contents=instruction,
                config=genai_types.GenerateContentConfig(
                    system_instruction=(
                        "你是一個擅長創意寫作的 Agent。"
                        "你的任務是依照指令創作出高品質的文字內容，"
                        "包括文章、故事、文案或其他創意文字。"
                        "請用繁體中文回答，風格生動有趣。"
                    ),
                    temperature=0.8,
                    max_output_tokens=1500,
                ),
            )

            async for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    # Stream incremental artifact updates to the client
                    await event_queue.enqueue_event(
                        TaskArtifactUpdateEvent(
                            append=True,
                            artifact=Artifact(
                                artifact_id="creative-content",
                                name="創意內容",
                                parts=[Part(root=TextPart(text=chunk.text))],
                            ),
                            task_id=context.task_id,
                            context_id=context.context_id,
                        )
                    )

            print(f"[GoogleAgent] ✅ 任務完成，共產生 {len(full_text)} 字。")

            # Final status update
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    status=TaskStatus(state="completed"),
                    final=True,
                    task_id=context.task_id,
                    context_id=context.context_id,
                )
            )

        except Exception as e:
            print(f"[GoogleAgent] ❌ Gemini API 錯誤: {e}")
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    status=TaskStatus(
                        state="failed",
                        message=new_agent_text_message(f"API 錯誤：{str(e)}")
                    ),
                    final=True,
                    task_id=context.task_id,
                    context_id=context.context_id,
                )
            )

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Handle task cancellation."""
        print(f"[GoogleAgent] 🛑 收到取消請求 Task ID: {context.task_id}")
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                status=TaskStatus(state="canceled"),
                final=True,
                task_id=context.task_id,
                context_id=context.context_id,
            )
        )
