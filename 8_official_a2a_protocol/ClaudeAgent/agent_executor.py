"""
ClaudeAgent - AgentExecutor
Handles A2A message/send and message/stream requests.
Uses Anthropic Claude API with SSE streaming support.
"""

import os
import asyncio
from typing import AsyncIterable

import anthropic

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from a2a.types import (
    TaskArtifactUpdateEvent,
    TaskStatus,
    TaskStatusUpdateEvent,
    UnsupportedOperationError,
    Part,
    TextPart,
    Artifact,
)


# High-sensitivity keywords that should be escalated to HumanAgent
SENSITIVE_KEYWORDS = ["退款", "授權", "發布", "付款", "refund", "authorize", "publish", "payment"]


class ClaudeAgentExecutor(AgentExecutor):
    """
    A2A-compliant AgentExecutor for the Claude Analysis Agent.

    Implements both synchronous (message/send) and streaming (message/stream)
    request handling via the EventQueue pattern.
    """

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key or api_key == "your_anthropic_api_key_here":
            print("[ClaudeAgent] ⚠️  ANTHROPIC_API_KEY 未設定，將使用 Mock 模式。")
            self.client = None
        else:
            self.client = anthropic.AsyncAnthropic(api_key=api_key)

    def _extract_text(self, context: RequestContext) -> str:
        """Extract plain text instruction from the A2A RequestContext."""
        try:
            for part in context.message.parts:
                if hasattr(part.root, "text"):
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
        Uses streaming Anthropic API to progressively push TaskArtifactUpdateEvents.
        """
        instruction = self._extract_text(context)
        print(f"\n[ClaudeAgent] ▶ 收到任務: {instruction[:80]}...")

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
            # Mock mode - return a placeholder response
            mock_response = (
                f"[Mock 模式] ClaudeAgent 收到指令：「{instruction}」\n"
                "由於 ANTHROPIC_API_KEY 未設定，此為模擬回應。"
            )
            await event_queue.enqueue_event(
                new_agent_text_message(
                    mock_response, context_id=context.context_id, task_id=context.task_id
                )
            )
            return

        try:
            # Use streaming API for SSE support
            full_text = ""
            async with self.client.messages.stream(
                model="claude-3-haiku-20240307",
                max_tokens=1500,
                temperature=0.2,
                system=(
                    "你是一個專業的資料分析 Agent。"
                    "你的任務是精確地依照指令分析提供的內容，並摘要出重點。"
                    "請用繁體中文回答，回答要清晰、有條理。"
                ),
                messages=[{"role": "user", "content": instruction}],
            ) as stream:
                async for text_chunk in stream.text_stream:
                    full_text += text_chunk
                    # Stream incremental artifact updates to the client
                    await event_queue.enqueue_event(
                        TaskArtifactUpdateEvent(
                            append=True,
                            artifact=Artifact(
                                artifact_id="analysis-result",
                                name="分析結果",
                                parts=[Part(root=TextPart(text=text_chunk))],
                            ),
                            task_id=context.task_id,
                            context_id=context.context_id,
                        )
                    )

            print(f"[ClaudeAgent] ✅ 任務完成，共產生 {len(full_text)} 字。")

            # Final status update - mark task as completed
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    status=TaskStatus(state="completed"),
                    final=True,
                    task_id=context.task_id,
                    context_id=context.context_id,
                )
            )

        except anthropic.APIError as e:
            print(f"[ClaudeAgent] ❌ Anthropic API 錯誤: {e}")
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
        """Handle task cancellation requests."""
        print(f"[ClaudeAgent] 🛑 收到取消請求 Task ID: {context.task_id}")
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                status=TaskStatus(state="canceled"),
                final=True,
                task_id=context.task_id,
                context_id=context.context_id,
            )
        )
