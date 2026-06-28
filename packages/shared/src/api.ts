/** Thin fetch helper for the FastAPI backend. Pass a Supabase access token to authenticate. */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, headers, ...rest } = init;
  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status} ${res.statusText}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}
