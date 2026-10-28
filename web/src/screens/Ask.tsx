import type { BullBearData, BusinessData, DeliveryData, SectionEvent, SectionName, SnapshotData } from "../api/types";
import { BuildProgress } from "../components/BuildProgress";
import { BullBearSection } from "../components/BullBearSection";
import { BusinessSection } from "../components/BusinessSection";
import { ContextStrip } from "../components/ContextStrip";
import { DeliveryScorecard } from "../components/DeliveryScorecard";
import { Section, SectionSkeleton } from "../components/SectionSkeleton";
import { SnapshotSection } from "../components/SnapshotSection";
import { Statement } from "../components/Statement";
import { SymbolSearch } from "../components/SymbolSearch";
import { useApiHealth, type ApiHealth } from "../hooks/useApiHealth";
import { useResearch } from "../hooks/useResearch";
import { coverageText } from "../lib/research";

const SERVER_COPY: Record<ApiHealth, string> = {
  unset: "Live research for other companies isn't connected yet.",
  checking: "Checking the live research server. If it was asleep, this takes about a minute.",
  ok: "Live research server is ready.",
  down: "Live research server isn't responding. Companies FINN has already researched still open instantly.",
};

const ORDER: { name: SectionName; title: string }[] = [
  { name: "snapshot", title: "Financial snapshot" },
  { name: "delivery", title: "Promised vs delivered" },
  { name: "business", title: "The business" },
  { name: "bull_bear", title: "Bull vs bear" },
];

function Body({ s }: { s: SectionEvent }) {
  const c = s.citations;
  switch (s.section) {
    case "snapshot":
      return <SnapshotSection data={s.data as unknown as SnapshotData} citations={c} />;
    case "delivery":
      return <DeliveryScorecard data={s.data as unknown as DeliveryData} citations={c} />;
    case "business":
      return <BusinessSection data={s.data as unknown as BusinessData} citations={c} />;
    case "bull_bear":
      return <BullBearSection data={s.data as unknown as BullBearData} citations={c} />;
  }
}

function ServerStatus() {
  const health = useApiHealth();
  return (
    <p className="mb-4 flex items-start gap-2 text-[13px] text-muted" role="status">
      <span
        aria-hidden="true"
        className={`mt-[6px] h-2 w-2 shrink-0 rounded-full ${health === "ok" ? "bg-up" : health === "down" ? "bg-down" : "bg-line"}`}
      />
      {SERVER_COPY[health]}
    </p>
  );
}

function Dossier({ symbol, eventId }: { symbol: string; eventId: string | null }) {
  const { sections, done, waking, error, progress } = useResearch(symbol);
  const snapshot = sections.find((s) => s.section === "snapshot");
  const snapData = snapshot?.data as SnapshotData | undefined;
  const name = snapData?.name ?? symbol;
  const coverage = coverageText(snapData?.sources, snapData?.built_at);

  if (error && sections.length === 0)
    return (
      <>
        <Statement detail={error.message}>No research on {symbol} right now.</Statement>
        <a href="#/ask" className="text-notable">Search another company</a>
      </>
    );

  return (
    <>
      {eventId && <ContextStrip eventId={eventId} />}
      <Statement detail={done ? coverage ?? undefined : undefined}>{name}</Statement>
      {!done && <BuildProgress progress={progress} waking={waking} />}
      {ORDER.map(({ name: section, title }) => {
        const s = sections.find((x) => x.section === section);
        if (!s) return done ? null : <SectionSkeleton key={section} title={title} />;
        return (
          <Section key={section} title={title} reason={s.status === "unavailable" ? s.reason : null}>
            {s.status === "ready" && s.data && <Body s={s} />}
          </Section>
        );
      })}
      {error && <p className="mt-4 text-[14px] text-down">{error.message}</p>}
      <a href="#/ask" className="mt-6 inline-block text-notable">Search another company</a>
    </>
  );
}

export function Ask({ symbol, eventId = null }: { symbol: string | null; eventId?: string | null }) {
  if (symbol) return <Dossier key={symbol} symbol={symbol.toUpperCase()} eventId={eventId} />;
  return (
    <>
      <Statement detail="Every answer comes from the company's own annual reports, earnings-call transcripts and filed results, with a link to the page it came from.">
        Ask about any NSE company.
      </Statement>
      <ServerStatus />
      <SymbolSearch />
    </>
  );
}
