import { useMemo, useState } from "react";
import type { SignalsFile, SymbolEntry } from "../api/types";
import { useData } from "../hooks/useData";

/** "Pidilite Industries Limited" -> "Pidilite Industries" */
export function shortName(name: string): string {
  return name.replace(/\s+(Limited|Ltd\.?)$/i, "");
}

/** Every company with a ready dossier: the investor's holdings first, then everything else researched. */
export function instantGroups(all: SymbolEntry[], holdings: Set<string>) {
  const ready = all.filter((s) => s.precomputed).sort((a, b) => shortName(a.name).localeCompare(shortName(b.name)));
  return { holdings: ready.filter((s) => holdings.has(s.symbol)), others: ready.filter((s) => !holdings.has(s.symbol)) };
}

function InstantList({ title, entries }: { title: string; entries: SymbolEntry[] }) {
  if (entries.length === 0) return null;
  return (
    <section className="mt-6">
      <h2 className="text-[13px] font-semibold text-muted">{title}</h2>
      <ul className="mt-1">
        {entries.map((s) => (
          <li key={s.symbol} className="border-t border-line">
            <a href={`#/ask/${encodeURIComponent(s.symbol)}`} className="flex items-baseline justify-between gap-3 py-2.5">
              <span className="min-w-0 truncate font-serif text-[17px]">{shortName(s.name)}</span>
              <span className="shrink-0 text-[12px] text-muted">{s.symbol}</span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** ≤ 8 matches on symbol prefix or company-name substring. */
export function matchSymbols(all: SymbolEntry[], query: string): SymbolEntry[] {
  const q = query.trim().toUpperCase();
  if (!q) return [];
  const prefix = all.filter((s) => s.symbol.startsWith(q));
  const byName = all.filter((s) => !s.symbol.startsWith(q) && s.name.toUpperCase().includes(q));
  return [...prefix, ...byName].slice(0, 8);
}

const open = (symbol: string) => (window.location.hash = `#/ask/${encodeURIComponent(symbol)}`);

export function SymbolSearch() {
  const symbols = useData<SymbolEntry[]>("symbols.json");
  const signals = useData<SignalsFile>("signals.json"); // its names are the portfolio's holdings
  const [query, setQuery] = useState("");
  const all = symbols.status === "ok" ? symbols.data : [];
  const matches = useMemo(() => matchSymbols(all, query), [all, query]);
  const groups = useMemo(
    () => instantGroups(all, new Set(signals.status === "ok" ? Object.keys(signals.data.names) : [])),
    [all, signals],
  );

  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        const pick = matches[0]?.symbol ?? query.trim().toUpperCase();
        if (pick) open(pick);
      }}
    >
      <label htmlFor="symbol" className="sr-only">NSE ticker or company name</label>
      <input
        id="symbol"
        type="search"
        autoComplete="off"
        autoCapitalize="characters"
        spellCheck={false}
        placeholder="Ticker or company, e.g. KOTAKBANK"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="w-full rounded-md border border-line bg-surface px-3 py-2.5 text-[16px] placeholder:text-muted"
      />
      {matches.length > 0 && (
        <ul className="mt-1">
          {matches.map((s) => (
            <li key={s.symbol} className="border-b border-line last:border-b-0">
              <a href={`#/ask/${encodeURIComponent(s.symbol)}`} className="flex items-baseline justify-between gap-3 py-2.5">
                <span className="min-w-0 truncate">
                  <span className="font-semibold">{s.symbol}</span> <span className="text-muted">{s.name}</span>
                </span>
                {s.precomputed && <span className="shrink-0 text-[12px] text-muted">Instant</span>}
              </a>
            </li>
          ))}
        </ul>
      )}
      {!query.trim() && (
        <>
          <p className="mt-4 text-[13px] text-muted">
            These open instantly. Any other NSE company is researched live: usually 10–30 minutes, and FINN tells you when it’s ready.
          </p>
          <InstantList title={`Your holdings (${groups.holdings.length})`} entries={groups.holdings} />
          <InstantList title={`Also researched (${groups.others.length})`} entries={groups.others} />
        </>
      )}
    </form>
  );
}
