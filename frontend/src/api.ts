const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    const refresh = localStorage.getItem("refresh_token");
    if (!refresh) throw new Error("Your session has expired. Please sign in again.");
    const response = await fetch(`${API_BASE}/auth/token/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.access) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      throw new Error("Your session has expired. Please sign in again.");
    }
    localStorage.setItem("access_token", body.access);
    if (body.refresh) localStorage.setItem("refresh_token", body.refresh);
    return body.access as string;
  })().finally(() => { refreshPromise = null; });
  return refreshPromise;
}

async function request(path: string, options: RequestInit, token: string | null) {
  return fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response = await request(path, options, localStorage.getItem("access_token"));
  if (response.status === 401 && localStorage.getItem("refresh_token")) {
    const token = await refreshAccessToken();
    response = await request(path, options, token);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = body.detail || body.message || Object.values(body).flat().join(" ");
    throw new Error(message || `Request failed (${response.status})`);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export async function download(path: string, filename: string) {
  const token = localStorage.getItem("access_token");
  const response = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Download failed (${response.status})`);
  }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function login(email: string, password: string) {
  const response = await fetch("/api/v1/auth/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Unable to sign in");
  localStorage.setItem("access_token", body.access);
  localStorage.setItem("refresh_token", body.refresh);
  return body;
}
