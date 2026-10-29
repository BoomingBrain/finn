export type ChatCitation = { source_id: string; url: string | null; page: number | null; label: string };
export type ChatAnswer = {
  points: { text: string; source_ids: string[] }[];
  citations: ChatCitation[];
  pending: { symbol: string; name: string }[];
  symbols: string[];
  not_covered: boolean;
};
export type ChatResult = { ok: true; answer: ChatAnswer } | { ok: false; error: string };

/** Fixed copy for every way a question can fail. */
export function chatError(status: number, code: string | undefined): string {
  if (code === "index_loading") return "Chat is starting up; try again in a minute.";
  if (code === "rate_limited") return "You've asked 30 questions this hour. Try again later.";
  if (code === "budget_exhausted") return "Today's AI budget is used up.";
  if (code === "bad_question") return "Ask a question of up to 300 characters.";
  return status === 0 ? "Couldn't reach the research server." : "Couldn't reach the research server.";
}

/** Asks the research server; `context` carries the companies of the previous answer for follow-ups. */
export async function sendChat(apiBase: string, question: string, context: string[]): Promise<ChatResult> {
  if (!apiBase) return { ok: false, error: chatError(0, undefined) };
  try {
    const res = await fetch(`${apiBase}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, context }),
    });
    const body = await res.json().catch(() => ({}));
    return res.ok ? { ok: true, answer: body as ChatAnswer } : { ok: false, error: chatError(res.status, body.error) };
  } catch {
    return { ok: false, error: chatError(0, undefined) };
  }
}
