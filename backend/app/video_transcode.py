import subprocess
import tempfile
import os

from .storage import get_object_bytes, put_object_file


def transcode_to_mp4(
    src_object_key: str,
    dst_object_key: str,
):
    """
    MOV(HEVC/H.265) → MP4(H.264 + AAC)
    """
    with tempfile.TemporaryDirectory() as tmp:
        src_path = os.path.join(tmp, "input.mov")
        dst_path = os.path.join(tmp, "output.mp4")

        # 1️⃣ MinIO에서 원본 다운로드
        data = get_object_bytes(src_object_key)
        with open(src_path, "wb") as f:
            f.write(data)

        # 2️⃣ ffmpeg 변환
        cmd = [
            "ffmpeg",
            "-y",
            "-i", src_path,
            "-c:v", "libx264",
            "-profile:v", "main",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-crf", "23",
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", "128k",
            dst_path,
        ]

        subprocess.run(cmd, check=True)

        # 3️⃣ 결과 업로드
        put_object_file(
            dst_object_key,
            dst_path,
            content_type="video/mp4",
        )