"""Ollama HTTP client."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx

from .prompt import PromptParts


@dataclass
class OllamaResult:
    response: str
    latency_ms: float


class OllamaClient:
    def __init__(
        self,
        host: str,
        model: str,
        timeout_s: float = 30.0,
        max_retries: int = 3,
        backoff_s: float = 1.0,
    ) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._backoff_s = backoff_s

    def generate(self, prompt: PromptParts) -> OllamaResult:
        payload = {
            "model": self._model,
            "prompt": prompt.user,
            "system": prompt.system,
            "stream": False,
        }
        last_error: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            start = time.perf_counter()
            try:
                response = httpx.post(
                    f"{self._host}/api/generate",
                    json=payload,
                    timeout=self._timeout_s,
                )
                response.raise_for_status()
                data = response.json()
                latency_ms = (time.perf_counter() - start) * 1000
                return OllamaResult(response=data.get("response", ""), latency_ms=latency_ms)
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
                last_error = exc
                time.sleep(self._backoff_s * attempt)

        raise RuntimeError("Ollama request failed") from last_error
