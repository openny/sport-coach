from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _mid(seg: Dict[str, Any]) -> float:
    st = float(seg.get("start_sec") or 0.0)
    ed = float(seg.get("end_sec") or 0.0)
    return (st + ed) / 2.0 if ed > st else st


def _best_segment_for_issue(segments: List[Dict[str, Any]], issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    간단 매핑:
    - issue.id/title/why 텍스트에 tag가 포함되면 그 tag 중 score 높은 것
    - 아니면 score 높은 것 1개
    """
    if not segments:
        return None

    text = " ".join(
        [str(issue.get("id") or ""), str(issue.get("title") or ""), str(issue.get("why") or "")]
    ).lower()

    # tag 힌트 찾기
    tagged = []
    for s in segments:
        tag = str(s.get("tag") or "").lower()
        if tag and tag in text:
            tagged.append(s)

    cand = tagged if tagged else segments

    def score(x: Dict[str, Any]) -> float:
        try:
            return float(x.get("score") or 0.0)
        except Exception:
            return 0.0

    cand = sorted(cand, key=score, reverse=True)
    return cand[0] if cand else None


def enforce_timecodes(coaching_json: Dict[str, Any], analysis_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    ✅ timecode_sec=0 또는 누락이면 segments의 mid로 무조건 채운다.
    """
    if not isinstance(coaching_json, dict):
        return coaching_json

    segs = (((analysis_json or {}).get("signals") or {}).get("segments") or [])
    if not isinstance(segs, list):
        segs = []

    issues = coaching_json.get("issues")
    if not isinstance(issues, list):
        issues = []
        coaching_json["issues"] = issues

    for issue in issues:
        if not isinstance(issue, dict):
            continue
        tc = issue.get("timecode_sec")
        try:
            tc_val = float(tc)
        except Exception:
            tc_val = 0.0

        if tc_val <= 0.0 and segs:
            best = _best_segment_for_issue(segs, issue) or segs[0]
            issue["timecode_sec"] = float(_mid(best))

    # rag.used 없으면 기본 true
    rag = coaching_json.get("rag")
    if not isinstance(rag, dict):
        coaching_json["rag"] = {"used": True, "citations": []}

    return coaching_json