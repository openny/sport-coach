import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchJob, fetchResult, JobResp, ResultResp } from "../lib/api";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const MINIO_PUBLIC = import.meta.env.VITE_MINIO_PUBLIC || "http://localhost:9000";

function safeJson(v: any) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

function isObj(v: any): v is Record<string, any> {
  return v && typeof v === "object" && !Array.isArray(v);
}

function toText(v: any): string {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return safeJson(v);
}

function toTextList(v: any): string[] {
  if (v == null) return [];
  if (Array.isArray(v)) return v.map((x) => toText(x)).filter(Boolean);
  if (typeof v === "string") return v.trim() ? [v] : [];
  if (isObj(v)) return [safeJson(v)];
  return [String(v)];
}

function mmss(sec: number) {
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

// v2 coaching_json 기준 + legacy 호환
// type Issue = {
//   id?: string;
//   title?: string;
//   severity?: "low" | "medium" | "high";
//
//   // v2
//   timecode_sec?: number;
//
//   // legacy
//   timecode?: { start?: number; end?: number } | { start_sec?: number; end_sec?: number };
//
//   // content
//   what?: string;
//   why?: string;
//   how_to_fix?: any; // string | string[]
//   drills?: any; // string | string[]
// };

type Issue = {
  id?: string;
  title?: string;
  what?: string;
  why?: string;
  how_to_fix?: any; // string | string[] | object 등
  severity?: "low" | "medium" | "high";
  timecode_sec?: number; // ✅ 백엔드가 주는 단일 초
  timecode?: { start?: number; end?: number } | { start_sec?: number; end_sec?: number };
};

export default function Result() {
  const { jobId } = useParams();
  const jid = useMemo(() => {
    const n = Number(jobId);
    return Number.isFinite(n) ? n : null;
  }, [jobId]);

  const videoRef = useRef<HTMLVideoElement | null>(null);

  const [job, setJob] = useState<JobResp | null>(null);
  const [res, setRes] = useState<ResultResp | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [openRag, setOpenRag] = useState(true);
  const [openDebug, setOpenDebug] = useState(false);

  useEffect(() => {
    if (!jid) return;
    let timer: any;

    const run = async () => {
      try {
        setErr(null);
        const j = await fetchJob(jid);
        setJob(j);

        if (j.status === "done") {
          const r = await fetchResult(j.video_id);
          setRes(r);
          clearInterval(timer);
        }
        if (j.status === "failed") {
          clearInterval(timer);
        }
      } catch (e: any) {
        setErr(e?.message || String(e));
        clearInterval(timer);
      }
    };

    run();
    timer = setInterval(run, 1500);
    return () => timer && clearInterval(timer);
  }, [jid]);

  // ---- derive video url (transcoded first) ----
  const videoUrl = useMemo(() => {
    const analysis = (res as any)?.analysis as any;
    const fromAnalysis = analysis?.video?.public_url || analysis?.public_url || analysis?.video_public_url;
    if (typeof fromAnalysis === "string" && fromAnalysis.startsWith("http")) return fromAnalysis;

    const objectKey =
      analysis?.video?.transcoded_object_key ||
      analysis?.video?.object_key ||
      analysis?.transcoded_object_key ||
      analysis?.object_key;

    if (typeof objectKey === "string") {
      const bucket = (import.meta as any).env?.VITE_MINIO_BUCKET || "coach";
      return `${MINIO_PUBLIC}/${bucket}/${objectKey}`;
    }
    return "";
  }, [res]);

  // ---- structured coaching_json parsing ----
  const coaching = useMemo(() => {
    const cj: any = (res as any)?.coaching_json || null;
    return isObj(cj) ? cj : null;
  }, [res]);

  const summaryOneLiner = useMemo(() => {
    const s: any = coaching?.summary ?? coaching?.overall_summary ?? coaching?.overview ?? null;
    if (typeof s === "string") return s;
    if (isObj(s)) return String(s.one_liner ?? s.one_liner ?? s.text ?? s.message ?? "");
    return "";
  }, [coaching]);

  const levelText = useMemo(() => {
    const s: any = coaching?.summary ?? coaching?.overall_summary ?? null;
    if (isObj(s) && s.level != null) return String(s.level);
    if (coaching?.level != null) return String(coaching.level);
    return "";
  }, [coaching]);

  const issues: Issue[] = useMemo(() => {
    const arr: any = coaching?.issues;
    if (Array.isArray(arr)) return arr;
    return [];
  }, [coaching]);

  const severityRank: Record<string, number> = { low: 1, medium: 2, high: 3 };

type IssueGroup = {
  key: string;
  title: string;
  severity: "low" | "medium" | "high";
  items: Issue[]; // 같은 이슈의 여러 발생 구간들
  base: Issue;    // 카드 본문(why/how 등)은 대표 1개로 표시
};

const groupedIssues: IssueGroup[] = useMemo(() => {
  if (!issues || issues.length === 0) return [];

  const m = new Map<string, IssueGroup>();

  for (const it of issues) {
    const key = String((it as any).id ?? it.title ?? "unknown");
    const title = String(it.title ?? (it as any).id ?? "이슈");
    const sev = (it.severity ?? "medium") as "low" | "medium" | "high";

    if (!m.has(key)) {
      m.set(key, { key, title, severity: sev, items: [it], base: it });
    } else {
      const g = m.get(key)!;
      g.items.push(it);

      // severity는 max로
      if (severityRank[sev] > severityRank[g.severity]) g.severity = sev;

      // base는 score 같은 게 없으니, "why/how/drills"가 더 풍부한 쪽을 대표로 삼고 싶으면 여기서 바꿀 수 있음
      // 지금은 첫 번째 유지
    }
  }

  // 그룹 안에서 time 기준 정렬
  const groups = Array.from(m.values());
  for (const g of groups) {
    g.items.sort((a, b) => {
      const sa = issueTimeStart(a) ?? 1e18;
      const sb = issueTimeStart(b) ?? 1e18;
      return sa - sb;
    });
  }

  // 그룹 자체도 첫 발생 시간 기준 정렬
  groups.sort((a, b) => {
    const sa = issueTimeStart(a.items[0]) ?? 1e18;
    const sb = issueTimeStart(b.items[0]) ?? 1e18;
    return sa - sb;
  });

  return groups;
}, [issues]);

  const ragContext = useMemo(() => {
    const analysis: any = (res as any)?.analysis;
    const rc = (res as any)?.rag_context || coaching?.rag_context || analysis?.rag_context || null;
    return rc && typeof rc === "object" ? rc : null;
  }, [res, coaching]);

  function seekTo(sec: number, autoPlay = true) {
    const v = videoRef.current;
    if (!v) return;
    const t = Math.max(0, sec);

    // 메타데이터 로딩 전이면 seek가 씹힐 수 있어서 한 번 더 보정
    const doSeek = () => {
      v.currentTime = t;
      if (autoPlay) v.play().catch(() => {});
    };

    if (Number.isFinite(v.duration) && v.duration > 0) {
      doSeek();
    } else {
      const handler = () => {
        v.removeEventListener("loadedmetadata", handler);
        doSeek();
      };
      v.addEventListener("loadedmetadata", handler);
      // 그래도 혹시 이미 로딩됐으면 즉시 시도
      doSeek();
    }
  }

  // v2: timecode_sec 우선, 없으면 legacy timecode.start(_sec)
  // function issueTimeStart(it: Issue): number | null {
  //   const tcSec = (it as any).timecode_sec;
  //   if (typeof tcSec === "number") return tcSec;
  //
  //   const tc: any = (it as any).timecode;
  //   if (!tc) return null;
  //   const s = tc.start ?? tc.start_sec ?? null;
  //   return typeof s === "number" ? s : null;
  // }
  //
  // function issueTimeEnd(it: Issue): number | null {
  //   const tc: any = (it as any).timecode;
  //   if (!tc) return null;
  //   const e = tc.end ?? tc.end_sec ?? null;
  //   return typeof e === "number" ? e : null;
  // }

function issueTimeStart(it: Issue): number | null {
  // ✅ 1) timecode_sec 우선
  if (typeof (it as any).timecode_sec === "number") return (it as any).timecode_sec;

  // ✅ 2) timecode 객체 지원
  const tc: any = (it as any).timecode;
  if (!tc) return null;
  const s = tc.start ?? tc.start_sec ?? null;
  return typeof s === "number" ? s : null;
}

function issueTimeEnd(it: Issue): number | null {
  const tc: any = (it as any).timecode;
  if (!tc) return null;
  const e = tc.end ?? tc.end_sec ?? null;
  return typeof e === "number" ? e : null;
}

  if (!jid) {
    return (
      <div className="container">
        <header className="header">
          <h1 className="title">스키 코칭 결과</h1>
          <Link className="link" to="/">
            ⟵ 홈
          </Link>
        </header>
        <div className="card">
          <div className="alert">잘못된 job id 입니다. /result/:jobId 로 접근해야 합니다.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <header className="header">
        <div>
          <h1 className="title">스키 코칭 결과</h1>
          <div className="subtitle">Job #{jid}</div>
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
        {err && <div className="alert">에러: {err}</div>}

        {!job ? (
          <div className="hint">job 조회 중...</div>
        ) : (
          <div className="hint">
            status: <b>{job.status}</b> / progress: <b>{job.progress}%</b> / video_id: <b>{job.video_id}</b>
          </div>
        )}
      </div>

      {job?.status === "done" && res && (
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: 14, marginTop: 14 }}>
          {/* left: player + issues */}
          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline" }}>
              <h2 className="h2" style={{ marginBottom: 8 }}>
                영상 & 타임라인
              </h2>
              {summaryOneLiner && (
                <div className="pill" title={levelText ? `레벨: ${levelText}` : ""}>
                  {summaryOneLiner}
                  {levelText ? ` · ${levelText}` : ""}
                </div>
              )}
            </div>

            {videoUrl ? (
              <video
                ref={videoRef}
                controls
                preload="metadata"
                style={{ width: "100%", borderRadius: 12, background: "#111" }}
              >
                <source src={videoUrl} />
                브라우저에서 재생 불가한 포맷일 수 있어요. (iPhone MOV/HEVC면 mp4(h264) 트랜스코딩 필요)
              </video>
            ) : (
              <div className="alert">
                영상 URL을 만들 수 없어요. analysis_json에 public_url/object_key/transcoded_object_key 중 하나를 넣어줘야 합니다.
              </div>
            )}

            <div style={{ marginTop: 14 }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h3 className="h2" style={{ margin: 0 }}>
                  이슈 타임라인
                </h3>
                <div className="hint">이슈를 클릭하면 해당 구간으로 이동합니다.</div>
              </div>

              {issues.length === 0 ? (
                <div className="hint" style={{ marginTop: 10 }}>
                  이슈가 없습니다. <code>coaching_json.issues[]</code> 필요
                </div>
              ) : (
                <div style={{ marginTop: 10, display: "grid", gap: 10 }}>
                  {groupedIssues.map((g, idx) => {
                      const sev = g.severity || "medium";
                      const firstStart = issueTimeStart(g.items[0]);

                      return (
                        <div
                          key={g.key || idx}
                          className="card"
                          style={{ textAlign: "left", padding: 12, borderRadius: 12 }}
                        >
                          {/* 헤더: 제목 + severity + 발생 타임칩들 */}
                          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                            <div style={{ fontWeight: 700 }}>{g.title}</div>
                            <div className="row" style={{ gap: 8 }}>
                              <span className="pill">{sev}</span>
                              <span className="pill">x{g.items.length}</span>
                            </div>
                          </div>

                          {/* 타임코드 칩들 */}
                          <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 10 }}>
                            {g.items.map((it, i) => {
                              const s = issueTimeStart(it);
                              const e = issueTimeEnd(it);
                              const label =
                                s != null && e != null ? `${mmss(s)}–${mmss(e)}` : s != null ? `${mmss(s)}` : "—";

                              return (
                                <button
                                  key={i}
                                  className="pill"
                                  style={{ cursor: s != null ? "pointer" : "default" }}
                                  onClick={() => {
                                    if (s != null) seekTo(s);
                                  }}
                                  title="클릭하면 해당 구간으로 이동"
                                >
                                  {label}
                                </button>
                              );
                            })}
                          </div>

                          {/* 본문: 대표(base) 내용 1회만 표시 */}
                          <div style={{ marginTop: 10 }}>
                            {(g.base as any).what && (
                              <div style={{ marginTop: 6 }}>
                                <b>문제</b>: {toText((g.base as any).what)}
                              </div>
                            )}
                            {(g.base as any).why && (
                              <div style={{ marginTop: 6 }}>
                                <b>왜</b>: {toText((g.base as any).why)}
                              </div>
                            )}
                            {(g.base as any).how_to_fix && (
                              <div style={{ marginTop: 6 }}>
                                <b>어떻게</b>: {toText((g.base as any).how_to_fix)}
                              </div>
                            )}
                          </div>

                          {/* 카드 자체를 눌러 첫 구간으로 이동하고 싶으면 이 버튼을 추가 */}
                          {firstStart != null && (
                            <div style={{ marginTop: 10 }}>
                              <button className="btn" onClick={() => seekTo(firstStart)}>
                                첫 발생 구간으로 이동
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                </div>
              )}
            </div>
          </div>

          {/* right: coaching + rag evidence */}
          <div style={{ display: "grid", gap: 14 }}>
            <div className="card">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <h2 className="h2" style={{ margin: 0 }}>
                  코칭 결과
                </h2>
                <button className="btn" onClick={() => setOpenDebug((v) => !v)}>
                  {openDebug ? "디버그 숨기기" : "디버그 보기"}
                </button>
              </div>

              {coaching ? (
                <div style={{ marginTop: 10, display: "grid", gap: 10 }}>
                  <div>
                    <div className="label">한 줄 요약</div>
                    <div style={{ fontSize: 16, fontWeight: 700 }}>
                      {summaryOneLiner || "요약 없음 (coaching_json.summary.one_liner 필요)"}
                    </div>
                    {levelText && <div className="hint">레벨: {levelText}</div>}
                  </div>

                  {isObj(coaching?.summary) && Array.isArray((coaching.summary as any).highlights) && (
                    <div>
                      <div className="label">하이라이트</div>
                      <ul style={{ margin: "6px 0 0 16px" }}>
                        {(coaching.summary as any).highlights.map((k: any, i: number) => (
                          <li key={i}>{toText(k)}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ marginTop: 10 }}>
                  <div className="label">LLM 원문</div>
                  <pre className="preDark">{(res as any).coaching_text || "(empty)"}</pre>
                </div>
              )}

              {openDebug && (
                <div style={{ marginTop: 12 }}>
                  <div className="label">raw coaching_json</div>
                  <pre className="pre">{safeJson((res as any).coaching_json)}</pre>
                </div>
              )}
            </div>

            <div className="card">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <h2 className="h2" style={{ margin: 0 }}>
                  RAG 근거(교본)
                </h2>
                <button className="btn" onClick={() => setOpenRag((v) => !v)}>
                  {openRag ? "접기" : "펼치기"}
                </button>
              </div>

              {!openRag ? null : !ragContext ? (
                <div className="hint" style={{ marginTop: 10 }}>
                  RAG 컨텍스트가 없습니다. 결과에 <code>rag_context</code> (query + chunks[])를 넣어주세요.
                </div>
              ) : (
                <div style={{ marginTop: 10 }}>
                  <div className="label">검색 쿼리</div>
                  <div className="hint" style={{ whiteSpace: "pre-wrap" }}>
                    {toText((ragContext as any).query)}
                  </div>

                  <div className="label" style={{ marginTop: 12 }}>
                    근거 청크
                  </div>

                  <div style={{ display: "grid", gap: 10, marginTop: 8 }}>
                    {Array.isArray((ragContext as any).chunks) && (ragContext as any).chunks.length > 0 ? (
                      (ragContext as any).chunks.map((c: any, i: number) => (
                        <div key={i} className="card" style={{ padding: 12, borderRadius: 12 }}>
                          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                            <div style={{ fontWeight: 700 }}>근거 #{i + 1}</div>
                            <div className="row" style={{ gap: 8 }}>
                              {c?.score != null && <span className="pill">score: {String(c.score)}</span>}
                              {c?.page != null && <span className="pill">p.{String(c.page)}</span>}
                              {c?.source && <span className="pill">{toText(c.source)}</span>}
                            </div>
                          </div>
                          <div style={{ marginTop: 8, whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
                            {toText(c?.content)}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="hint">chunks[]가 비어있습니다.</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {job?.status === "done" && res && (
        <div className="card" style={{ marginTop: 14 }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <h2 className="h2" style={{ margin: 0 }}>
              분석 JSON (디버그)
            </h2>
            <a className="link" href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
              API docs →
            </a>
          </div>
          <pre className="pre">{safeJson((res as any).analysis)}</pre>
        </div>
      )}
    </div>
  );
}