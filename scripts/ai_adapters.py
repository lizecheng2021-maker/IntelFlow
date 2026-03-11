"""
Unified LLM adapter layer.

Provides a single interface to call Claude, OpenAI, Gemini, Zhipu, DashScope, and Ollama.
Prefers raw HTTP requests over SDKs for simplicity and fewer dependencies.
"""

import time
import logging
from abc import ABC, abstractmethod

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Raised when an LLM call fails after retries."""


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class LLMAdapter(ABC):
    """Base class for all LLM adapters with built-in retry on HTTP 429."""

    MAX_RETRIES = 3
    BACKOFF_BASE = 2  # seconds

    def __init__(self, model: str, api_key: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 4096, **kwargs):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra = kwargs

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def _call(self, prompt: str, system: str, max_tokens: int, temperature: float) -> str:
        ...

    def generate(self, prompt: str, system: str = "",
                 max_tokens: int | None = None, temperature: float | None = None) -> str:
        mt = max_tokens or self.max_tokens
        temp = temperature if temperature is not None else self.temperature
        last_err = None
        for attempt in range(self.MAX_RETRIES):
            try:
                return self._call(prompt, system, mt, temp)
            except LLMError:
                raise
            except Exception as exc:
                last_err = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status == 429 or "rate" in str(exc).lower():
                    wait = self.BACKOFF_BASE ** (attempt + 1)
                    logger.warning("%s rate-limited, retry in %ss (attempt %d/%d)",
                                   self.name, wait, attempt + 1, self.MAX_RETRIES)
                    time.sleep(wait)
                    continue
                raise LLMError(f"{self.name} failed: {exc}") from exc
        raise LLMError(f"{self.name} failed after {self.MAX_RETRIES} retries: {last_err}")

    def test_connection(self) -> bool:
        try:
            result = self.generate("Say hello", max_tokens=32)
            return bool(result and result.strip())
        except Exception as exc:
            logger.error("%s connection test failed: %s", self.name, exc)
            return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(url: str, headers: dict, payload: dict, timeout: int = 120) -> dict:
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code == 429:
        raise requests.exceptions.HTTPError("rate limited", response=resp)
    resp.raise_for_status()
    return resp.json()


def _openai_compatible_generate(url: str, api_key: str, model: str,
                                prompt: str, system: str,
                                max_tokens: int, temperature: float) -> str:
    """Shared helper for OpenAI-compatible APIs (OpenAI, Zhipu, DashScope)."""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    data = _post(url, headers, {
        "model": model, "messages": messages,
        "max_tokens": max_tokens, "temperature": temperature,
    })
    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Claude (Anthropic)
# ---------------------------------------------------------------------------

class ClaudeAdapter(LLMAdapter):
    API_URL = "https://api.anthropic.com/v1/messages"

    @property
    def name(self) -> str:
        return "anthropic"

    def _call(self, prompt, system, max_tokens, temperature):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            kwargs = {"model": self.model, "max_tokens": max_tokens,
                      "temperature": temperature,
                      "messages": [{"role": "user", "content": prompt}]}
            if system:
                kwargs["system"] = system
            return client.messages.create(**kwargs).content[0].text
        except ImportError:
            pass
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {"model": self.model, "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}]}
        if system:
            payload["system"] = system
        data = _post(self.API_URL, headers, payload)
        return data["content"][0]["text"]


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

class OpenAIAdapter(LLMAdapter):
    API_URL = "https://api.openai.com/v1/chat/completions"

    @property
    def name(self) -> str:
        return "openai"

    def _call(self, prompt, system, max_tokens, temperature):
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            resp = client.chat.completions.create(
                model=self.model, messages=messages,
                max_tokens=max_tokens, temperature=temperature)
            return resp.choices[0].message.content
        except ImportError:
            pass
        return _openai_compatible_generate(
            self.API_URL, self.api_key, self.model,
            prompt, system, max_tokens, temperature)


# ---------------------------------------------------------------------------
# Gemini (Google)
# ---------------------------------------------------------------------------

class GeminiAdapter(LLMAdapter):
    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    @property
    def name(self) -> str:
        return "gemini"

    def _call(self, prompt, system, max_tokens, temperature):
        url = f"{self.API_BASE}/{self.model}:generateContent?key={self.api_key}"
        contents = [{"parts": [{"text": prompt}]}]
        payload = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        data = _post(url, {"Content-Type": "application/json"}, payload)
        return data["candidates"][0]["content"]["parts"][0]["text"]


# ---------------------------------------------------------------------------
# Zhipu (GLM) — OpenAI-compatible
# ---------------------------------------------------------------------------

class ZhipuAdapter(LLMAdapter):
    API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    @property
    def name(self) -> str:
        return "zhipu"

    def _call(self, prompt, system, max_tokens, temperature):
        return _openai_compatible_generate(
            self.API_URL, self.api_key, self.model,
            prompt, system, max_tokens, temperature)


# ---------------------------------------------------------------------------
# DashScope (Qwen) — OpenAI-compatible
# ---------------------------------------------------------------------------

class DashScopeAdapter(LLMAdapter):
    API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    @property
    def name(self) -> str:
        return "dashscope"

    def _call(self, prompt, system, max_tokens, temperature):
        return _openai_compatible_generate(
            self.API_URL, self.api_key, self.model,
            prompt, system, max_tokens, temperature)


# ---------------------------------------------------------------------------
# Ollama (local)
# ---------------------------------------------------------------------------

class OllamaAdapter(LLMAdapter):
    @property
    def name(self) -> str:
        return "ollama"

    def _call(self, prompt, system, max_tokens, temperature):
        base = self.extra.get("base_url", "http://localhost:11434")
        url = f"{base}/api/generate"
        payload = {
            "model": self.model, "prompt": prompt, "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        if system:
            payload["system"] = system
        data = _post(url, {"Content-Type": "application/json"}, payload)
        return data["response"]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, type[LLMAdapter]] = {
    "anthropic": ClaudeAdapter,
    "openai": OpenAIAdapter,
    "gemini": GeminiAdapter,
    "zhipu": ZhipuAdapter,
    "dashscope": DashScopeAdapter,
    "ollama": OllamaAdapter,
}


def create_llm(config: dict) -> LLMAdapter:
    """Create an LLM adapter from a config dict.

    Expected keys: provider, model, temperature, max_tokens, api_key (optional).
    """
    provider = config.get("provider", "").lower()
    cls = _PROVIDERS.get(provider)
    if not cls:
        raise LLMError(f"Unknown provider '{provider}'. Choose from: {list(_PROVIDERS)}")
    return cls(
        model=config.get("model", ""),
        api_key=config.get("api_key"),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 4096),
        base_url=config.get("base_url", "http://localhost:11434"),
    )


# Config loading: use utils.load_ai_config() from the shared module
