import { useMemo, useState } from "react";
import type { SymbolEntry } from "../api/types";
import { useData } from "../hooks/useData";
import { DEMO_TICKERS } from "../lib/research";

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
  const [query, setQuery] = useState("");
  const all = symbols.status === "ok" ? symbols.data : [];
  const matches = useMemo(() => matchSymbols(all, query), [all, query]);

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
        <div className="mt-4">
          <p className="text-[13px] text-muted">Ready to open instantly:</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {DEMO_TICKERS.map((s) => (
              <a key={s} href={`#/ask/${s}`} className="rounded-md border border-line px-3 py-1.5 text-[14px]">
                {s}
              </a>
            ))}
          </div>
        </div>
      )}
    </form>
  );
}
