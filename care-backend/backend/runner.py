import asyncio
import os

import boto3
from botocore.exceptions import ClientError


MODEL_ID = os.getenv("MODEL_ID", "eu.anthropic.claude-sonnet-4-6")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-central-1")

class LLMRunner:
    """Low-level execution layer for LLM requests via AWS Bedrock."""

    def __init__(self) -> None:
        self._client = boto3.client("bedrock-runtime", region_name=AWS_REGION)

    async def run(self, prompt: str) -> dict:
        """Send *prompt* to Bedrock and return the raw generated text.

        The blocking boto3 call is offloaded to a thread so the async
        event loop stays free.
        """
        messages = [
            {
                "role": "user",
                "content": [{"text": prompt}],
            }
        ]

        try:
            response = await asyncio.to_thread(
                self._client.converse,
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