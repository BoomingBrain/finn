import type { ReactNode } from "react";

/** Placeholder lines while a section streams in. */
export function SectionSkeleton({ title }: { title: string }) {
  return (
    <section className="border-t border-line py-5" aria-busy="true">
      <h2 className="text-[13px] font-semibold text-muted">{title}</h2>
      <div className="mt-3 space-y-2" aria-hidden="true">
        {[92, 78, 85].map((w) => (
          <div key={w} className="h-3 animate-pulse rounded-sm bg-surface" style={{ width: `${w}%` }} />
        ))}
      </div>
    </section>
  );
}

/** A section frame; an unavailable section shows its fixed reason instead of content. */
export function Section({ title, reason, children }: { title: string; reason?: string | null; children?: ReactNode }) {
  return (
    <section className="border-t border-line py-5">
      <h2 className="text-[13px] font-semibold text-muted">{title}</h2>
      {reason ? <p className="mt-2 text-[14px] text-muted">{reason}.</p> : children}
    </section>
  );
}
