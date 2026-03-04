import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { clearJobHistory, loadJobHistory } from "../lib/history";
import { fetchJob, JobResp } from "../lib/api";

type ItemState =
  | ({ loading: true } & Partial<JobResp>)
  | (JobResp & { loading?: false })
  | { error: string; loading?: false };

export default function History() {
  const [ids, setIds] = useState<number[]>([]);
  const [items, setItems] = useState<Record<number, ItemState | undefined>>({});
  const [q, setQ] = useState("");

  useEffect(() => {
    setIds(loadJobHistory());
  }, []);

  useEffect(() => {
    if (ids.length === 0) return;
    let cancelled = false;

    // ✅ 먼저 "로딩" 상태로 채워서 undefined 접근 방지
    setItems((prev) => {
      const next = { ...prev };
      for (const id of ids) {
        if (!next[id]) next[id] = { loading: true };
      }
      return next;
    });

    (async () => {
      const next: Record<number, ItemState> = {};
      await Promise.all(
        ids.map(async (id) => {
          try {
            next[id] = (await fetchJob(id)) as ItemState;
          } catch (e: any) {
            next[id] = { error: e?.message || String(e) };
          }
        })
      );
      if (!cancelled) {
        setItems((prev) => ({ ...prev, ...next }));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [ids]);

  const rows = useMemo(() => {
    const s = q.trim().toLowerCase();

    return ids
      .map((id) => {
        const it = items[id];
        // ✅ 아직 없으면 loading으로 처리
        const safe: ItemState = it ?? { loading: true };
        return { id, it: safe };
      })
      .filter(({ id, it }) => {
        if (!s) return true;
        const status = (it as any)?.status ?? "";
        const err = (it as any)?.error ?? "";
        return (`job ${id} ${status} ${err}`).toLowerCase().includes(s);
      });
  }, [ids, items, q]);

  return (
    <div className="container">
      <header className="header">
        <div>
          <h1 className="title">히스토리</h1>
          <div className="subtitle">localStorage 기반 job 목록</div>
        </div>
        <Link className="link" to="/">
          ⟵ 홈
        </Link>
      </header>

      <div className="card">
        <div className="row">
          <input
            className="input"
            placeholder="검색: job/status"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <button
            className="btn"
            disabled={ids.length === 0}
            onClick={() => {
              clearJobHistory();
              setIds([]);
              setItems({});
            }}
          >
            전체 삭제
          </button>
        </div>

        {rows.length === 0 ? (
          <div className="hint" style={{ marginTop: 12 }}>
            히스토리가 없습니다.
          </div>
        ) : (
          <div className="list" style={{ marginTop: 12 }}>
            {rows.map(({ id, it }) => {
              const anyIt: any = it;
              const isLoading = anyIt?.loading === true && !anyIt?.error && anyIt?.status == null;

              return (
                <Link key={id} className="item" to={`/result/${id}`}>
                  <div className="itemTitle">Job #{id}</div>

                  {anyIt?.error ? (
                    <div className="itemSub err">조회 실패: {anyIt.error}</div>
                  ) : isLoading ? (
                    <div className="itemSub">조회 중...</div>
                  ) : (
                    <div className="itemSub">
                      status: <b>{anyIt?.status ?? "-"}</b> / progress:{" "}
                      <b>{typeof anyIt?.progress === "number" ? `${anyIt.progress}%` : "-"}</b> / video_id:{" "}
                      <b>{anyIt?.video_id ?? "-"}</b>
                    </div>
                  )}
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}