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

export class NotFound extends Error {}

const cache = new Map<string, Promise<unknown>>();

/** A snapshot file, fetched once per visit and shared by every screen. Rejects with NotFound on 404. */
export function loadData<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    const p = fetch(dataUrl(path), { cache: "no-cache" }).then(async (r) => {
      if (r.status === 404) throw new NotFound(path);
      if (!r.ok) throw new Error(`${r.status} ${path}`);
      return r.json();
    });
    p.catch(() => cache.delete(path)); // let a later visit retry
    cache.set(path, p);
  }
  return cache.get(path) as Promise<T>;
}
