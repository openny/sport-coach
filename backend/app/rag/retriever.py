# backend/app/rag/retriever.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import ManualChunk
from .embedder import embed_texts


@dataclass
class RetrievedChunk:
    content: str
    source: Optional[str] = None
    score: Optional[float] = None


def _cosine_from_normalized(a: list[float], b: list[float]) -> float:
    # E5 서버에서 normalize된 벡터를 준다고 가정(대부분 그렇고, 그래야 안정적)
    # normalized면 cosine = dot
    s = 0.0
    # 길이가 다르면 안전하게 min
    n = min(len(a), len(b))
    for i in range(n):
        s += float(a[i]) * float(b[i])
    return s


def retrieve(sport: str, query: str, top_k: int = 5, limit_scan: int = 2000) -> List[RetrievedChunk]:
    """
    MVP: manual_chunks에서 limit_scan 만큼만 가져와 cosine 계산 후 top_k 반환.
    추후 pgvector로 교체 권장.
    """
    q_emb = embed_texts([query], is_query=True)[0]

    db: Session = SessionLocal()
    try:
        rows = (
            db.query(ManualChunk)
            .filter(ManualChunk.sport == sport)
            .order_by(ManualChunk.id.desc())
            .limit(limit_scan)
            .all()
        )

        scored: list[tuple[float, ManualChunk]] = []
        for r in rows:
            if not r.embedding:
                continue
            score = _cosine_from_normalized(q_emb, r.embedding)
            scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        out: List[RetrievedChunk] = []
        for score, r in top:
            page = None
            try:
                page = (r.meta or {}).get("page")
            except Exception:
                page = None

            out.append(
                RetrievedChunk(
                    content=r.chunk_text,
                    source=f"manual:{r.manual_id}" + (f" p.{page}" if page else ""),
                    score=float(score),
                )
            )
        return out
    finally:
        db.close()