import os
import uvicorn
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from .models import ManualChunk
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from .db import Base, engine, get_db
from .models import Video, Job, Manual
from .schemas import (
    VideoCreateResp,
    AnalyzeReq,
    JobStatusResp,
    ResultResp,
    ManualUploadResp,
    ManualReindexResp,
    JobOut,
    ManualOut,
    ManualChunksStats,
)
from .storage import put_object_bytes
from .tasks import run_analysis_job, reindex_manual_job


# -------------------------
# helpers
# -------------------------
def build_minio_public_url(object_key: str) -> str:
    """
    object_key: videos/{video_id}/{filename} 형태 권장.
    MINIO_PUBLIC=http://localhost:9000
    버킷명은 videos로 고정(현재 mc에서 local/videos public 설정된 것으로 보임)
    """
    base = os.getenv("MINIO_PUBLIC", "http://localhost:9000").rstrip("/")
    key = object_key.lstrip("/")

    # object_key가 이미 videos/... 형태면 그대로 bucket prefix 제거
    if key.startswith("videos/"):
        key = key[len("videos/") :]

    # 최종: http://localhost:9000/videos/{rest}
    return f"{base}/videos/{key}"


app = FastAPI(title="Ski Coach MVP")

# ✅ 프론트 dev 주소 넓힘 (필요하면 더 추가)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


# -------------------------
# videos
# -------------------------
@app.post("/v1/videos", response_model=VideoCreateResp)
async def create_video(filename: str, db: Session = Depends(get_db)):
    """
    ✅ 안정화: object_key 를 videos/{video_id}/{filename} 로 만들기 위해
    1) 일단 Video row 생성 후 id 확보
    2) object_key 업데이트
    """
    # 1) 먼저 row 생성 (임시 object_key)
    video = Video(sport="ski", level="intermediate", filename=filename, object_key="tmp")
    db.add(video)
    db.commit()
    db.refresh(video)

    # 2) id 기반 object_key 안정화
    object_key = f"videos/{video.id}/{filename}"
    video.object_key = object_key
    db.commit()
    db.refresh(video)

    return VideoCreateResp(
        video_id=video.id,
        upload_url=f"/v1/videos/{video.id}/upload",
        object_key=object_key,
    )


@app.post("/v1/videos/{video_id}/upload")
async def upload_video(video_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "video not found")

    data = await file.read()

    # ✅ content-type이 비어있으면 mp4로 넣되, MOV 업로드도 허용
    content_type = file.content_type or "video/mp4"

    put_object_bytes(video.object_key, data, content_type)
    return {"ok": True, "video_id": video_id}


@app.get("/v1/videos/{video_id}")
def get_video_meta(video_id: int, db: Session = Depends(get_db)):
    """
    ✅ 프론트가 video player에 넣을 URL이 필요해서 추가.
    public 버킷이면 public_url로 바로 재생 가능.
    """
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "video not found")

    public_url = build_minio_public_url(video.object_key) if video.object_key else None

    return {
        "video_id": video.id,
        "filename": video.filename,
        "object_key": video.object_key,
        "public_url": public_url,
        "sport": getattr(video, "sport", None),
        "level": getattr(video, "level", None),
    }


@app.post("/v1/videos/{video_id}/analyze", response_model=JobStatusResp)
def analyze(video_id: int, req: AnalyzeReq, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "video not found")

    video.sport = req.sport
    video.level = req.level

    job = Job(video_id=video_id, status="queued", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)

    run_analysis_job.delay(job.id)

    # ✅ 프론트 편의를 위해 video_id도 같이 내려줘도 좋지만
    # 기존 스키마(JobStatusResp)에 필드가 없으면 일단 유지
    return JobStatusResp(job_id=job.id, status=job.status, progress=job.progress)


# -------------------------
# jobs
# -------------------------
@app.get("/v1/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobOut(
        job_id=job.id,
        video_id=job.video_id,
        status=job.status,
        progress=job.progress,
        error=job.error,
    )


# -------------------------
# results
# -------------------------
@app.get("/v1/videos/{video_id}/result", response_model=ResultResp)
def get_result(video_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.video_id == video_id).order_by(Job.id.desc()).first()
    if not job or not job.result:
        raise HTTPException(404, "result not ready")

    return ResultResp(
        analysis=job.result.analysis_json,
        coaching_text=job.result.coaching_text,
        coaching_json=getattr(job.result, "coaching_json", None),
        rag_context=getattr(job.result, "rag_context", None),
    )


# -------------------------
# manuals (admin)
# -------------------------
@app.post("/v1/admin/manuals", response_model=ManualUploadResp)
async def upload_manual(
    sport: str,
    title: str,
    version: str = "v1",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    object_key = f"manuals/{sport}/{version}/{file.filename}"
    data = await file.read()
    put_object_bytes(object_key, data, file.content_type or "application/pdf")

    manual = Manual(sport=sport, title=title, version=version, status="active", object_key=object_key)
    db.add(manual)
    db.commit()
    db.refresh(manual)

    return ManualUploadResp(manual_id=manual.id)


@app.post("/v1/admin/manuals/{manual_id}/reindex", response_model=ManualReindexResp)
def reindex_manual(manual_id: int):
    reindex_manual_job.delay(manual_id)
    return ManualReindexResp(ok=True)



@app.get("/v1/admin/manuals", response_model=List[ManualOut])
def list_manuals(sport: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Manual).order_by(Manual.id.desc())
    if sport:
        q = q.filter(Manual.sport == sport)
    items = q.limit(100).all()
    return [
        ManualOut(
            id=m.id,
            sport=m.sport,
            title=m.title,
            version=m.version,
            status=m.status,
            object_key=m.object_key,
            created_at=m.created_at,
        )
        for m in items
    ]

@app.get("/v1/admin/manuals/{manual_id}/chunks", response_model=ManualChunksStats)
def manual_chunks_stats(manual_id: int, db: Session = Depends(get_db)):
    n = db.query(func.count(ManualChunk.id)).filter(ManualChunk.manual_id == manual_id).scalar() or 0
    return ManualChunksStats(manual_id=manual_id, chunks=int(n))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)