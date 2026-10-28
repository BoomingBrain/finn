import type { BullBearData, Citation } from "../api/types";
import { Chips } from "./CitationChip";

function Side({ title, points, citations }: { title: string; points: BullBearData["bull"]; citations: Citation[] }) {
  return (
    <div className="min-w-0">
      <h3 className="font-serif text-[18px] font-medium">{title}</h3>
      {points.length === 0 ? (
        <p className="mt-1 text-[14px] text-muted">Nothing the sources support.</p>
      ) : (
        <ul className="mt-1 space-y-2">
          {points.map((p) => (
            <li key={p.text} className="text-[14px]">
              {p.text}
              <Chips ids={p.source_ids} citations={citations} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function BullBearSection({ data, citations }: { data: BullBearData; citations: Citation[] }) {
  return (
    <div className="mt-2 grid gap-5 sm:grid-cols-2">
      <Side title="Bull case" points={data.bull} citations={citations} />
      <Side title="Bear case" points={data.bear} citations={citations} />
    </div>
  );
}
