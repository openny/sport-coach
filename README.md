# Ski Coach MVP (Local Docker)

로컬에서 **스키 1종목 MVP**(영상 업로드 → 포즈/룰 분석 → RAG(교본) → LLM 코칭 → 결과 UI)를 end-to-end로 테스트할 수 있는 템플릿입니다.

## 구성
- Backend: FastAPI + Celery + Postgres + Redis + MinIO
- Analysis: MediaPipe Pose 기반 MVP 피처/이슈 탐지(룰 v1)
- RAG: PDF 업로드 → 청킹 → 임베딩(sentence-transformers) → 간단 cosine 검색(MVP)
- LLM: Ollama 기본(또는 OpenAI-compatible endpoint)
- Frontend: React(Vite) 업로드/진행/결과/어드민

## 실행
```bash
docker compose up --build
```

### URL
- Frontend: http://localhost:5173
- Backend Swagger: http://localhost:8000/docs
- MinIO console: http://localhost:9001 (minio / minio123456)

## 사용 순서
1) (어드민) 교본 PDF 업로드 → 임베딩 재생성
2) (사용자) 영상 업로드 → 분석 시작 → 결과 확인

## Ollama 모델 받기(선택)
```bash
curl http://localhost:11434/api/pull -d '{"name":"qwen2.5:14b-instruct-q4_K_M"}'
```

## 참고
- MVP는 pgvector VECTOR 컬럼 대신 embedding을 JSON으로 저장합니다. 이후 단계에서 pgvector 컬럼으로 쉽게 전환 가능하도록 인터페이스를 유지했습니다.
