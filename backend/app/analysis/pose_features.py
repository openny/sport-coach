from __future__ import annotations

import math
import os
import tempfile
import subprocess
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import cv2  # opencv-python
except Exception:
    cv2 = None

try:
    import mediapipe as mp  # mediapipe
except Exception:
    mp = None

from app.storage import get_object_bytes
from app.config import settings


def _angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """
    각도 ABC (b가 꼭짓점) 를 degree로 반환
    """
    ba = a - b
    bc = c - b
    nba = np.linalg.norm(ba) + 1e-9
    nbc = np.linalg.norm(bc) + 1e-9
    cosv = float(np.dot(ba, bc) / (nba * nbc))
    cosv = max(-1.0, min(1.0, cosv))
    return float(math.degrees(math.acos(cosv)))


def _deg_from_vertical(v: np.ndarray) -> float:
    """
    벡터 v가 수직(0, -1)과 이루는 각(도).
    이미지 좌표계(y가 아래로 증가) 기준.
    """
    vertical = np.array([0.0, -1.0], dtype=np.float32)
    nv = np.linalg.norm(v) + 1e-9
    cosv = float(np.dot(v, vertical) / nv)
    cosv = max(-1.0, min(1.0, cosv))
    ang = float(math.degrees(math.acos(cosv)))
    return ang


def _merge_segments(raw: List[Dict[str, Any]], gap_sec: float = 0.4) -> List[Dict[str, Any]]:
    """
    인접한 구간을 합침 (gap_sec 이하로 끊기면 붙임)
    raw items: {start_sec, end_sec, tag, score}
    """
    if not raw:
        return []
    raw = sorted(raw, key=lambda x: (x["tag"], x["start_sec"]))
    out: List[Dict[str, Any]] = []
    cur = raw[0].copy()

    for s in raw[1:]:
        if s["tag"] == cur["tag"] and s["start_sec"] <= cur["end_sec"] + gap_sec:
            cur["end_sec"] = max(cur["end_sec"], s["end_sec"])
            cur["score"] = float(max(cur.get("score", 0.0), s.get("score", 0.0)))
        else:
            out.append(cur)
            cur = s.copy()
    out.append(cur)

    # 너무 짧은 구간 제거
    out2 = []
    for s in out:
        if (s["end_sec"] - s["start_sec"]) >= 0.6:
            out2.append(s)
    return out2


def _ffmpeg_transcode_to_mp4(src_path: str, dst_path: str) -> None:
    """
    iPhone MOV(HEVC) 같은 경우를 대비해 mp4(h264+aac)로 변환
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", src_path,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        dst_path,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_pose_and_feature_analysis(
    video: Any = None,
    *,
    # ✅ 새 호출 방식(권장): tasks.py에서 bytes + key를 넘겨준다
    video_bytes: Optional[bytes] = None,
    analysis_key: Optional[str] = None,          # object_key 또는 transcoded key
    filename: Optional[str] = None,
    video_id: Optional[int] = None,
    transcoded_object_key: Optional[str] = None, # 없으면 None
    sport: str = "ski",
    level: str = "intermediate",
    sample_fps: float = 2.0,
    max_seconds: float = 25.0,
) -> Dict[str, Any]:
    """
    ✅ ORM(Video) 의존 제거 버전 (호환 유지)
    - (권장) video_bytes + analysis_key 로 호출
    - (호환) video 객체를 주면 object_key/filename/id를 getattr로 읽어서 처리
    - MinIO에서 다운로드(필요 시) -> 임시 파일 저장 -> (가능하면) mp4 트랜스코딩
    - mediapipe pose로 keypoints 추정
    - feature 계산 후 segments 생성
    """

    if cv2 is None:
        raise RuntimeError("opencv-python이 설치되어 있지 않습니다. (pip install opencv-python)")
    if mp is None:
        raise RuntimeError("mediapipe가 설치되어 있지 않습니다. (pip install mediapipe)")

    # -----------------------------
    # 0) 입력 정리 (호환 포함)
    # -----------------------------
    if analysis_key is None and video is not None:
        analysis_key = getattr(video, "transcoded_object_key", None) or getattr(video, "object_key", None)

    if filename is None and video is not None:
        filename = getattr(video, "filename", None)

    if video_id is None and video is not None:
        video_id = getattr(video, "id", None)

    if transcoded_object_key is None and video is not None:
        transcoded_object_key = getattr(video, "transcoded_object_key", None)

    if not analysis_key:
        raise RuntimeError("analysis_key(object_key)가 없습니다. tasks.py에서 analysis_key를 넘겨주세요.")

    if not filename:
        filename = os.path.basename(analysis_key)

    # MinIO 공개 URL (디버그/프론트 미리보기용)
    public_url = f"{settings.MINIO_PUBLIC_ENDPOINT}/{settings.MINIO_BUCKET}/{analysis_key}"

    # bytes가 없으면 MinIO에서 가져옴
    if video_bytes is None:
        video_bytes = get_object_bytes(analysis_key)

    # -----------------------------
    # 1) 파일로 저장 + 트랜스코딩 시도
    # -----------------------------
    with tempfile.TemporaryDirectory() as td:
        src_path = os.path.join(td, "src.bin")
        with open(src_path, "wb") as f:
            f.write(video_bytes)

        mp4_path = os.path.join(td, "video.mp4")
        try:
            _ffmpeg_transcode_to_mp4(src_path, mp4_path)
            cap_path = mp4_path
        except Exception:
            cap_path = src_path

        cap = cv2.VideoCapture(cap_path)
        if not cap.isOpened():
            raise RuntimeError("비디오를 열 수 없습니다. (코덱/ffmpeg 문제 가능)")

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = (total_frames / fps) if (fps > 0 and total_frames > 0) else 0.0

        end_sec = min(max_seconds, duration if duration > 0 else max_seconds)
        frame_step = max(1, int(round(fps / sample_fps)))

        mp_pose = mp.solutions.pose
        pose = mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        keypoints_ts: List[Dict[str, Any]] = []
        feats_ts: List[Dict[str, Any]] = []

        def get_lm(lms, idx) -> Optional[np.ndarray]:
            if lms is None:
                return None
            try:
                lm = lms.landmark[idx]
                return np.array([lm.x, lm.y, lm.visibility], dtype=np.float32)
            except Exception:
                return None

        # mediapipe landmark indices
        L_SHO = 11
        R_SHO = 12
        L_HIP = 23
        R_HIP = 24
        L_KNE = 25
        R_KNE = 26
        L_ANK = 27
        R_ANK = 28

        cur_frame = 0
        last_t = None

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if cur_frame % frame_step != 0:
                cur_frame += 1
                continue

            t_sec = cur_frame / fps
            if t_sec > end_sec:
                break
            last_t = float(t_sec)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = pose.process(rgb)
            lms = res.pose_landmarks

            l_sho = get_lm(lms, L_SHO)
            r_sho = get_lm(lms, R_SHO)
            l_hip = get_lm(lms, L_HIP)
            r_hip = get_lm(lms, R_HIP)
            l_kne = get_lm(lms, L_KNE)
            r_kne = get_lm(lms, R_KNE)
            l_ank = get_lm(lms, L_ANK)
            r_ank = get_lm(lms, R_ANK)

            if l_sho is None or r_sho is None or l_hip is None or r_hip is None:
                cur_frame += 1
                continue

            sho_c = (l_sho[:2] + r_sho[:2]) / 2.0
            hip_c = (l_hip[:2] + r_hip[:2]) / 2.0

            trunk_v = sho_c - hip_c
            trunk_angle = _deg_from_vertical(trunk_v)

            lknee = None
            rknee = None
            if l_hip is not None and l_kne is not None and l_ank is not None:
                lknee = _angle_deg(l_hip[:2], l_kne[:2], l_ank[:2])
            if r_hip is not None and r_kne is not None and r_ank is not None:
                rknee = _angle_deg(r_hip[:2], r_kne[:2], r_ank[:2])

            hip_sway = float(hip_c[0] - 0.5)
            vis = float(np.mean([l_sho[2], r_sho[2], l_hip[2], r_hip[2]]))

            keypoints_ts.append(
                {
                    "t": float(t_sec),
                    "sho": {"x": float(sho_c[0]), "y": float(sho_c[1])},
                    "hip": {"x": float(hip_c[0]), "y": float(hip_c[1])},
                    "vis": vis,
                }
            )
            feats_ts.append(
                {
                    "t": float(t_sec),
                    "trunk_angle_deg": float(trunk_angle),
                    "knee_left_deg": float(lknee) if lknee is not None else None,
                    "knee_right_deg": float(rknee) if rknee is not None else None,
                    "hip_sway": float(hip_sway),
                    "vis": vis,
                }
            )

            cur_frame += 1

        cap.release()
        pose.close()

    # -----------------------------
    # 2) segments 생성(룰 기반)
    # -----------------------------
    raw_segments: List[Dict[str, Any]] = []

    FORWARD_LEAN_DEG = 25.0
    TOO_STRAIGHT_KNEE = 160.0
    TOO_DEEP_KNEE = 110.0
    HIP_SWAY_BIG = 0.10

    def mark(tag: str, start: float, end: float, score: float):
        raw_segments.append({"tag": tag, "start_sec": float(start), "end_sec": float(end), "score": float(score)})

    active: Dict[str, Dict[str, float]] = {}

    for f in feats_ts:
        t = float(f["t"])

        # forward lean
        if f["trunk_angle_deg"] is not None and f["trunk_angle_deg"] > FORWARD_LEAN_DEG and f["vis"] > 0.4:
            active.setdefault("forward_lean", {"start": t, "max": 0.0})
            active["forward_lean"]["max"] = max(active["forward_lean"]["max"], float(f["trunk_angle_deg"]))
        else:
            if "forward_lean" in active:
                s = active.pop("forward_lean")
                mark("forward_lean", s["start"], t, min(1.0, (s["max"] - FORWARD_LEAN_DEG) / 25.0))

        # knee too straight
        kL = f.get("knee_left_deg")
        kR = f.get("knee_right_deg")
        knee_max = None
        if isinstance(kL, (int, float)) and isinstance(kR, (int, float)):
            knee_max = max(float(kL), float(kR))
        elif isinstance(kL, (int, float)):
            knee_max = float(kL)
        elif isinstance(kR, (int, float)):
            knee_max = float(kR)

        if knee_max is not None and knee_max > TOO_STRAIGHT_KNEE and f["vis"] > 0.4:
            active.setdefault("knee_too_straight", {"start": t, "max": 0.0})
            active["knee_too_straight"]["max"] = max(active["knee_too_straight"]["max"], knee_max)
        else:
            if "knee_too_straight" in active:
                s = active.pop("knee_too_straight")
                mark("knee_too_straight", s["start"], t, min(1.0, (s["max"] - TOO_STRAIGHT_KNEE) / 20.0))

        # knee too deep
        knee_min = None
        if isinstance(kL, (int, float)) and isinstance(kR, (int, float)):
            knee_min = min(float(kL), float(kR))
        elif isinstance(kL, (int, float)):
            knee_min = float(kL)
        elif isinstance(kR, (int, float)):
            knee_min = float(kR)

        if knee_min is not None and knee_min < TOO_DEEP_KNEE and f["vis"] > 0.4:
            active.setdefault("knee_too_deep", {"start": t, "min": 999.0})
            active["knee_too_deep"]["min"] = min(active["knee_too_deep"]["min"], knee_min)
        else:
            if "knee_too_deep" in active:
                s = active.pop("knee_too_deep")
                mark("knee_too_deep", s["start"], t, min(1.0, (TOO_DEEP_KNEE - s["min"]) / 30.0))

        # hip sway
        if abs(float(f["hip_sway"])) > HIP_SWAY_BIG and f["vis"] > 0.4:
            active.setdefault("hip_sway", {"start": t, "max": 0.0})
            active["hip_sway"]["max"] = max(active["hip_sway"]["max"], abs(float(f["hip_sway"])))
        else:
            if "hip_sway" in active:
                s = active.pop("hip_sway")
                mark("hip_sway", s["start"], t, min(1.0, (s["max"] - HIP_SWAY_BIG) / 0.10))

    # 끝까지 열려있던 segment 닫기
    if feats_ts:
        last_t2 = float(feats_ts[-1]["t"])
        for tag, s in list(active.items()):
            if tag == "forward_lean":
                mark(tag, s["start"], last_t2, min(1.0, (s["max"] - FORWARD_LEAN_DEG) / 25.0))
            elif tag == "knee_too_straight":
                mark(tag, s["start"], last_t2, min(1.0, (s["max"] - TOO_STRAIGHT_KNEE) / 20.0))
            elif tag == "knee_too_deep":
                mark(tag, s["start"], last_t2, min(1.0, (TOO_DEEP_KNEE - s["min"]) / 30.0))
            elif tag == "hip_sway":
                mark(tag, s["start"], last_t2, min(1.0, (s["max"] - HIP_SWAY_BIG) / 0.10))

    segments = _merge_segments(raw_segments)

    def seg_count(tag: str) -> int:
        return sum(1 for s in segments if s["tag"] == tag)

    summary_lines = [
        f"포즈 기반 자동 분석(샘플링 {sample_fps}fps, 최대 {max_seconds}s).",
        f"- 상체 전경(forward_lean): {seg_count('forward_lean')} 구간",
        f"- 무릎 과신전(knee_too_straight): {seg_count('knee_too_straight')} 구간",
        f"- 무릎 과도 굴곡(knee_too_deep): {seg_count('knee_too_deep')} 구간",
        f"- 좌우 밸런스 흔들림(hip_sway): {seg_count('hip_sway')} 구간",
        "segments는 timecode 기반 이슈 후보이며, LLM이 이를 코칭 이슈로 구조화한다.",
    ]
    summary_text = "\n".join(summary_lines)

    analysis_json: Dict[str, Any] = {
        "sport": sport,
        "level": level,
        "summary": summary_text,
        "meta": {
            "filename": filename,
            "object_key": analysis_key,
            "video_id": video_id,
            "note": "pose+heuristics MVP (mediapipe). thresholds tunable.",
        },
        "signals": {
            "segments": segments,
            "keypoints": keypoints_ts[:3000],
            "features": feats_ts[:3000],
        },
        "video": {
            "object_key": analysis_key,
            "transcoded_object_key": transcoded_object_key,
            "public_url": public_url,
        },
    }
    return analysis_json