import type { ReactNode } from "react";

/** The one plain-language sentence that opens each screen. */
export function Statement({ children, detail }: { children: ReactNode; detail?: ReactNode }) {
  return (
    <header className="mb-6">
      <h1 className="font-serif text-[28px] leading-[1.18] font-medium tracking-[-0.01em] text-balance">{children}</h1>
      {detail && <p className="mt-3 max-w-[60ch] text-muted">{detail}</p>}
    </header>
  );
}
