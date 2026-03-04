import React, { useState } from "react";
import { createVideo, uploadVideo, analyze } from "../lib/api";

export default function Upload({ sport, level, onStartJob, goAdmin }: any) {
  const [file, setFile] = useState<File | null>(null);

  const start = async () => {
    if (!file) return;
    const v = await createVideo(file.name);
    await uploadVideo(v.video_id, file);
    const job = await analyze(v.video_id, sport, level);
    onStartJob({ videoId: v.video_id, jobId: job.job_id });
  };

  return (
    <div style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      <h2>영상 업로드</h2>
      <p>권장: 정면/측면 중 하나, 흔들림 최소, 10~20초만 잘라서 테스트</p>

      <input type="file" accept="video/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />

      <div style={{ marginTop: 16 }}>
        <button onClick={start} disabled={!file}>분석 시작</button>
        <button onClick={goAdmin} style={{ marginLeft: 8 }}>교본 업로드(어드민)</button>
      </div>
    </div>
  );
}
