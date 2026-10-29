import type { ReactNode } from "react";

/** A flat tile for one number: small label, large tabular figure, optional coloured detail. Numbers only. */
export function StatBox({ label, value, tone = "", children }: { label: string; value: ReactNode; tone?: string; children?: ReactNode }) {
  return (
    <div className="min-w-0 rounded-md bg-surface px-3 py-2.5">
      <dt className="truncate text-[12px] text-muted">{label}</dt>
      <dd className={`mt-0.5 text-[18px] leading-tight font-semibold ${tone}`}>{value}</dd>
      {children && <dd className="mt-1 text-[12px] leading-snug">{children}</dd>}
    </div>
  );
}

export function StatGrid({ children, cols = 2, className = "" }: { children: ReactNode; cols?: 2 | 3; className?: string }) {
  return <dl className={`grid gap-2 ${cols === 3 ? "grid-cols-3" : "grid-cols-2"} ${className}`}>{children}</dl>;
}
