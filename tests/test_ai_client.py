import time
from unittest.mock import patch, MagicMock

import pytest

from app.services.ai_client import (
    AIClient,
    CircuitBreaker,
    get_ai_client,
    _circuit_breaker,
)


class TestCircuitBreaker:
    def test_closed_initially(self):
        cb = CircuitBreaker(threshold=3, window_s=60)
        assert not cb.is_open()

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(threshold=3, window_s=60)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open()

    def test_does_not_open_on_fewer_failures(self):
        cb = CircuitBreaker(threshold=3, window_s=60)
        cb.record_failure()
        cb.record_failure()
        assert not cb.is_open()

    def test_old_failures_age_out(self):
        cb = CircuitBreaker(threshold=3, window_s=0.05)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open()
        time.sleep(0.1)
        assert not cb.is_open()

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(threshold=3, window_s=60)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        # Two failures after a success; still not open.
        assert not cb.is_open()


class TestGetAIClient:
    def setup_method(self):
        _circuit_breaker.reset()

    def test_returns_none_when_no_key(self):
        with patch("app.services.ai_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.AI_CIRCUIT_THRESHOLD = 3
            mock_settings.AI_CIRCUIT_WINDOW_S = 60
            assert get_ai_client() is None

    def test_returns_client_when_key_set(self):
        with patch("app.services.ai_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.EMBED_MODEL = "text-embedding-3-small"
            mock_settings.CHAT_MODEL = "gpt-4o-mini"
            mock_settings.AI_EMBED_TIMEOUT_S = 20
            mock_settings.AI_CHAT_TIMEOUT_S = 30
            client = get_ai_client()
            assert client is not None
            assert isinstance(client, AIClient)

    def test_returns_none_when_circuit_open(self):
        _circuit_breaker.threshold = 1
        _circuit_breaker.record_failure()
        with patch("app.services.ai_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.EMBED_MODEL = "x"
            mock_settings.CHAT_MODEL = "y"
            mock_settings.AI_EMBED_TIMEOUT_S = 20
            mock_settings.AI_CHAT_TIMEOUT_S = 30
            assert get_ai_client() is None


class TestAIClientEmbed:
    def test_calls_openai_and_returns_vectors(self):
        with patch("app.services.ai_client.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.embeddings.create.return_value.data = [
                MagicMock(embedding=[0.1, 0.2, 0.3]),
                MagicMock(embedding=[0.4, 0.5, 0.6]),
            ]
            c = AIClient("sk-x", embed_model="m", chat_model="c", embed_timeout=20, chat_timeout=30)
            out = c.embed(["foo", "bar"])
            assert out == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
            mock_client.embeddings.create.assert_called_once()

    def test_records_failure_on_exception(self):
        _circuit_breaker.reset()
        with patch("app.services.ai_client.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.embeddings.create.side_effect = RuntimeError("boom")
            c = AIClient("sk-x", embed_model="m", chat_model="c", embed_timeout=20, chat_timeout=30)
            with pytest.raises(RuntimeError):
                c.embed(["foo"])
        # Failure was recorded:
        assert _circuit_breaker.failure_count() == 1
