const API_BASE = "http://127.0.0.1:8000";

export async function api(path, method = "GET", body = null) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE}${path}`, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

export function saveState(state) {
  localStorage.setItem("fyp_state", JSON.stringify(state));
}
export function loadState() {
  const s = localStorage.getItem("fyp_state");
  return s ? JSON.parse(s) : {};
}
