import { useEffect, useState } from "react";

export type Tab = "brief" | "watch" | "ask";
export type Route = { tab: Tab; param: string | null };

const TABS: Tab[] = ["brief", "watch", "ask"];

export function parseHash(hash: string): Route {
  const [tab, param] = hash.replace(/^#\/?/, "").split("/");
  return TABS.includes(tab as Tab) ? { tab: tab as Tab, param: param ? decodeURIComponent(param) : null } : { tab: "brief", param: null };
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
