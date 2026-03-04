from __future__ import annotations

import time
from typing import Any, Dict, List

from celery import shared_task
from sqlalchemy.orm import Session
from sqlalchemy import delete

from .analysis.pose_features import run_pose_and_feature_analysis
from .analysis.issues import segments_to_issues_seed  # ✅ 추가

from .coach.json_parse import extract_json
from .coach.llm import generate_coaching
from .coach.postprocess import enforce_timecodes

from .config import settings
from .db import SessionLocal
from .models import Job, Result, Video, Manual, ManualChunk

from .rag.chunking import chunk_text
from .rag.embedder import embed_texts
from .rag.pdf import extract_text_per_page
from .rag.retriever import retrieve

from .storage import get_object_bytes
from .video_transcode import transcode_to_mp4

from .coach.prompts import (
    compact_issues_seed_for_llm,
    compact_rag_chunks_for_llm,
    build_ski_prompt_v2, compact_analysis_for_llm,
)

# ---------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------

def _now_ms() -> int:
    return int(time.time() * 1000)


def _analysis_summary_text(analysis_json: Dict[str, Any]) -> str:
    s = ""
    if isinstance(analysis_json, dict):
        s = str(analysis_json.get("summary") or "").strip()
    if len(s) < 20:
        s = "Ski coaching request. Provide feedback focusing on stance, balance, edging, pressure control, and turn timing."
    return s


def _fallback_coaching_json(level: str, analysis_summary: str, rag_chunks: List[dict]) -> Dict[str, Any]:
    """
    ✅ LLM 실패/파싱 실패 시 프론트가 깨지지 않게 최소 JSON
    """
    return {
        "summary": {
            "one_liner": "균형과 하체 정렬을 먼저 잡고, 엣지-압력-타이밍을 순서대로 개선해보세요.",
            "level": level,
            "highlights": ["균형/정렬", "엣지", "압력", "타이밍"],
            "top_priority": "균형/정렬",
            "overall_score": 0,
        },
        "issues": [],
        "rag": {
            "used": True if rag_chunks else False,
            "citations": [
                {
                    "source": c.get("source"),
                    "page": int(c.get("page") or 0),
                    "score": float(c.get("score") or 0.0),
                    "preview": (c.get("content") or "")[:160],
                }
                for c in (rag_chunks or [])[:5]
            ],
        },
        "debug": {
            "analysis_summary": analysis_summary[:300],
            "fallback": True,
        },
    }


def _ensure_coaching_json_shape(
    coaching_json: Any,
    *,
    level: str,
    analysis_summary: str,
    rag_chunks: List[Dict[str, Any]],
    issues_seed: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    - coaching_json이 dict가 아니면 fallback
    - issues가 비었거나 이상하면 issues_seed 기반으로 최소 복구
    """
    if not isinstance(coaching_json, dict):
        coaching_json = _fallback_coaching_json(level, analysis_summary, rag_chunks)

    coaching_json.setdefault("summary", {})
    coaching_json.setdefault("issues", [])
    coaching_json.setdefault("rag", {"used": bool(rag_chunks), "citations": []})
    coaching_json.setdefault("debug", {})

    # summary 최소 필드 보정
    s = coaching_json["summary"]
    if not isinstance(s, dict):
        coaching_json["summary"] = {}
        s = coaching_json["summary"]
    s.setdefault("level", level)
    # 프론트 키가 one_liner / one_line 혼재 가능성 대비
    if "one_liner" not in s and "one_line" in s:
        s["one_liner"] = s["one_line"]
    s.setdefault("one_liner", "영상 분석 결과를 기반으로 우선순위부터 개선해보세요.")
    s.setdefault("highlights", [])
    s.setdefault("top_priority", "")
    s.setdefault("overall_score", 0)

    # rag citations 기본 채우기
    if not coaching_json["rag"].get("citations"):
        coaching_json["rag"]["citations"] = [
            {
                "source": c.get("source"),
                "page": int(c.get("page") or 0),
                "score": float(c.get("score") or 0.0),
                "preview": (c.get("content") or "")[:160],
            }
            for c in (rag_chunks or [])[:5]
        ]
    coaching_json["rag"]["used"] = bool(rag_chunks)

    # issues_seed 기반으로 timecode / title / severity 정합성 강제
    seed_by_id = {x.get("id"): x for x in issues_seed if isinstance(x, dict) and x.get("id")}
    fixed_issues: List[Dict[str, Any]] = []

    if isinstance(coaching_json.get("issues"), list):
        for it in coaching_json["issues"]:
            if not isinstance(it, dict):
                continue
            sid = it.get("id")
            seed = seed_by_id.get(sid)
            if not seed:
                continue
            it["title"] = seed.get("title") or it.get("title")
            it["severity"] = seed.get("severity") or it.get("severity")
            it["timecode_sec"] = float(seed.get("start_sec") or seed.get("timecode_sec") or 0.0)
            fixed_issues.append(it)

    # LLM이 issues를 안 주거나/엉뚱하게 주면 seed 기반 최소 이슈 생성
    if not fixed_issues and issues_seed:
        for x in issues_seed[:6]:
            fixed_issues.append(
                {
                    "id": x.get("id"),
                    "title": x.get("title"),
                    "severity": x.get("severity", "medium"),
                    "timecode_sec": float(x.get("start_sec") or x.get("timecode_sec") or 0.0),
                    "why": x.get("why", ""),
                    "how_to_fix": [
                        (x.get("hints") or {}).get("top_cues", "")
                    ],
                    "drills": [
                        (x.get("hints") or {}).get("drills", "")
                    ],
                    "textbook_basis": {"claims": [], "citations": []},
                }
            )

    coaching_json["issues"] = fixed_issues

    # debug에 최소 정보
    coaching_json["debug"].setdefault("analysis_summary", analysis_summary[:400])
    coaching_json["debug"].setdefault("issues_seed_count", len(issues_seed))
    coaching_json["debug"].setdefault("rag_count", len(rag_chunks))

    return coaching_json


def _embed_texts_compat(texts: List[str], *, is_query: bool) -> List[Any]:
    """
    embed_texts 시그니처가 프로젝트마다 달라서(이전에 is_query 에러) 안전 래퍼 제공
    - embed_texts(texts, is_query=bool) 지원하면 그대로
    - 아니면 embed_texts(texts) 로 fallback
    """
    try:
        return embed_texts(texts, is_query=is_query)  # type: ignore
    except TypeError:
        return embed_texts(texts)  # type: ignore


# ---------------------------------------------------------------------
# Main Task
# ---------------------------------------------------------------------
def dedup_issues_seed(issues_seed: list[dict], max_items: int = 6) -> list[dict]:
    # id/tag 기준으로 최고 score만 유지
    best: dict[str, dict] = {}
    for it in issues_seed:
        k = str(it.get("id") or it.get("tag") or it.get("title") or "")
        if not k:
            continue
        if k not in best or float(it.get("score", 0)) > float(best[k].get("score", 0)):
            best[k] = it

    # score 내림차순 + max_items 제한
    out = sorted(best.values(), key=lambda x: float(x.get("score", 0)), reverse=True)
    return out[:max_items]

@shared_task(bind=True)
def run_analysis_job(self, job_id: int):
    db: Session = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return

        video = db.get(Video, job.video_id)
        if not video:
            job.status = "failed"
            job.error = "video not found"
            db.commit()
            return

        job.status = "running"
        job.progress = 5
        db.commit()

        # ✅ Result row 확보(없으면 생성)
        if not job.result:
            r = Result(job_id=job.id, analysis_json={}, coaching_text="", coaching_json=None)
            db.add(r)
            db.commit()
            db.refresh(job)
        result = job.result

        # ---------------------------------------------------------
        # 1) (선택) 트랜스코딩: iPhone MOV/HEVC 대응
        # ---------------------------------------------------------
        try:
            dst_key = f"videos/{video.id}/transcoded.mp4"
            # video.object_key 없으면 여기서 터지므로 getattr로 방어
            src_key = getattr(video, "object_key", None)
            if src_key:
                transcode_to_mp4(src_key, dst_key)
                # 모델에 컬럼이 있을 때만 저장
                if hasattr(video, "transcoded_object_key"):
                    video.transcoded_object_key = dst_key
                db.commit()
        except Exception:
            pass

        job.progress = 15
        db.commit()

        # ---------------------------------------------------------
        # 2) 분석 생성 (pose+heuristics)
        # ---------------------------------------------------------
        analysis_key = getattr(video, "transcoded_object_key", None) or getattr(video, "object_key", None)
        filename = getattr(video, "filename", None)

        if not analysis_key:
            raise RuntimeError("video.object_key 가 없습니다.")

        video_bytes = get_object_bytes(analysis_key)

        analysis_json = run_pose_and_feature_analysis(
            video_bytes=video_bytes,
            analysis_key=analysis_key,
            filename=filename,
            video_id=getattr(video, "id", None),
            transcoded_object_key=getattr(video, "transcoded_object_key", None),
            sport=video.sport or "ski",
            level=video.level or "intermediate",
            sample_fps=2.0,
            max_seconds=25.0,
        )

        # ✅ public_url 세팅
        bucket = settings.MINIO_BUCKET
        public_base = settings.MINIO_PUBLIC_ENDPOINT
        video_key = getattr(video, "transcoded_object_key", None) or getattr(video, "object_key", None)

        analysis_json["video"] = {
            "object_key": getattr(video, "object_key", None),
            "transcoded_object_key": getattr(video, "transcoded_object_key", None),
            "public_url": f"{public_base}/{bucket}/{video_key}" if video_key else None,
        }

        # ✅ issues_seed 생성 (LLM 이전에 확정 이슈 만들기)

        issues_seed = segments_to_issues_seed(analysis_json, max_items=6)
        issues_seed = dedup_issues_seed(issues_seed, max_items=6)
        analysis_json.setdefault("signals", {})
        analysis_json["signals"]["issues_seed"] = issues_seed

        result.analysis_json = analysis_json
        db.commit()

        job.progress = 35
        db.commit()

        # ---------------------------------------------------------
        # 3) RAG 검색
        # ---------------------------------------------------------
        raw_summary = _analysis_summary_text(analysis_json)

        retrieved = retrieve(sport=video.sport or "ski", query=raw_summary, top_k=5)
        rag_chunks: List[Dict[str, Any]] = [
            {
                "content": c.content,
                "source": c.source,
                "score": float(c.score),
                "page": int(getattr(c, "page", 0) or 0),
            }
            for c in retrieved
        ]

        # ✅ 프론트에서 RAG 컨텍스트 표시하려면 반드시 저장(컬럼 있을 때만)
        if hasattr(result, "rag_context"):
            result.rag_context = {"query": raw_summary, "chunks": rag_chunks}
            db.commit()

        job.progress = 55
        db.commit()

        # ---------------------------------------------------------
        # 4) LLM 코칭 (issues_seed 기반 확장)
        # ---------------------------------------------------------
        analysis_summary = compact_analysis_for_llm(result.analysis_json, max_chars=320)
        rag_block = compact_rag_chunks_for_llm(rag_chunks, max_chunks=2, max_chars_each=220)

        prompt = build_ski_prompt_v2(
            level=(video.level or "intermediate"),
            analysis_summary=analysis_summary,
            issues_seed = issues_seed[:4],  # ✅ 원본 리스트 그대로
            rag_block=rag_block,
        )

        llm_text = generate_coaching(prompt)

        # LLM 원문 저장(디버그)
        result.coaching_text = llm_text
        db.commit()

        # JSON 파싱
        coaching_json: Any = None
        try:
            coaching_json = extract_json(llm_text)
        except Exception as e:
            coaching_json = None
            # 파싱 실패 사유는 debug로 남김
            try:
                result.coaching_json = {
                    "debug": {
                        "extract_json_error": str(e),
                        "llm_head": (llm_text or "")[:200],
                    }
                }
                db.commit()
            except Exception:
                pass

        # ✅ 형태 보정 + issues_seed 기반 강제 정합
        coaching_json = _ensure_coaching_json_shape(
            coaching_json,
            level=(video.level or "intermediate"),
            analysis_summary=analysis_summary,
            rag_chunks=rag_chunks,
            issues_seed=issues_seed,
        )

        # ✅ timecode_sec 후처리(segments 기반 정교화)
        # enforce_timecodes가 dict 아닌 입력을 싫어하면 위에서 이미 dict로 보정됨
        try:
            coaching_json = enforce_timecodes(coaching_json, result.analysis_json)
        except Exception:
            pass

        result.coaching_json = coaching_json
        db.commit()

        job.status = "done"
        job.progress = 100
        db.commit()

    except Exception as e:
        job = db.get(Job, job_id)
        if job:
            job.status = "failed"
            job.error = str(e)
            db.commit()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------
# Manual Reindex Task
# ---------------------------------------------------------------------

@shared_task(bind=True)
def reindex_manual_job(self, manual_id: int):
    db: Session = SessionLocal()
    try:
        m = db.get(Manual, manual_id)
        if not m:
            return

        print(f"[reindex] start manual_id={manual_id}")
        print(f"[reindex] object_key={m.object_key} sport={m.sport} version={m.version}")

        # 기존 청크 삭제
        print("[reindex] deleting old chunks...")
        db.execute(delete(ManualChunk).where(ManualChunk.manual_id == manual_id))
        db.commit()
        print("[reindex] delete committed")

        # PDF 다운로드
        print("[reindex] downloading pdf from minio...")
        pdf_bytes = get_object_bytes(m.object_key)
        print(f"[reindex] pdf_bytes={len(pdf_bytes)}")

        # 텍스트 추출/청킹
        print("[reindex] extracting text per page...")
        pages = extract_text_per_page(pdf_bytes)
        non_empty = sum(1 for p in pages if p.get("text"))
        print(f"[reindex] pages={len(pages)} non_empty={non_empty}")

        print("[reindex] chunking...")
        chunks = chunk_text(pages, max_chars=1200, overlap=150)
        print(f"[reindex] chunks={len(chunks)}")

        texts = [c["text"] for c in chunks]
        metas = [c["meta"] for c in chunks]

        # 임베딩 (배치)
        BATCH = 16
        print("[reindex] embedding...")

        for i in range(0, len(texts), BATCH):
            batch_texts = texts[i : i + BATCH]
            batch_metas = metas[i : i + BATCH]

            vecs = _embed_texts_compat(batch_texts, is_query=False)

            for t, v, meta in zip(batch_texts, vecs, batch_metas):
                db.add(
                    ManualChunk(
                        manual_id=m.id,
                        sport=m.sport,
                        version=m.version,
                        chunk_text=t,
                        meta=meta,
                        embedding=v,
                    )
                )

            db.commit()
            print(f"[reindex] embedded {min(i+BATCH, len(texts))}/{len(texts)}")

        print("[reindex] done")
    finally:
        db.close()