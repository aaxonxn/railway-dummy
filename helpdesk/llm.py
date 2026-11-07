"""Gemini LLM client interface using official google-genai SDK."""

import os
import time
from typing import Optional
from dotenv import load_dotenv

from helpdesk.config import config
from helpdesk.logging_config import logger

load_dotenv()

# Global client cache
_GEMINI_CLIENT = None


def get_gemini_client():
    """Retrieve or initialize google-genai client."""
    global _GEMINI_CLIENT
    if _GEMINI_CLIENT is None:
        from google import genai
        api_key = config.gemini_api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY is not configured. Live LLM calls will fail.")
            return None
        _GEMINI_CLIENT = genai.Client(api_key=api_key)
    return _GEMINI_CLIENT


class LLMClient:
    """Interface for invoking Google Gemini models with retries and fallback."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or config.gemini_model
        self.fallback_models = [
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.7-flash",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",
        ]

    def generate(self, prompt: str, system_instruction: Optional[str] = None, max_retries: int = 3) -> str:
        """Generate content from Gemini with error handling and retry logic."""
        client = get_gemini_client()
        if client is None:
            raise RuntimeError("Gemini API key is not configured. Please set GEMINI_API_KEY in .env.")

        models_to_try = [self.model_name] + [m for m in self.fallback_models if m != self.model_name]

        last_error = None
        for current_model in models_to_try:
            for attempt in range(max_retries):
                try:
                    kwargs = {"contents": prompt}
                    if system_instruction:
                        from google.genai import types
                        kwargs["config"] = types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.1,  # Low temperature for strict factual adherence
                        )

                    logger.debug("Calling Gemini (%s) attempt %d...", current_model, attempt + 1)
                    response = client.models.generate_content(
                        model=current_model,
                        **kwargs
                    )
                    if response and response.text:
                        return response.text.strip()
                    return ""
                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    logger.warning("Gemini call failed with model %s (attempt %d/%d): %s", current_model, attempt + 1, max_retries, err_str)
                    if "404" in err_str or "not available" in err_str.lower():
                        break
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                        logger.warning("Rate limit on %s; trying next model...", current_model)
                        break
                    if "503" in err_str or "UNAVAILABLE" in err_str:
                        logger.warning("Model %s temporarily unavailable (503); trying next model...", current_model)
                        break
                    time.sleep(1.0 * (attempt + 1))

        raise RuntimeError(f"All Gemini generation attempts failed. Last error: {last_error}")
