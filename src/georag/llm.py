"""Client for any OpenAI-compatible chat endpoint (Ollama, llama.cpp server, vLLM).

Only three calls are used across the agent: ``chat`` (whole answer), ``stream`` (token
iterator for the UI) and ``json`` (schema-constrained output for plans and extraction).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

_THINK = re.compile(r"<think>.*?</think>\s*", re.S)


def strip_thinking(text: str) -> str:
    text = _THINK.sub("", text)
    # An unterminated block means the model ran out of tokens while thinking.
    return text.split("<think>")[0].strip() if "<think>" in text else text.strip()


def extract_json(text: str) -> Any:
    text = strip_thinking(text)
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    if start < 0:
        raise ValueError("no JSON object in model output")
    depth, in_str, esc = 0, False, False
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unterminated JSON in model output")


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    log: list[dict] = field(default_factory=list)

    def add(self, kind: str, prompt: int, completion: int, seconds: float) -> None:
        self.calls += 1
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.seconds += seconds
        self.log.append(
            {
                "kind": kind,
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "seconds": round(seconds, 2),
            }
        )

    @property
    def tokens_per_second(self) -> float:
        return self.completion_tokens / self.seconds if self.seconds else 0.0


class LLM(Protocol):
    model: str
    usage: Usage

    def chat(
        self, messages: list[dict], max_tokens: int | None = None, temperature: float | None = None
    ) -> str: ...

    def stream(self, messages: list[dict], max_tokens: int | None = None) -> Iterator[str]: ...

    def json(
        self, messages: list[dict], schema: type[BaseModel] | dict, max_tokens: int | None = None
    ) -> Any: ...


class OpenAICompatLLM:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "local",
        temperature: float = 0.2,
        max_tokens: int = 700,
        timeout_s: float = 600.0,
        no_think: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.no_think = no_think
        self.client = httpx.Client(timeout=timeout_s, headers={"Authorization": f"Bearer {api_key}"})
        self.usage = Usage()
        self._json_format: int | None = None  # which response_format style the server honoured

    def _prep(self, messages: list[dict]) -> list[dict]:
        if not self.no_think:
            return messages
        msgs = [dict(m) for m in messages]
        # Hybrid Qwen3 models honour '/no_think'; instruct-only models ignore it.
        for m in reversed(msgs):
            if m["role"] == "user":
                m["content"] = f"{m['content']} /no_think"
                break
        return msgs

    def _payload(
        self, messages: list[dict], max_tokens: int | None, temperature: float | None, **extra
    ) -> dict:
        return {
            "model": self.model,
            "messages": self._prep(messages),
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self.max_tokens,
            **extra,
        }

    def available(self) -> bool:
        try:
            return self.client.get(f"{self.base_url}/models", timeout=5).status_code == 200
        except httpx.HTTPError:
            return False

    def chat(
        self, messages: list[dict], max_tokens: int | None = None, temperature: float | None = None, **extra
    ) -> str:
        t = time.perf_counter()
        resp = self.client.post(
            f"{self.base_url}/chat/completions",
            json=self._payload(messages, max_tokens, temperature, **extra),
        )
        resp.raise_for_status()
        data = resp.json()
        u = data.get("usage") or {}
        self.usage.add(
            "chat", u.get("prompt_tokens", 0), u.get("completion_tokens", 0), time.perf_counter() - t
        )
        return strip_thinking(data["choices"][0]["message"]["content"] or "")

    def stream(self, messages: list[dict], max_tokens: int | None = None) -> Iterator[str]:
        t = time.perf_counter()
        n = 0
        in_think = False
        payload = self._payload(messages, max_tokens, None, stream=True)
        with self.client.stream("POST", f"{self.base_url}/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if body == "[DONE]":
                    break
                delta = json.loads(body)["choices"][0].get("delta", {}).get("content") or ""
                if not delta:
                    continue
                n += 1
                if "<think>" in delta:
                    in_think = True
                if in_think:
                    if "</think>" in delta:
                        in_think = False
                        delta = delta.split("</think>", 1)[1]
                    else:
                        continue
                if delta:
                    yield delta
        self.usage.add("stream", 0, n, time.perf_counter() - t)

    def json(
        self, messages: list[dict], schema: type[BaseModel] | dict, max_tokens: int | None = None
    ) -> Any:
        js = schema.model_json_schema() if isinstance(schema, type) else schema
        # Servers disagree on how a schema is passed: Ollama and vLLM take OpenAI's json_schema,
        # llama-cpp-python takes {"type": "json_object", "schema": ...} and turns it into a grammar.
        formats: list[dict[str, Any]] = [
            {"type": "json_schema", "json_schema": {"name": "output", "schema": js, "strict": True}},
            {"type": "json_object", "schema": js},
        ]
        if self._json_format is not None:
            formats.insert(0, formats.pop(self._json_format))
        last_error: Exception | None = None
        for fmt in formats:
            try:
                text = self.chat(messages, max_tokens=max_tokens, temperature=0.0, response_format=fmt)
                data = extract_json(text)
                out = schema.model_validate(data) if isinstance(schema, type) else data
            except (httpx.HTTPStatusError, ValueError) as exc:  # pydantic's ValidationError is a ValueError
                last_error = exc
                continue
            self._json_format = 0 if fmt["type"] == "json_schema" else 1
            return out
        raise ValueError(f"model output did not match the schema: {last_error}")


class ScriptedLLM:
    """Deterministic stand-in used by the test suite and CPU-only CI.

    ``responder`` receives the message list and returns the reply text; the default echoes a
    short answer that cites the first source, which is enough to exercise the citation parser,
    the support check and the API.
    """

    def __init__(self, responder: Callable[[list[dict]], str] | None = None, model: str = "scripted"):
        self.model = model
        self.usage = Usage()
        self.responder = responder or self._default
        self.calls: list[list[dict]] = []

    @staticmethod
    def _default(messages: list[dict]) -> str:
        user = messages[-1]["content"]
        m = re.search(r"\[1\][^\n]*\n(.+?)(?:\n\[2\]|\n\n|$)", user, re.S)
        snippet = (m.group(1).strip() if m else "The sources describe the method.").split(". ")[0]
        return f"{snippet.rstrip('.')} [1]."

    def chat(
        self, messages: list[dict], max_tokens: int | None = None, temperature: float | None = None, **_: Any
    ) -> str:
        self.calls.append(messages)
        self.usage.add("chat", 0, 0, 0.0)
        return strip_thinking(self.responder(messages))

    def stream(self, messages: list[dict], max_tokens: int | None = None) -> Iterator[str]:
        text = self.chat(messages, max_tokens)
        yield from re.findall(r"\S+\s*", text)

    def json(
        self, messages: list[dict], schema: type[BaseModel] | dict, max_tokens: int | None = None
    ) -> Any:
        data = extract_json(self.chat(messages, max_tokens))
        return schema.model_validate(data) if isinstance(schema, type) else data
