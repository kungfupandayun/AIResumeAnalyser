import logging
import time
from collections import deque
from typing import List, Optional

from openai import OpenAI

from core.config import settings

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Simple time-window circuit breaker.

    Opens after `threshold` failures within `window_s` seconds.
    A single success resets the failure deque.
    """

    def __init__(self, threshold: int, window_s: float):
        self.threshold = threshold
        self.window_s = window_s
        self._failures: deque = deque()

    def _evict_old(self) -> None:
        now = time.monotonic()
        while self._failures and (now - self._failures[0]) > self.window_s:
            self._failures.popleft()

    def is_open(self) -> bool:
        self._evict_old()
        return len(self._failures) >= self.threshold

    def record_failure(self) -> None:
        self._failures.append(time.monotonic())

    def record_success(self) -> None:
        self._failures.clear()

    def failure_count(self) -> int:
        self._evict_old()
        return len(self._failures)

    def reset(self) -> None:
        self._failures.clear()


_circuit_breaker = CircuitBreaker(
    threshold=settings.AI_CIRCUIT_THRESHOLD,
    window_s=settings.AI_CIRCUIT_WINDOW_S,
)


class AIClient:
    """Thin wrapper around the OpenAI SDK.

    Each public method records success/failure with the module-level circuit
    breaker. Scorers wrap calls in their own try/except and treat any
    exception as 'AI not available for this call'.
    """

    def __init__(
        self,
        api_key: str,
        embed_model: str,
        chat_model: str,
        embed_timeout: float,
        chat_timeout: float,
    ):
        self._client = OpenAI(api_key=api_key)
        self._embed_model = embed_model
        self._chat_model = chat_model
        self._embed_timeout = embed_timeout
        self._chat_timeout = chat_timeout

    def embed(self, texts: List[str]) -> List[List[float]]:
        try:
            resp = self._client.embeddings.create(
                model=self._embed_model,
                input=texts,
                timeout=self._embed_timeout,
            )
            _circuit_breaker.record_success()
            return [d.embedding for d in resp.data]
        except Exception:
            _circuit_breaker.record_failure()
            raise

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self._chat_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                timeout=self._chat_timeout,
            )
            _circuit_breaker.record_success()
            return resp.choices[0].message.content or ""
        except Exception:
            _circuit_breaker.record_failure()
            raise


def get_ai_client() -> Optional[AIClient]:
    """Return an AIClient if usable, else None.

    None means: no API key configured, OR the circuit breaker is open
    after recent failures. Either way: scorers take their keyword-only path.
    """
    if not settings.OPENAI_API_KEY:
        return None
    if _circuit_breaker.is_open():
        logger.warning("AI circuit breaker open; falling back to keyword-only mode.")
        return None
    return AIClient(
        api_key=settings.OPENAI_API_KEY,
        embed_model=settings.EMBED_MODEL,
        chat_model=settings.CHAT_MODEL,
        embed_timeout=settings.AI_EMBED_TIMEOUT_S,
        chat_timeout=settings.AI_CHAT_TIMEOUT_S,
    )
