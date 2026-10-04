"""Tiny client for any OpenAI-compatible server (Ollama, LM Studio, vLLM, hosted free tiers). Standard library only."""
import json
import urllib.request

from . import config


class LLMError(Exception):
    pass


def enabled() -> bool:
    return config.LLM_PROVIDER == "openai_compatible"


def embeddings_enabled() -> bool:
    return enabled() and bool(config.EMBED_MODEL)


def _post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(config.LLM_BASE_URL + path, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": "Bearer " + config.LLM_API_KEY} if config.LLM_API_KEY else {})})
    try:
        with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT) as r:
            return json.load(r)
    except Exception as e:  # network, HTTP error, bad JSON: all mean "model unavailable"
        raise LLMError(f"LLM request failed: {e}") from e


def chat(messages: list[dict]) -> str:
    out = _post("/chat/completions", {"model": config.LLM_MODEL, "messages": messages, "temperature": 0.1})
    try:
        return out["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError("Unexpected LLM response") from e


def embed(texts: list[str]) -> list[list[float]]:
    out = _post("/embeddings", {"model": config.EMBED_MODEL, "input": texts})
    try:
        return [d["embedding"] for d in out["data"]]
    except (KeyError, TypeError) as e:
        raise LLMError("Unexpected embeddings response") from e
