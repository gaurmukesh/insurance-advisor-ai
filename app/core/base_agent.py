import json
import time
from abc import ABC, abstractmethod
from typing import Any
import structlog
from pydantic import BaseModel
from app.core.llm import chat, chat_mini
from app.core.observability import get_langfuse

logger = structlog.get_logger("agent")


class AgentInput(BaseModel):
    pass


class AgentOutput(BaseModel):
    raw: str
    parsed: Any = None
    trace_id: str = ""


class BaseAgent(ABC):
    """
    Standard interface every Gen AI module inherits.

    Subclass provides:
      - system_prompt() -> str
      - build_prompt(input) -> str
      - _parse(raw) -> Any   [optional, default returns raw string]

    BaseAgent provides for free:
      - Correct LLM dispatch (GPT-4o vs mini)
      - LangFuse trace on every call
      - JSON parse with markdown fence stripping
    """

    trace_name: str = "base_agent"
    use_mini: bool = False  # set True in subclass for low-complexity tasks

    async def run(self, input: AgentInput) -> AgentOutput:
        langfuse = get_langfuse()
        trace = langfuse.trace(name=self.trace_name) if langfuse else None

        logger.info("agent_run_start", agent=self.trace_name)
        start = time.monotonic()

        system = self.system_prompt()
        prompt = self.build_prompt(input)

        fn = chat_mini if self.use_mini else chat
        raw = await fn(system, prompt, trace_name=self.trace_name)

        parsed = self._parse(raw)

        logger.info(
            "agent_run_complete",
            agent=self.trace_name,
            duration_ms=int((time.monotonic() - start) * 1000),
            langfuse_trace_id=trace.id if trace else None,
        )
        return AgentOutput(raw=raw, parsed=parsed, trace_id=trace.id if trace else "")

    @abstractmethod
    def system_prompt(self) -> str: ...

    @abstractmethod
    def build_prompt(self, input: AgentInput) -> str: ...

    def _parse(self, raw: str) -> Any:
        return raw

    def _parse_json(self, raw: str) -> Any:
        """Use this in _parse() when the agent returns JSON."""
        try:
            clean = (
                raw.strip()
                .removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            return json.loads(clean)
        except Exception:
            return raw
