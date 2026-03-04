import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getManualChunks, listManuals, reindexManual, uploadManual, ManualOut } from "../lib/api";

type Sport = "ski" | "snowboard" | "golf" | "running";

export default function AdminManuals() {
  const [sport, setSport] = useState<Sport>("ski");
  const [title, setTitle] = useState("Ski Manual");
  const [version, setVersion] = useState("v1");
  const [file, setFile] = useState<File | null>(null);

  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [items, setItems] = useState<ManualOut[]>([]);
  const [chunksMap, setChunksMap] = useState<Record<number, number>>({});

  const canUpload = useMemo(() => !!file && !busy, [file, busy]);

  async function refresh() {
    const rows = await listManuals(sport);
    setItems(rows);

    // chunk count도 같이 불러서 “임베딩 됐는지” 바로 보여주기
    const next: Record<number, number> = {};
    for (const m of rows) {
      try {
        const st = await getManualChunks(m.id);
        next[m.id] = st.chunks;
      } catch {
        next[m.id] = 0;
      }
    }
    setChunksMap(next);
  }

  useEffect(() => {
    refresh().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sport]);

  async function onUpload() {
    if (!file) return;
    setBusy(true);
    setErr(null);
    setMsg(null);

    try {
      const out = await uploadManual({ sport, title, version, file });
      setMsg(`업로드 완료! manual_id=${out.manual_id}`);
      setFile(null);
      await refresh();
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onReindex(manualId: number) {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await reindexManual(manualId);
      setMsg(`reindex 요청 완료! manual_id=${manualId} (worker가 처리 중)`);
      // 잠깐 후 refresh 하면 chunk count 증가 확인 가능
      setTimeout(() => refresh().catch(() => {}), 1500);
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container">
      <header className="header">
        <div>
          <h1 className="title">교본 관리 (RAG)</h1>
          <div className="subtitle">PDF 업로드 → 청킹/임베딩 → 코칭 근거로 사용</div>
        </div>
        <div className="row">
          <Link className="link" to="/">
            ⟵ 홈
          </Link>
          <Link className="link" to="/history">
            히스토리
          </Link>
        </div>
      </header>

      <div className="card">
        <h2 className="h2">교본 업로드</h2>
        {err && <div className="alert">에러: {err}</div>}
        {msg && <div className="ok">{msg}</div>}

        <div className="grid2">
          <div>
            <div className="label">종목</div>
            <select className="select" value={sport} disabled={busy} onChange={(e) => setSport(e.target.value as Sport)}>
              <option value="ski">스키</option>
              <option value="snowboard">보드</option>
              <option value="golf">골프</option>
              <option value="running">런닝</option>
            </select>
            <div className="hint">MVP는 ski만 실제로 쓰지만, 구조는 확장형</div>
          </div>

          <div>
            <div className="label">버전</div>
            <input className="input" value={version} disabled={busy} onChange={(e) => setVersion(e.target.value)} />
            <div className="hint">예: v1 / 2026.02 / book-3rd</div>
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <div className="label">교본 제목</div>
          <input className="input" value={title} disabled={busy} onChange={(e) => setTitle(e.target.value)} />
        </div>

        <div style={{ marginTop: 12 }}>
          <div className="label">PDF 파일</div>
          <input
            type="file"
            accept="application/pdf"
            disabled={busy}
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <div className="hint">업로드 후 “리인덱스”를 눌러야 chunks/embedding이 생성됩니다.</div>
        </div>

        <div className="row" style={{ marginTop: 14 }}>
          <button className="btnPrimary" disabled={!canUpload} onClick={onUpload}>
            {busy ? "처리 중..." : "업로드"}
          </button>
          <button className="btn" disabled={busy} onClick={() => refresh().catch(() => {})}>
            목록 새로고침
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
          <h2 className="h2">교본 목록</h2>
          <span className="hint">chunks=0이면 아직 임베딩이 안된 상태</span>
        </div>

        {items.length === 0 ? (
          <div className="hint" style={{ marginTop: 8 }}>
            교본이 없습니다. 먼저 업로드 해주세요.
          </div>
        ) : (
          <div className="list" style={{ marginTop: 10 }}>
            {items.map((m) => (
              <div className="listItem" key={m.id}>
                <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
                  <div>
                    <div style={{ fontWeight: 900 }}>
                      #{m.id} · {m.title}
                    </div>
                    <div className="hint">
                      sport={m.sport} / version={m.version} / status={m.status}
                    </div>
                    <div className="hint">object_key: {m.object_key}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="pill">chunks: {chunksMap[m.id] ?? 0}</div>
                    <div style={{ height: 8 }} />
                    <button className="btn" disabled={busy} onClick={() => onReindex(m.id)}>
                      리인덱스(청킹/임베딩)
                    </button>
                  </div>
                </div>

                {(chunksMap[m.id] ?? 0) > 0 ? (
                  <div className="ok" style={{ marginTop: 10 }}>
                    임베딩 완료 ✅ (코칭 결과에서 RAG 근거로 표시됩니다)
                  </div>
                ) : (
                  <div className="hint" style={{ marginTop: 10 }}>
                    아직 임베딩 없음 → 리인덱스를 눌러주세요
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}