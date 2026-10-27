"""Patch gemini_provider.py: replace both 3-models x 2-attempts retry loops with a
bounded single-attempt chain (llm_fallback.bounded_model_chain).

Usage (from backend\\):  python patch_gemini.py
Makes gemini_provider.py.bak first. Safe to re-run (it refuses if already patched).
"""
import re
import shutil
import sys
from pathlib import Path

TARGET = Path(sys.argv[1] if len(sys.argv) > 1 else "app/llm/gemini_provider.py")

METHOD = '''    def _run_chain(self, prompt: str, config: Any) -> str:
        """One attempt per model; quota errors stop the chain; bounded total time."""
        from app.llm.llm_fallback import bounded_model_chain

        budget = float(getattr(settings, "GEMINI_CHAIN_BUDGET_S", 10.0))
        state: dict = {"exc": None, "fatal": False}

        def attempt(model_name: str, timeout: float) -> str:
            if state["fatal"] and state["exc"] is not None:
                raise state["exc"]
            try:
                response = self.client.models.generate_content(  # type: ignore
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
                text = response.text
                if text and text.strip():
                    return text
                raise self._empty_error(response)
            except errors.APIError as exc:
                state["exc"] = exc
                if exc.code not in (500, 502, 503, 504, 429):
                    state["fatal"] = True
                logger.warning(
                    "Gemini API error (%s) on model %s; single attempt, no retry.",
                    exc.code,
                    model_name,
                )
                raise
            except Exception as exc:  # noqa: BLE001
                state["exc"] = exc
                raise

        res = bounded_model_chain(
            self._candidate_models(), attempt, budget_s=budget
        )
        if res.ok:
            self._answered_model = res.model
            return res.text  # type: ignore[return-value]
        if state["exc"] is not None:
            raise state["exc"]
        raise RuntimeError(res.error or "Gemini failed.")

'''

LOOP = re.compile(
    r"last_error = None\s+for model_name in self\._candidate_models\(\):.*?"
    r'raise RuntimeError\("Gemini failed after retries\."\)',
    re.DOTALL,
)
ANCHOR = "    def _call(self, prompt: str, system: str | None = None) -> str:"


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    if "_run_chain" in src:
        print("Already patched. Nothing to do.")
        return 0
    if src.count(ANCHOR) != 1:
        print(f"ERROR: expected exactly one {ANCHOR!r}; found {src.count(ANCHOR)}.")
        return 1
    n = len(LOOP.findall(src))
    if n != 2:
        print(f"ERROR: expected 2 retry loops (_call, _call_structured); found {n}. No changes made.")
        return 1

    shutil.copy2(TARGET, str(TARGET) + ".bak")
    new = LOOP.sub("return self._run_chain(prompt, config)", src)
    new = new.replace(ANCHOR, METHOD + ANCHOR, 1)
    compile(new, str(TARGET), "exec")  # syntax check before writing
    TARGET.write_text(new, encoding="utf-8")
    print(f"Patched {TARGET} (2 loops replaced). Backup: {TARGET}.bak")
    return 0


if __name__ == "__main__":
    sys.exit(main())
