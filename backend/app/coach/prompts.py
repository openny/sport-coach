# app/coach/prompts.py
from __future__ import annotations
from typing import Any, Dict, List
import json

def _truncate(s: str, max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def compact_analysis_for_llm(analysis_json: Dict[str, Any], max_chars: int = 650) -> str:
    if not isinstance(analysis_json, dict):
        return ""
    summary = str(analysis_json.get("summary") or "")
    return _truncate(summary, max_chars)

def compact_rag_chunks_for_llm(rag_chunks: List[Dict[str, Any]], max_chunks=4, max_chars_each=360) -> str:
    chunks = (rag_chunks or [])[:max_chunks]
    lines = []
    for i, c in enumerate(chunks, start=1):
        src = c.get("source") or "manual"
        page = int(c.get("page") or 0)
        score = float(c.get("score") or 0.0)
        content = (c.get("content") or "")[:max_chars_each]
        lines.append(f"[RAG-{i}] source={src} page={page} score={score:.3f}\n{content}")
    return "\n\n".join(lines) if lines else "(RAG 없음)"

def compact_issues_seed_for_llm(issues_seed: List[Dict[str, Any]], max_items=6) -> str:
    seed = (issues_seed or [])[:max_items]
    # JSON 그대로 주는 게 LLM이 덜 헷갈림
    minimal = []
    for x in seed:
        minimal.append({
            "id": x.get("id"),
            "tag": x.get("tag"),
            "title": x.get("title"),
            "severity": x.get("severity"),
            "timecode_sec": x.get("timecode_sec"),
            "start_sec": x.get("start_sec"),
            "end_sec": x.get("end_sec"),
            "score": x.get("score"),
            "why": x.get("why"),
            "hints": x.get("hints", {}),
        })
    return json.dumps(minimal, ensure_ascii=False)

def build_ski_prompt_v2(
    *,
    level: str,
    analysis_summary: str,
    issues_seed: List[Dict[str, Any]],
    rag_block: str,
) -> str:
    """
    v2: issues_seed(포즈/규칙 기반 확정 이슈)를 LLM이 설명/큐/드릴/교본근거로 확장하는 프롬프트.
    - issues_seed의 id/title/severity/timecode(start_sec)는 절대 변경 금지
    - 출력은 JSON "만" (코드블록/설명/마크다운 금지)
    """

    # ✅ LLM이 흔들리지 않게 issues_seed를 JSON으로 고정해서 넣는다.
    #    (compact_issues_seed_for_llm을 써도 되지만, 여기선 원본 구조를 최대한 유지)
    #    필요하면 issues_seed를 더 줄여서 넣는 전처리(상위 N개 등)는 호출부에서 처리.
    issues_seed_json = json.dumps(issues_seed, ensure_ascii=False)

    # ✅ rag_block 유무를 모델이 헷갈리지 않게 명시
    rag_used = "true" if (rag_block and rag_block.strip() and rag_block.strip() != "(RAG 없음)") else "false"

    # ✅ level별 난이도 지시를 명시 (중요!)
    level_policy = f"""
[레벨 정책]
- beginner: 용어 최소화, "지금 당장 할 1~2개" 중심, 안전 강조, 드릴은 쉬운 것 위주
- intermediate: 원인/결과(엣지-압력-타이밍) 연결 설명, 큐 2~3개 + 드릴 2개, 잘못된 보상동작도 언급
- advanced: 미세 조정(압력 이동 타이밍/상체 고정/하체 독립), 드릴은 난이도 있는 변형 포함
현재 레벨 = {level}
""".strip()

    # ✅ 출력 스키마: 프론트가 바로 렌더링 가능한 필드명으로 통일
    schema = r"""
출력은 오직 JSON 1개만. 절대 코드블록(```) 금지, 마크다운 금지, 설명 금지.
첫 글자는 반드시 {, 마지막 글자는 반드시 } 로 끝내.

반드시 아래 스키마를 지켜라:

{
  "summary": {
    "level": "beginner|intermediate|advanced",
    "one_liner": "한 줄 요약",
    "highlights": ["핵심 1", "핵심 2", "핵심 3"],
    "top_priority": "가장 먼저 고칠 1가지",
    "overall_score": 0
  },
  "issues": [
    {
      "id": "issues_seed의 id 그대로",
      "title": "issues_seed의 title 그대로",
      "severity": "issues_seed의 severity 그대로",
      "timecode_sec": 0.0,
      "why": "왜 중요한지 (안전/효율/컨트롤) — 영상 신호 기반으로 구체적으로",
      "how_to_fix": ["바로 적용 큐 1", "큐 2", "큐 3"],
      "drills": ["드릴 1", "드릴 2"],
      "textbook_basis": {
        "claims": ["교본 원칙 1", "원칙 2"],
        "citations": [
          {"source": "manual:... p....", "preview": "근거 발췌(짧게)", "page": 0, "score": 0.0}
        ]
      }
    }
  ],
  "rag": {
    "used": true,
    "citations": [
      {"source": "manual:... p....", "page": 0, "score": 0.0, "preview": "짧은 발췌"}
    ]
  },
  "extra_drills": ["추가 드릴 1"],
  "safety_notes": ["안전 1"],
  "next_session_plan": ["다음 세션 목표 1"]
}

핵심 규칙(절대 위반 금지):
1) issues 배열 길이는 issues_seed 배열 길이와 정확히 같아야 한다. (추가/삭제/재정렬 금지)
2) 각 issue의 id/title/severity 는 issues_seed의 값을 그대로 복사한다.
3) 각 issue의 timecode_sec 는 issues_seed의 start_sec 값을 그대로 사용한다. (소수 유지 가능)
4) why/how_to_fix/drills/textbook_basis만 너가 새로 채운다.
5) rag.used가 false이면 rag.citations는 [] 로 출력한다.
6) rag.used가 true이면 rag.citations는 RAG 블록의 근거를 요약해서 최대 5개로 넣는다.
7) citations.page/score는 RAG 블록에서 제공된 page/score를 그대로 사용하라. 없으면 0.
8) 한국어로 작성하되, 특정 기술 용어(엣지/압력/센터/카빙 등)는 혼용 가능.
""".strip()

    # ✅ analysis_summary는 이미 compact된 값이 들어오는 걸 권장 (호출부에서 max_chars 제한)
    # ✅ rag_block도 compact된 문자열이 들어오는 걸 권장

    prompt = f"""
너는 "스키 AI 코치"다. 비난 금지. 레벨 정책을 반드시 따른다.
중요: 아래 issues_seed는 포즈+규칙 기반으로 검출된 '확정 이슈'다.
너의 역할은 이 확정 이슈를 설명(why) + 즉시 적용 큐(how_to_fix) + 드릴(drills) + 교본 근거(textbook_basis)로 확장하는 것이다.

{level_policy}

[영상 분석 요약]
{analysis_summary}

[issues_seed JSON (절대 수정/추가/삭제/재정렬 금지)]
{issues_seed_json}

[교본 발췌(RAG)]
{rag_block if (rag_block and rag_block.strip()) else "(RAG 없음)"}

[RAG 사용 여부]
rag.used = {rag_used}

{schema}
""".strip()

    return prompt