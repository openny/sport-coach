from pydantic import BaseModel
from datetime import datetime
from typing import Literal, Optional, Any, Dict

Sport = Literal["ski", "snowboard", "golf", "running"]
Level = Literal["beginner", "intermediate", "advanced"]

class VideoCreateResp(BaseModel):
    video_id: int
    upload_url: str
    object_key: str

class AnalyzeReq(BaseModel):
    sport: Sport
    level: Level = "intermediate"

class JobStatusResp(BaseModel):
    job_id: int
    status: str
    progress: int
    error: Optional[str] = None

class ResultResp(BaseModel):
    analysis: Dict[str, Any]
    coaching_text: str
    coaching_json: Optional[Dict[str, Any]] = None
    rag_context: Optional[Dict[str, Any]] = None

class ManualUploadResp(BaseModel):
    manual_id: int

class ManualReindexResp(BaseModel):
    ok: bool

class JobOut(BaseModel):
    job_id: int
    video_id: int
    status: str
    progress: int
    error: Optional[str] = None

    class Config:
        from_attributes = True


class VideoMetaOut(BaseModel):
    video_id: int
    filename: Optional[str] = None
    object_key: Optional[str] = None
    public_url: Optional[str] = None

    class Config:
        from_attributes = True

class ManualOut(BaseModel):
    id: int
    sport: str
    title: str
    version: str
    status: str
    object_key: str
    created_at: Optional[datetime] = None

class ManualChunksStats(BaseModel):
    manual_id: int
    chunks: int