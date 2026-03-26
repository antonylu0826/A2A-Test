"""
HumanAgent - AgentExecutor
Implements the Human-in-the-Loop gate using A2A's official 'input-required' task state.

When a high-risk operation is detected, the Task is set to 'input-required',
halting all automated processing until a human confirms via the terminal.
"""

import asyncio
import threading

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from a2a.types import (
    TaskStatus,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    Part,
    TextPart,
    Artifact,
    Message,
)

# High-risk keywords that trigger human review
HIGH_RISK_KEYWORDS = [
    "退款", "授權", "發布", "付款", "宣傳費", "廣告費", "核准", "批准",
    "refund", "authorize", "publish", "payment", "approve", "confirm",
]


class HumanAgentExecutor(AgentExecutor):
    """
    A2A-compliant AgentExecutor for the Human Decision Gate.

    Uses the official A2A 'input-required' task state to pause automation
    and wait for human confirmation via the terminal.
    """

    def _extract_text(self, context: RequestContext) -> str:
        """Extract plain text instruction from the A2A RequestContext."""
        try:
            for part in context.message.parts:
                if hasattr(part.root, 'text'):
                    return part.root.text
        except Exception:
            pass
        return "（無法解析訊息內容）"

    def _is_high_risk(self, instruction: str) -> bool:
        """Detect if the instruction involves a high-risk operation."""
        lower_instruction = instruction.lower()
        return any(keyword in lower_instruction for keyword in HIGH_RISK_KEYWORDS)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Handle the task. If high-risk, set to 'input-required' and wait for
        human confirmation. Then complete or fail based on human decision.
        """
        instruction = self._extract_text(context)
        print(f"\n[HumanAgent] ⚠️  收到需審查的任務: {instruction[:100]}")

        # Step 1: Signal 'input-required' - this is the core A2A HiTL mechanism
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                status=TaskStatus(
                    state="input-required",
                    message=Message(
                        messageId="human-review-request",
                        role="agent",
                        parts=[Part(root=TextPart(
                            text=(
                                f"🔴 高風險操作攔截！\n"
                                f"任務內容：「{instruction}」\n\n"
                                "此操作需要人類主管授權，已暫停自動化流程。"
                            )
                        ))],
                    ),
                ),
                final=False,
                task_id=context.task_id,
                context_id=context.context_id,
            )
        )

        # Step 2: Block and wait for human input in a background thread
        print("\n" + "=" * 60)
        print("🚨 [HumanAgent 安全閘] 偵測到高敏感操作，需要人工審核！")
        print(f"   任務：{instruction}")
        print("=" * 60)

        # Use a threading Event to bridge sync terminal input with async
        approval_event = threading.Event()
        human_decision = {"approved": False, "reason": ""}

        def wait_for_human_input():
            while True:
                try:
                    response = input("\n請輸入決定 [approve/deny]: ").strip().lower()
                    if response in ("approve", "a", "yes", "y", "批准", "授權"):
                        human_decision["approved"] = True
                        human_decision["reason"] = "人工主管已批准此操作。"
                        break
                    elif response in ("deny", "d", "no", "n", "拒絕", "否"):
                        human_decision["approved"] = False
                        human_decision["reason"] = "人工主管已拒絕此操作。"
                        break
                    else:
                        print("請輸入 'approve' (批准) 或 'deny' (拒絕)")
                except (EOFError, KeyboardInterrupt):
                    human_decision["approved"] = False
                    human_decision["reason"] = "輸入中斷，自動拒絕。"
                    break
            approval_event.set()

        # Run terminal input in a separate thread to avoid blocking the event loop
        input_thread = threading.Thread(target=wait_for_human_input, daemon=True)
        input_thread.start()

        # Await the human decision without blocking the event loop
        await asyncio.get_event_loop().run_in_executor(None, approval_event.wait)

        # Step 3: Process the human's decision
        if human_decision["approved"]:
            print(f"\n[HumanAgent] ✅ 已批准。理由：{human_decision['reason']}")
            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    append=False,
                    artifact=Artifact(
                        artifact_id="human-decision",
                        name="人工審核結果",
                        parts=[Part(root=TextPart(
                            text=f"✅ 已獲授權：{human_decision['reason']}"
                        ))],
                    ),
                    task_id=context.task_id,
                    context_id=context.context_id,
                )
            )
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    status=TaskStatus(state="completed"),
                    final=True,
                    task_id=context.task_id,
                    context_id=context.context_id,
                )
            )
        else:
            print(f"\n[HumanAgent] ❌ 已拒絕。理由：{human_decision['reason']}")
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    status=TaskStatus(
                        state="failed",
                        message=Message(
                            messageId="human-denial",
                            role="agent",
                            parts=[Part(root=TextPart(
                                text=f"❌ 操作被拒絕：{human_decision['reason']}"
                            ))],
                        ),
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
        """Handle cancellation of pending human review."""
        print(f"[HumanAgent] 🛑 審核流程取消 Task ID: {context.task_id}")
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                status=TaskStatus(state="canceled"),
                final=True,
                task_id=context.task_id,
                context_id=context.context_id,
            )
        )
