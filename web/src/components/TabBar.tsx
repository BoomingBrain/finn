import type { Tab } from "../hooks/useHashRoute";

const ICONS: Record<Tab, JSX.Element> = {
  brief: <path d="M5 6h14M5 12h14M5 18h9" />,
  portfolio: <path d="M4 8h16v11H4zM9 8V5h6v3M4 13h16" />,
  watch: <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0" />,
  ask: <path d="M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14zM16 16l5 5" />,
};
const LABELS: Record<Tab, string> = { brief: "Brief", portfolio: "Portfolio", watch: "Watch", ask: "Ask" };

export function TabBar({ active, unread = 0 }: { active: Tab; unread?: number }) {
  return (
    <nav
      aria-label="Sections"
      className="fixed inset-x-0 bottom-0 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]"
    >
      <ul className="mx-auto flex max-w-xl">
        {(Object.keys(LABELS) as Tab[]).map((tab) => {
          const current = tab === active;
          return (
            <li key={tab} className="flex-1">
              <a
                href={`#/${tab}`}
                aria-current={current ? "page" : undefined}
                className={`relative flex h-14 flex-col items-center justify-center gap-0.5 text-[12px] ${
                  current ? "text-text" : "text-muted"
                }`}
              >
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth={current ? 2 : 1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  {ICONS[tab]}
                </svg>
                <span className={current ? "font-semibold" : undefined}>{LABELS[tab]}</span>
                {tab === "watch" && unread > 0 && (
                  <span className="absolute top-2 left-1/2 ml-2 h-2 w-2 rounded-full bg-critical" aria-label={`${unread} unread alerts`} />
                )}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
