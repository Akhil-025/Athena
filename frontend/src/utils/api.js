import askStreamRaw from "../hooks/useStreamingAPI";

/** fetchStats */
export async function fetchStats(url) {
  try {
    const res = await fetch(url);
    if(!res.ok) throw new Error("Failed to fetch stats");
    const j = await res.json();
    return j.stats || j;
  } catch (e) {
    console.warn("fetchStats failed", e);
    return null;
  }
}

/** askQuestionAPI */
export async function askQuestionAPI(url, payload) {
  const res = await fetch(url, {
    method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload)
  });
  if(!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }
  return res.json();
}

/** askQuestionStream wrapper */
export async function askQuestionStream(url, payload, onChunk) {
  return askStreamRaw(url, payload, onChunk);
}
