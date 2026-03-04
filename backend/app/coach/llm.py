# backend/app/coach/llm.py
from __future__ import annotations

import os
from typing import Dict, Any
import time
import re
import requests

from ..config import settings

def _openai_compat_chat(prompt: str) -> str:
    """
    OpenAI-compatible /v1/chat/completions
    """
    base = settings.LLM_BASE_URL.rstrip("/")
    url = f"{base}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"

    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful sports coach."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=180)
    if not r.ok:
        raise RuntimeError(f"LLM error: {r.status_code} {r.text}")

    data = r.json()
    return data["choices"][0]["message"]["content"]

def chat_completion(prompt: str) -> str:
    """
    ✅ tasks.py에서 import해서 쓰는 표준 진입점
    """
    provider = (getattr(settings, "LLM_PROVIDER", "") or "openai_compatible").lower()
    # 지금 너는 openai_compatible을 쓰는 상태로 보임
    return _openai_compat_chat(prompt)

def _shrink_prompt(prompt: str, *, keep_head: int, keep_tail: int) -> str:
    if len(prompt) <= keep_head + keep_tail:
        return prompt[: max(0, keep_head)]
    return prompt[:keep_head] + "\n...\n" + prompt[-keep_tail:]

def generate_coaching(prompt: str) -> str:
    url = f"{settings.LLM_BASE_URL}/chat/completions"

    # 1차 시도: 원본 prompt
    candidates = [
        prompt,
        # 2차: 줄이기(중간 잘라내기)
        _shrink_prompt(prompt, keep_head=2400, keep_tail=400),
        # 3차: 더 줄이기
        _shrink_prompt(prompt, keep_head=1800, keep_tail=300),
        # 4차: 매우 짧게
        _shrink_prompt(prompt, keep_head=1200, keep_tail=220),
    ]

    last_err = None
    for p in candidates:
        try:
            payload = {
                "model": settings.LLM_MODEL,
                "messages": [{"role": "user", "content": p}],
                "temperature": 0.2,
            }
            r = requests.post(url, json=payload, timeout=120)
            if r.status_code == 400 and "maximum context length" in r.text:
                last_err = RuntimeError(f"LLM context too long: {r.text}")
                continue

            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"LLM call failed after shrinking: {last_err}")