"""
UNKNOWN X v2.0 - Gemini LLM Engine (Production Stable)

Uses Google GenAI SDK with Chat API.
Compatible with Gemini 3.6 Flash.
"""

import time

from google import genai
from google.genai import types

from app.rag.config import settings
from app.rag.logger import logger


class GeminiEngine:
    """Gemini wrapper for UNKNOWN X."""

    def __init__(self):
        if not settings.GEMINI_API_KEY:  # type: ignore
            raise ValueError("GEMINI_API_KEY not found in backend/.env")

        # Create reusable Gemini client
        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY,  # type: ignore
            http_options=types.HttpOptions(timeout=60000),  # 60 seconds
        )

        self.model_name = settings.GEMINI_MODEL

        logger.info(f"Gemini Engine initialized with model: {self.model_name}")

    def generate(
        self,
        prompt: str,
        retries: int = 4,
    ) -> str:
        """
        Generate response using Gemini Chat API.
        """

        for attempt in range(1, retries + 1):

            try:
                chat = self.client.chats.create(
                    model=self.model_name,
                    config=types.GenerateContentConfig(
                        temperature=settings.TEMPERATURE,
                        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
                    ),
                )

                response = chat.send_message(prompt)

                if response is None:
                    raise ValueError("Gemini returned None.")

                if not getattr(response, "text", None):
                    raise ValueError("Gemini returned empty response.")

                logger.info("Gemini response generated successfully.")

                assert response.text is not None
                return response.text.strip()

            except Exception as error:  # noqa: BLE001

                error_text = str(error)

                logger.warning(
                    f"Gemini attempt {attempt}/{retries} failed: {error_text}"
                )

                # Stop immediately on quota errors.
                if (
                    "RESOURCE_EXHAUSTED" in error_text
                    or "429" in error_text
                    or "PerDay" in error_text
                ):
                    logger.error("Gemini daily quota exhausted.")
                    return (
                        "Gemini API quota exhausted. "
                        "Please generate a new API key or wait for quota reset."
                    )

                # Retry only for temporary errors.
                if attempt < retries:
                    time.sleep(min(2 ** (attempt - 1), 8))

        logger.error("Gemini failed after all retry attempts.")

        return "Unable to generate a response at the moment. " "Please try again."
