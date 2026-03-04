import React, { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { analyzeVideo, createVideo, uploadVideo } from "../lib/api";
import { pushJobHistory } from "../lib/history";

type Level = "beginner" | "intermediate" | "advanced";

export default function Home() {
  const nav = useNavigate();
  const [level, setLevel] = useState<Level>("intermediate");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const canStart = useMemo(() => !!file && !busy, [file, busy]);

  async function onStart() {
    if (!file) return;
    setBusy(true);
    setErr(null);

    try {
      setStage("1/3 video 레코드 생성...");
      const videoId = await createVideo(file.name);

      setStage("2/3 업로드 중...");
      await uploadVideo(videoId, file);

      setStage("3/3 분석 시작...");
      const jobId = await analyzeVideo(videoId, { sport: "ski", level });

      pushJobHistory(jobId);
      nav(`/result/${jobId}`);
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
      setStage("");
    }
  }

  return (
    <div className="container">
      <header className="header">
        <div>
          <h1 className="title">스키 AI 코치</h1>
          <div className="subtitle">업로드 → 분석 → 코칭</div>
        </div>
        <Link className="link" to="/history">
          히스토리 →
        </Link>
        <Link className="link" to="/admin/manuals">
          교본 관리 →
        </Link>
      </header>

      <div className="card">
        <h2 className="h2">분석 시작</h2>
        {err && <div className="alert">에러: {err}</div>}

        <div className="grid2">
          <div>
            <div className="label">종목</div>
            <div className="pill">SKI (MVP 고정)</div>
          </div>
          <div>
            <div className="label">레벨</div>
            <select className="select" value={level} disabled={busy} onChange={(e) => setLevel(e.target.value as Level)}>
              <option value="beginner">초급</option>
              <option value="intermediate">중급</option>
              <option value="advanced">상급</option>
            </select>
          </div>
        </div>

        <div style={{ marginTop: 14 }}>
          <div className="label">영상 선택</div>
          <input type="file" accept="video/*" disabled={busy} onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <div className="hint">처음엔 10~20초 짧은 클립이 가장 안정적</div>
        </div>

        <div className="row" style={{ marginTop: 16 }}>
          <button className="btnPrimary" disabled={!canStart} onClick={onStart}>
            {busy ? "진행 중..." : "분석 시작"}
          </button>
          {stage && <div className="stage">{stage}</div>}
        </div>
      </div>
    </div>
  );
}