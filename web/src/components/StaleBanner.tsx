import { relativeTime } from "../lib/format";

export function StaleBanner({ asOf }: { asOf: string }) {
  return (
    <p role="status" className="mb-5 border-l-[3px] border-critical pl-3 text-[13px] text-muted">
      Data as of {relativeTime(asOf)}. FINN refreshes after each market session; this view may be missing newer filings.
    </p>
  );
}
