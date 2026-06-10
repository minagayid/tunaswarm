"""Hugging Face Inference API client for TunaSwarm.

Reads HF_TOKEN from env.  Uses the unified Inference Providers endpoint so
any supported model can be selected via the HF_MODEL env var.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

# Forward-compatible import: huggingface_hub>=0.21 has InferenceClient.
try:
    from huggingface_hub import InferenceClient  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    InferenceClient = None  # type: ignore

DEFAULT_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen3-4B-Instruct")
DEFAULT_TOKEN = os.getenv("HF_TOKEN", "")
HF_TIMEOUT = int(os.getenv("HF_TIMEOUT", "60"))


class HFInferenceError(Exception):
    pass


class HFClient:
    def __init__(self, token: Optional[str] = None, model: Optional[str] = None) -> None:
        self.token = token or DEFAULT_TOKEN
        self.model = model or DEFAULT_MODEL
        if InferenceClient is None:
            raise HFInferenceError(
                "huggingface_hub is not installed. Run: pip install huggingface_hub"
            )
        if not self.token:
            raise HFInferenceError("HF_TOKEN is not set. Export it or pass token=...")

        self._client = InferenceClient(token=self.token, timeout=HF_TIMEOUT)

    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        seed: Optional[int] = None,
    ) -> str:
        model_id = model or self.model
        try:
            result = self._client.text_generation(
                prompt=prompt,
                model=model_id,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                seed=seed,
            )
        except Exception as exc:
            raise HFInferenceError(f"Inference failed: {exc}") from exc
        if isinstance(result, str):
            return result
        # Some versions return a TextGenerationOutput object
        return getattr(result, "generated_text", str(result))

    def chat(
        self,
        messages: list[Dict[str, str]],
        *,
        model: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        seed: Optional[int] = None,
        stream: bool = False,
    ):
        model_id = model or self.model
        try:
            return self._client.chat_completion(
                model=model_id,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                seed=seed,
                stream=stream,
            )
        except Exception as exc:
            raise HFInferenceError(f"Chat inference failed: {exc}") from exc

    def embed(self, texts: list[str], *, model: Optional[str] = None) -> list[list[float]]:
        model_id = model or self.model
        try:
            return self._client.feature_extraction(texts=texts, model=model_id)
        except Exception as exc:
            raise HFInferenceError(f"Embedding failed: {exc}") from exc


_client_singleton: Optional[HFClient] = None


def get_client() -> HFClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = HFClient()
    return _client_singleton


def complete_text(prompt: str, **kwargs: Any) -> str:
    return get_client().generate(prompt, **kwargs)


def complete_chat(messages: list[Dict[str, str]], **kwargs: Any) -> Any:
    return get_client().chat(messages, **kwargs)
