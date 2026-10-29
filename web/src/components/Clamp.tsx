import { useState } from "react";

/** Long text from a filing or screener, cut to a few lines with a toggle; short text renders as is. */
export function Clamp({ text, lines = 2, className = "" }: { text: string; lines?: 2 | 3; className?: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > (lines === 2 ? 110 : 170);
  return (
    <div className={className}>
      <p className={!open && long ? (lines === 2 ? "line-clamp-2" : "line-clamp-3") : undefined}>{text}</p>
      {long && (
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="mt-0.5 text-[13px] text-notable">
          {open ? "Less" : "More"}
        </button>
      )}
    </div>
  );
}
