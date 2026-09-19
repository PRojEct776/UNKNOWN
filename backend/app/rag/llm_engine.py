"""
UNKNOWN Project - Sprint 3
LLM Engine using Google Gemini

Handles:
- Gemini client initialization
- Environment configuration
- Timeout protection
- Retry mechanism
- Logging
"""

import os
import time
import logging

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()

logger = logging.getLogger("UNKNOWN")


class GeminiEngine:
    """Gemini LLM wrapper for UNKNOWN RAG pipeline."""

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        model_name = os.getenv("MODEL_NAME", "gemini-2.5-flash")

        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in .env")

        # Create one reusable Gemini client
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=30000)  # 30 seconds
        )

        self.model_name = model_name

        logger.info(f"Gemini Engine initialized with model: {model_name}")

    def generate(self, prompt: str, retries: int = 2) -> str:
        """
        Generate response from Gemini.

        Args:
            prompt (str): Prompt sent to Gemini.
            retries (int): Number of retry attempts for transient failures.

        Returns:
            str: Gemini-generated response or fallback message.
        """

        temperature = float(os.getenv("TEMPERATURE", 0.2))
        max_tokens = int(os.getenv("MAX_OUTPUT_TOKENS", 2048))

        for attempt in range(1, retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                )

                logger.info("Gemini response generated successfully.")
                return response.text.strip()

            except Exception as error:
                logger.warning(
                    f"Gemini attempt {attempt}/{retries} failed: {error}"
                )

                # Retry only if attempts remain
                if attempt < retries:
                    time.sleep(2)
                else:
                    logger.error("Gemini failed after all retry attempts.")

        return "Unable to generate a response at the moment. Please try again."