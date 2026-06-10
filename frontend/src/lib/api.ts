const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getApiKey(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("apt_api_key") || "";
}

export function setApiKey(key: string) {
  localStorage.setItem("apt_api_key", key);
}

export function hasApiKey(): boolean {
  if (typeof window === "undefined") return false;
  return !!localStorage.getItem("apt_api_key");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": getApiKey(),
      ...options.headers,
    },
  });

  if (res.status === 401 && !path.includes("/calendar/")) {
    localStorage.removeItem("apt_api_key");
    window.location.href = "/";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }

  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
};
