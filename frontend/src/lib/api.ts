const configuredApiBaseUrl =
  typeof process !== "undefined" ? process.env.BUN_PUBLIC_API_BASE_URL?.replace(/\/$/, "") : "";
const isLocalBrowser =
  typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname);

export const API_BASE_URL = configuredApiBaseUrl || (isLocalBrowser ? "http://127.0.0.1:8000" : "");

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers);
  if (options?.body !== undefined && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: headers.entries().next().done ? undefined : headers,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}
