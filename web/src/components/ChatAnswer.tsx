import type { ChatAnswer as Answer } from "../lib/chat";
import { companyName } from "../lib/format";

function href(url: string, page: number | null): string {
  return page ? `${url}#page=${page}` : url;
}

/** One answer: cited points, then any companies that still need research. */
export function ChatAnswer({ answer }: { answer: Answer }) {
  const cite = Object.fromEntries(answer.citations.map((c) => [c.source_id, c]));
  return (
    <div className="space-y-2">
      {answer.points.length > 0 && (
        <ul className="space-y-2">
          {answer.points.map((p) => (
            <li key={p.text} className={`text-[15px] ${answer.not_covered ? "text-muted" : ""}`}>
              {p.text}
              {[...new Set(p.source_ids)].map((id) =>
                cite[id]?.url ? (
                  <a key={id} href={href(cite[id].url!, cite[id].page)} target="_blank" rel="noreferrer"
                    className="ml-1 inline-block rounded-sm border border-line px-1.5 py-px align-[1px] text-[11px] whitespace-nowrap text-muted hover:text-text">
                    {cite[id].label}
                  </a>
                ) : null,
              )}
            </li>
          ))}
        </ul>
      )}
      {answer.pending.map((c) => (
        <p key={c.symbol} className="text-[14px] text-muted">
          Research pending for {companyName(c.name)}.{" "}
          <a href={`#/ask/${encodeURIComponent(c.symbol)}`} className="font-semibold text-notable">Research it</a>
        </p>
      ))}
    </div>
  );
}
