const HISTORY_KEY = "sportCoachJobHistory";

export function loadJobHistory(): number[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(arr)) return [];
    return arr.map(Number).filter((x) => Number.isFinite(x));
  } catch {
    return [];
  }
}

export function pushJobHistory(jobId: number) {
  const prev = loadJobHistory();
  const next = [jobId, ...prev.filter((x) => x !== jobId)].slice(0, 50);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
}

export function clearJobHistory() {
  localStorage.removeItem(HISTORY_KEY);
}