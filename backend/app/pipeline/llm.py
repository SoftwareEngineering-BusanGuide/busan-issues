"""Gemini API로 정해진 JSON 형식의 응답을 받는다. 모델을 바꿔도 이 파일만 고치면 된다 (NFR-006)."""

import json
import time
from collections.abc import Callable
from typing import Any

import httpx

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
RETRY_STATUS = {429, 500, 503}


class LlmError(Exception):
    pass


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        client: httpx.Client | None = None,
        retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=60)
        self._retries = retries
        self._sleep = sleep

    def generate_json(self, prompt: str, schema: dict) -> Any:
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "temperature": 0},
        }
        url = f"{BASE_URL}/models/{self._model}:generateContent"
        for attempt in range(self._retries + 1):
            try:
                res = self._client.post(url, json=body, headers={"x-goog-api-key": self._api_key})
            except httpx.TransportError as e:
                if attempt == self._retries:
                    raise LlmError(f"Gemini 연결 실패: {e}") from e
                self._sleep(5 * 2**attempt)
                continue
            # 무료 등급 속도 제한(429)이나 일시 장애면 잠시 기다렸다 다시 시도한다
            if res.status_code in RETRY_STATUS and attempt < self._retries:
                self._sleep(5 * 2**attempt)
                continue
            if res.status_code != 200:
                raise LlmError(f"Gemini 오류 {res.status_code}: {res.text[:200]}")
            try:
                parts = res.json()["candidates"][0]["content"]["parts"]
                return json.loads("".join(p.get("text", "") for p in parts))
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                raise LlmError(f"Gemini 응답 형식 오류: {e}") from e
        raise LlmError("Gemini 재시도 횟수 초과")
