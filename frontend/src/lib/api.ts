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

async function request<T>(path: string, options: RequestInit = {}, retries = 2): Promise<T> {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(`${API_URL}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": getApiKey(),
          ...options.headers,
        },
      });

      if (res.status === 401) {
        if (!path.includes("/calendar/") && !path.includes("/test-telegram")) {
          console.warn("401 on", path, "- clearing API key");
          localStorage.removeItem("apt_api_key");
        }
        throw new Error("Unauthorized");
      }

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`API error ${res.status}: ${text}`);
      }

      return res.json();
    } catch (e) {
      if (e instanceof Error && e.message === "Unauthorized") throw e;
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
        continue;
      }
      throw e;
    }
  }
  throw new Error("Request failed");
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
