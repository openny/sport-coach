from __future__ import annotations

from typing import List
import requests
from ..config import settings

def _prefix_e5(texts: List[str], is_query: bool) -> List[str]:
    """
    E5 계열 권장 프리픽스:
    - query:  검색 질의
    - passage: 문서 청크
    """
    prefix = "query: " if is_query else "passage: "
    return [prefix + t for t in texts]

def embed_texts(texts: List[str], is_query: bool = False) -> List[List[float]]:
    """
    Embedding Server (E5) 호출
    POST /embed/text
    Body: {"inputs":[...], "normalize": true}
    Resp: {"embeddings":[[...],[...]]}
    """
    base = (getattr(settings, "EMBED_BASE_URL", "") or "").rstrip("/")
    if not base:
        raise RuntimeError("EMBED_BASE_URL is empty")

    url = f"{base}/embed/text"

    # ✅ E5 권장 프리픽스 적용 (검색 품질 개선)
    inputs = _prefix_e5(texts, is_query=is_query)

    payload = {
        "inputs": inputs,      # ✅ 서버 요구 필드명
        "normalize": True,
        "model": getattr(settings, "EMBED_MODEL", None),
    }

    headers = {"Content-Type": "application/json"}
    key = getattr(settings, "EMBED_API_KEY", "") or ""
    if key:
        headers["Authorization"] = f"Bearer {key}"

    r = requests.post(url, json=payload, headers=headers, timeout=180)
    if not r.ok:
        raise RuntimeError(f"embeddings failed: {r.status_code} {r.text}")

    j = r.json()
    if "embeddings" in j and isinstance(j["embeddings"], list):
        return j["embeddings"]

    raise RuntimeError(f"unknown embed response shape: keys={list(j.keys())}")