import { Statement } from "../components/Statement";
import { useApiHealth, type ApiHealth } from "../hooks/useApiHealth";

const SERVER_COPY: Record<ApiHealth, string> = {
  unset: "Live research for other companies isn't connected yet.",
  checking: "Checking the live research server. If it was asleep, this takes about a minute.",
  ok: "Live research server is ready.",
  down: "Live research server isn't responding. Companies FINN has already researched still open instantly.",
};

export function Ask({ symbol }: { symbol: string | null }) {
  const health = useApiHealth();
  return (
    <>
      <Statement detail="Every answer comes from the company's own annual reports, earnings-call transcripts and filed results, with a link to the page it came from.">
        {symbol ? `Research on ${symbol} opens here.` : "Ask about any NSE company."}
      </Statement>
      <p className="flex items-start gap-2 text-[13px] text-muted" role="status">
        <span
          aria-hidden="true"
          className={`mt-[6px] h-2 w-2 shrink-0 rounded-full ${health === "ok" ? "bg-up" : health === "down" ? "bg-down" : "bg-line"}`}
        />
        {SERVER_COPY[health]}
      </p>
    </>
  );
}
