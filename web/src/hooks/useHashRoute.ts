import { useEffect, useState } from "react";

export type Tab = "brief" | "portfolio" | "watch" | "chat" | "ask";
export type Route = { tab: Tab; param: string | null; query: Record<string, string> };

const TABS: Tab[] = ["brief", "portfolio", "watch", "chat", "ask"];

/** "#/ask/PIDILITIND?event=abc" -> { tab: "ask", param: "PIDILITIND", query: { event: "abc" } } */
export function parseHash(hash: string): Route {
  const [path, search = ""] = hash.replace(/^#\/?/, "").split("?");
  const [tab, param] = path.split("/");
  const query = Object.fromEntries(new URLSearchParams(search));
  return TABS.includes(tab as Tab)
    ? { tab: tab as Tab, param: param ? decodeURIComponent(param) : null, query }
    : { tab: "brief", param: null, query: {} };
}

export function useHashRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
