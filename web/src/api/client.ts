/** Static snapshot files ship with the site under data/; the Render service is only for live research. */
export const apiBase: string = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export function dataUrl(path: string): string {
  return `./data/${path.replace(/^\//, "")}`;
}

export async function getJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return (await res.json()) as T;
}
