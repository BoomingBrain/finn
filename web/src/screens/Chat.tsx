import { useState } from "react";
import { apiBase as defaultApiBase } from "../api/client";
import { ChatAnswer } from "../components/ChatAnswer";
import { Statement } from "../components/Statement";
import { sendChat, type ChatAnswer as Answer } from "../lib/chat";

const SUGGESTIONS = ["Which holdings missed guidance?", "Is Polycab's debt a concern?", "Compare margins of Infosys and Persistent"];

type Turn = { question: string; answer?: Answer; error?: string };

/** Questions answered only from FINN's research reports, each point with its source. */
export function Chat({ apiBase = defaultApiBase }: { apiBase?: string }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [waiting, setWaiting] = useState(false);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || waiting) return;
    const context = [...turns].reverse().find((t) => t.answer)?.answer?.symbols ?? [];
    setTurns((t) => [...t, { question: q }]);
    setDraft("");
    setWaiting(true);
    const result = await sendChat(apiBase, q, context);
    setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { ...turn, ...(result.ok ? { answer: result.answer } : { error: result.error }) } : turn)));
    setWaiting(false);
  }

  return (
    <div className="pb-20">
      <Statement detail="Answers come only from FINN's reports, each with its source.">
        Ask about your holdings and researched companies.
      </Statement>
      {turns.length === 0 && (
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" onClick={() => ask(s)} className="rounded-md border border-line px-3 py-1.5 text-left text-[14px]">
              {s}
            </button>
          ))}
        </div>
      )}
      <ol className="space-y-5">
        {turns.map((t, i) => (
          <li key={i} className="space-y-2">
            <p className="ml-auto w-fit max-w-[85%] rounded-md bg-surface px-3 py-2 text-[15px]">{t.question}</p>
            {t.answer && <ChatAnswer answer={t.answer} />}
            {t.error && <p className="text-[14px] text-down">{t.error}</p>}
            {!t.answer && !t.error && <p className="text-[14px] text-muted" aria-live="polite">Reading the reports…</p>}
          </li>
        ))}
      </ol>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(draft);
        }}
        className="fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+56px)] border-t border-line bg-bg px-4 py-2"
      >
        <div className="mx-auto flex max-w-xl gap-2">
          <label htmlFor="chat" className="sr-only">Your question</label>
          <input id="chat" value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={300} autoComplete="off"
            placeholder="Ask about a company"
            className="min-w-0 flex-1 rounded-md border border-line bg-surface px-3 py-2 text-[16px] placeholder:text-muted" />
          <button type="submit" disabled={waiting || !draft.trim()} className="rounded-md bg-surface px-3 text-[14px] font-semibold text-notable disabled:text-muted">
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
