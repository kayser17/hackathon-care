import asyncio
import logging
import os

logger = logging.getLogger("care.runner")

# OpenAI-compatible settings (take priority when CARE_API_KEY is set)
CARE_API_KEY = os.getenv("CARE_API_KEY", "")
CARE_API_URL_LLM = os.getenv("CARE_API_URL_LLM", "https://api.openai.com/v1")
CARE_MODEL_LLM = os.getenv("CARE_MODEL_LLM", "gpt-4o-mini")

# Bedrock settings (used when CARE_API_KEY is empty)
MODEL_ID = os.getenv("MODEL_ID", "eu.anthropic.claude-sonnet-4-6")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-central-1")

_USE_OPENAI = bool(CARE_API_KEY)


class LLMRunner:
    """Low-level execution layer for LLM requests.

    When CARE_API_KEY is set, uses the OpenAI-compatible API.
    Otherwise falls back to AWS Bedrock.
    """

    def __init__(self) -> None:
        if _USE_OPENAI:
            import openai
            self._openai = openai.OpenAI(api_key=CARE_API_KEY, base_url=CARE_API_URL_LLM)
            logger.info("LLMRunner: using OpenAI-compatible API (%s, model=%s)", CARE_API_URL_LLM, CARE_MODEL_LLM)
        else:
            import boto3
            self._bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
            logger.info("LLMRunner: using AWS Bedrock (region=%s, model=%s)", AWS_REGION, MODEL_ID)

    async def run(self, prompt: str) -> dict:
        if _USE_OPENAI:
            return await self._run_openai(prompt)
        return await self._run_bedrock(prompt)

    async def _run_openai(self, prompt: str) -> dict:
        try:
            response = await asyncio.to_thread(
                self._openai.chat.completions.create,
                model=CARE_MODEL_LLM,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.2,
            )
            text = response.choices[0].message.content or ""
        except Exception as exc:
            return {"raw": f"Error: {exc}"}
        return {"raw": text}

    async def _run_bedrock(self, prompt: str) -> dict:
        from botocore.exceptions import ClientError

        messages = [
            {
                "role": "user",
                "content": [{"text": prompt}],
            }
        ]

        try:
            response = await asyncio.to_thread(
                self._bedrock.converse,
                modelId=MODEL_ID,
                messages=messages,
                inferenceConfig={
                    "maxTokens": 500,
                    "temperature": 0.2,
                },
            )
        except (ClientError, Exception) as exc:
            return {"raw": f"Error: {exc}"}

        try:
            text = response["output"]["message"]["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return {"raw": "Error: unexpected response format"}

        return {"raw": text}