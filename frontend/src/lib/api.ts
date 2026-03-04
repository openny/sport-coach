export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export type JobStatus = "queued" | "running" | "done" | "failed";

export type JobResp = {
  job_id: number;
  video_id: number; // ✅ 이제 백엔드에서 준다 (필수)
  status: JobStatus;
  progress: number;
  error?: string | null;
};

export type RagChunk = {
  content: string;
  source?: string | null;
  score?: number | null;
};

export type RagContext = {
  query?: string | null;
  chunks?: RagChunk[];
};

export type ResultResp = {
  analysis: any;
  coaching_text: string;
  coaching_json?: any;
  rag_context?: RagContext | null;

  // (선택) 백엔드가 나중에 내려주면 자동으로 영상 URL 구성에 사용
  video_url?: string | null;
  video_object_key?: string | null;
  transcoded_object_key?: string | null;
};

export type VideoMetaResp = {
  video_id: number;
  filename?: string;
  object_key?: string;
  public_url?: string;
};

export async function createVideo(filename: string): Promise<number> {
  const r = await fetch(`${API_BASE}/v1/videos?filename=${encodeURIComponent(filename)}`, { method: "POST" });
  if (!r.ok) throw new Error(`createVideo failed: ${r.status}`);
  const data = await r.json();
  return data.video_id ?? data.id;
}

export async function uploadVideo(videoId: number, file: File): Promise<void> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch(`${API_BASE}/v1/videos/${videoId}/upload`, { method: "POST", body: fd });
  if (!r.ok) throw new Error(`uploadVideo failed: ${r.status}`);
}

export async function analyzeVideo(videoId: number, payload: any): Promise<number> {
  const r = await fetch(`${API_BASE}/v1/videos/${videoId}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`analyzeVideo failed: ${r.status}`);
  const data = await r.json();
  return data.job_id ?? data.id;
}

export async function fetchJob(jobId: number): Promise<JobResp> {
  const r = await fetch(`${API_BASE}/v1/jobs/${jobId}`);
  if (!r.ok) throw new Error(`fetchJob failed: ${r.status}`);
  return (await r.json()) as JobResp;
}

export async function fetchVideoMeta(videoId: number): Promise<VideoMetaResp> {
  const r = await fetch(`${API_BASE}/v1/videos/${videoId}`);
  if (!r.ok) throw new Error(`fetchVideoMeta failed: ${r.status}`);
  return (await r.json()) as VideoMetaResp;
}

export async function fetchResult(videoId: number): Promise<ResultResp> {
  const r = await fetch(`${API_BASE}/v1/videos/${videoId}/result`);
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as ResultResp;
}

// ----------------------------
// Admin / RAG manuals
// ----------------------------
export type ManualOut = {
  id: number;
  sport: string;
  title: string;
  version: string;
  status: string;
  object_key: string;
  created_at?: string | null;
};

export type ManualChunksStats = {
  manual_id: number;
  chunks: number;
};

export async function uploadManual(form: {
  sport: string;
  title: string;
  version: string;
  file: File;
}): Promise<{ manual_id: number }> {
  const fd = new FormData();
  fd.append("file", form.file);

  const url =
    `${API_BASE}/v1/admin/manuals` +
    `?sport=${encodeURIComponent(form.sport)}` +
    `&title=${encodeURIComponent(form.title)}` +
    `&version=${encodeURIComponent(form.version)}`;

  const r = await fetch(url, { method: "POST", body: fd });
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as { manual_id: number };
}

export async function listManuals(sport?: string): Promise<ManualOut[]> {
  const url = sport
    ? `${API_BASE}/v1/admin/manuals?sport=${encodeURIComponent(sport)}`
    : `${API_BASE}/v1/admin/manuals`;

  const r = await fetch(url);
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as ManualOut[];
}

export async function reindexManual(manualId: number): Promise<{ ok: boolean }> {
  const r = await fetch(`${API_BASE}/v1/admin/manuals/${manualId}/reindex`, {
    method: "POST",
  });
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as { ok: boolean };
}

export async function getManualChunks(manualId: number): Promise<ManualChunksStats> {
  const r = await fetch(`${API_BASE}/v1/admin/manuals/${manualId}/chunks`);
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as ManualChunksStats;
}
