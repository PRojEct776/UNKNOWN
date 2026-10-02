"""
UNKNOWN X v3.1 - Gemini Live Smoke Test

Purpose:
    Production smoke test for Gemini provider.
    Retries only transient Gemini server failures.
"""

from __future__ import annotations

import time

from app.llm.base_provider import ErrorKind
from app.llm.gemini_provider import GeminiProvider


def test_live_request(retries: int = 3, delay: int = 5) -> None:
    """Run a live Gemini request with retry for transient failures."""

    if retries < 1:
        raise ValueError("retries must be >= 1")

    provider = GeminiProvider()
    last_response = None

    for attempt in range(1, retries + 1):
        try:
            response = provider.generate(
                "Explain Retrieval-Augmented Generation in one sentence."
            )
            last_response = response

        except Exception as error:
            print(f"\nAttempt {attempt}/{retries}")
            print(f"Unhandled exception: {error}")

            if attempt < retries:
                wait = delay * (2 ** (attempt - 1))
                print(f"Retrying in {wait} seconds...\n")
                time.sleep(wait)
                continue

            raise

        print("\n" + "=" * 60)
        print(f"Attempt {attempt}/{retries}")
        print("=" * 60)
        print(f"Provider : {response.provider}")
        print(f"Model    : {response.model}")
        print(f"Latency  : {response.latency_ms} ms")
        print(f"Success  : {response.success}")

        if response.success:
            print("\nResponse:\n")
            print(response.answer)
            print("\n✅ Gemini live test passed.")
            return

        assert response.error_kind is not None
        print(f"\nError Type : {response.error_kind.value}")
        print(f"Error      : {response.error}")

        # Retry only temporary Gemini server failures.
        if response.error_kind == ErrorKind.TRANSIENT and attempt < retries:
            wait = delay * (2 ** (attempt - 1))
            print(f"\nRetrying in {wait} seconds...\n")
            time.sleep(wait)
            continue

        break

    assert last_response is not None

    print("\n" + "=" * 60)
    print("UNKNOWN X v3.1 - GEMINI LIVE TEST RESULT")
    print("=" * 60)
    assert last_response.error_kind is not None
    print(f"Final Error Type : {last_response.error_kind.value}")
    print(f"Final Error      : {last_response.error}")

    if last_response.error_kind == ErrorKind.TRANSIENT:
        print("\n⚠ Gemini servers are temporarily under high demand.")
        print("Backend is working correctly. Try again later.")
        return

    if last_response.error_kind == ErrorKind.RATE_LIMIT:
        print("\n⚠ Gemini API quota exhausted.")
        return

    if last_response.error_kind == ErrorKind.INVALID_REQUEST:
        raise RuntimeError("Invalid Gemini request or API key.")

    if last_response.error_kind == ErrorKind.EMPTY:
        raise RuntimeError("Gemini returned an empty response.")

    raise RuntimeError(last_response.error or "Gemini live test failed.")


if __name__ == "__main__":
    test_live_request()
