from .runner import LLMRunner


class LlmAnalysisService:
    """Business layer for chat risk analysis and summarization."""

    def __init__(self, runner: LLMRunner) -> None:
        self.runner = runner

    async def analyze_message(
        self,
        message: str,
        context: list[str] | None = None,
    ) -> dict:
        """Analyze a single message with optional chat context."""
        prompt = self._build_message_prompt(message=message, context=context)
        raw = await self.runner.run(prompt)
        return self._to_structured_response(raw)

    async def analyze_conversation(self, messages: list[str]) -> dict:
        """Analyze a conversation for potential risk signals."""
        prompt = self._build_conversation_prompt(messages)
        raw = await self.runner.run(prompt)
        return self._to_structured_response(raw)

    async def generate_summary(self, messages: list[str]) -> str:
        """Generate a short summary from conversation messages."""
        prompt = self._build_summary_prompt(messages)
        raw = await self.runner.run(prompt)
        return self._to_structured_response(raw)["summary"]

    def _build_message_prompt(
        self,
        message: str,
        context: list[str] | None,
    ) -> str:
        context_block = ""
        if context:
            context_block = "Context messages:\n" + "\n".join(context) + "\n\n"

        return (
            f"{context_block}"
            "Analyze this message for potential risk signals "
            "(bullying, grooming, distress):\n\n"
            f'"{message}"'
        )

    def _build_conversation_prompt(self, messages: list[str]) -> str:
        numbered = "\n".join(f"{idx + 1}. {msg}" for idx, msg in enumerate(messages))
        return (
            "Analyze this conversation for risk signals "
            "(bullying, grooming, distress):\n\n"
            f"{numbered}"
        )

    def _build_summary_prompt(self, messages: list[str]) -> str:
        numbered = "\n".join(f"{idx + 1}. {msg}" for idx, msg in enumerate(messages))
        return (
            "Generate a concise summary of this conversation:\n\n"
            f"{numbered}"
        )

    def _to_structured_response(self, raw: dict) -> dict:
        risk_value = raw.get("severity", "low")
        if risk_value not in {"low", "medium", "high"}:
            risk_value = "low"

        severity_value = self._coerce_float(raw.get("confidence", 0.0))
        summary_value = str(raw.get("summary", ""))

        return {
            "risk": risk_value,
            "severity": severity_value,
            "summary": summary_value,
        }

    def _coerce_float(self, value: object) -> float:
        try:
            coerced = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(coerced, 1.0))
