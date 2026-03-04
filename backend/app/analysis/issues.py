# app/analysis/issues.py
from __future__ import annotations
from typing import Any, Dict, List

TAG_MAP: Dict[str, Dict[str, str]] = {
    "forward_lean": {
        "title": "상체 과전경(앞으로 숙임)",
        "why": "상체가 과도하게 앞으로 기울면 중심이 앞/안쪽으로 무너져 엣지 전환이 늦고 턴 후반에 급하게 버티는 패턴이 나올 수 있습니다.",
        "top_cues": "갈비뼈를 골반 위에 쌓고(상체-골반 스택), 정강이를 부츠 텅에 '가볍게' 유지하세요.",
        "drills": "가랜드(half-turn), 사이드슬립에서 상체 고정, J턴"
    },
    "knee_too_straight": {
        "title": "무릎 과신전(너무 펴짐)",
        "why": "무릎이 너무 펴지면 충격흡수와 압력조절이 어려워 턴이 딱딱해지고, 바깥스키 압력 전달이 끊기기 쉽습니다.",
        "top_cues": "발목-무릎-골반을 부드럽게 굴곡 유지(스프링처럼), 턴 진입 때 무릎을 '살짝' 더 넣어주세요.",
        "drills": "범프 없이도 업다운(미세), 트래버스-압력유지, 슬로우 카빙"
    },
    "knee_too_deep": {
        "title": "무릎 과도 굴곡(너무 앉음)",
        "why": "과도한 스쿼트는 다음 턴 전환을 느리게 만들고, 상체가 뒤로 빠지며 스키 팁이 떠서 조향이 불안정해질 수 있습니다.",
        "top_cues": "무릎만 접지 말고 발목/엉덩이로 분산, '앉기' 대신 '앞으로 길게' 서세요.",
        "drills": "폴플랜트 리듬, 롱턴에서 자세 높이 일정, 원풋 슬라이드(안전 범위)"
    },
    "hip_sway": {
        "title": "좌우 밸런스 흔들림(힙 스웨이)",
        "why": "골반이 좌우로 흔들리면 중심이 스키 위에 안정적으로 쌓이지 않아 엣지 각/압력 타이밍이 매 턴 달라질 수 있습니다.",
        "top_cues": "골반은 진행방향에 안정, 하체만 회전/엣지. '배꼽을 슬로프 아래로' 유지하세요.",
        "drills": "레일로드 트랙(가벼운 카빙), 원턴-원턴 멈춤, 폴 없이 팔 앞으로 고정"
    },
}

def _severity(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"

def segments_to_issues_seed(analysis_json: Dict[str, Any], max_items: int = 6) -> List[Dict[str, Any]]:
    segs = (analysis_json.get("signals") or {}).get("segments") or []
    if not isinstance(segs, list):
        return []

    # score 높은 순으로 우선
    segs = sorted(segs, key=lambda s: float(s.get("score") or 0.0), reverse=True)[:max_items]

    out: List[Dict[str, Any]] = []
    for i, s in enumerate(segs, start=1):
        tag = str(s.get("tag") or "unknown")
        m = TAG_MAP.get(tag, {})
        start = float(s.get("start_sec") or 0.0)
        end = float(s.get("end_sec") or start)
        score = float(s.get("score") or 0.0)

        out.append({
            "id": f"{tag}-{i}",
            "tag": tag,
            "title": m.get("title", tag),
            "severity": _severity(score),
            "timecode_sec": start,          # ✅ 영상 seek 기본값
            "start_sec": start,
            "end_sec": end,
            "score": score,
            "why": m.get("why", "자세 변동이 감지되었습니다."),
            "hints": {
                "top_cues": m.get("top_cues", ""),
                "drills": m.get("drills", "")
            }
        })
    return out