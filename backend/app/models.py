from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from .db import Base
from datetime import datetime

class Video(Base):
    __tablename__ = "videos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sport: Mapped[str] = mapped_column(String(20), index=True)
    level: Mapped[str] = mapped_column(String(20), default="intermediate")
    filename: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    transcoded_object_key = mapped_column(Text, nullable=True)
    jobs: Mapped[list["Job"]] = relationship(back_populates="video")

class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    video: Mapped["Video"] = relationship(back_populates="jobs")
    result: Mapped["Result"] = relationship(back_populates="job", uselist=False)

class Result(Base):
    __tablename__ = "results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True)
    analysis_json: Mapped[dict] = mapped_column(JSON)
    coaching_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["Job"] = relationship(back_populates="result")
    coaching_json: Mapped[dict] = mapped_column(JSON, default={})
    rag_context = mapped_column(JSON, nullable=True)

class Manual(Base):
    __tablename__ = "manuals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sport: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(50), default="v1")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/inactive
    object_key: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ManualChunk(Base):
    __tablename__ = "manual_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manual_id: Mapped[int] = mapped_column(ForeignKey("manuals.id"), index=True)
    sport: Mapped[str] = mapped_column(String(20), index=True)
    version: Mapped[str] = mapped_column(String(50), index=True)
    chunk_text: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON)
    # MVP: JSON embedding(추후 pgvector VECTOR로 교체 권장)
    embedding: Mapped[list[float]] = mapped_column(JSON)
