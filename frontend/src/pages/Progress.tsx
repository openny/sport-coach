import React, { useEffect, useState } from "react";
import { jobStatus } from "../lib/api";

export default function Progress({ jobId, onDone }: any) {
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    const t = setInterval(async () => {
      const s = await jobStatus(jobId);
      setStatus(s);
      if (s.status === "done") onDone();
      if (s.status === "failed") clearInterval(t);
    }, 1000);
    return () => clearInterval(t);
  }, [jobId]);

  return (
    <div style={{ padding: 24, maxWidth: 720, margin: "0 auto" }}>
      <h2>분석 진행</h2>
      {status && (
        <>
          <div>상태: {status.status}</div>
          <div>진행: {status.progress}%</div>
          {status.error && <pre>{status.error}</pre>}
        </>
      )}
    </div>
  );
}
