import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Chat, resetConversation } from "../screens/Chat";
import { chatError } from "./chat";

const answer = {
  points: [{ text: "Polycab is nearly debt-free.", source_ids: ["POLYCAB#2"] }],
  citations: [{ source_id: "POLYCAB#2", url: "https://www.screener.in/company/POLYCAB/", page: null, label: "POLYCAB Screener" }],
  pending: [{ symbol: "KOTAKBANK", name: "Kotak Mahindra Bank Limited" }],
  symbols: ["POLYCAB"],
  not_covered: false,
};

function mockFetch(...bodies: unknown[]) {
  const fn = vi.fn();
  for (const b of bodies) fn.mockResolvedValueOnce(new Response(JSON.stringify(b), { status: 200 }));
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  cleanup();
  resetConversation();
  vi.unstubAllGlobals();
});

describe("Chat", () => {
  it("renders cited points and a pending line with a research link", async () => {
    mockFetch(answer);
    render(<Chat apiBase="https://api.test" />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Polycab vs Kotak?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Polycab is nearly debt-free.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "POLYCAB Screener" }).getAttribute("href")).toBe("https://www.screener.in/company/POLYCAB/");
    expect(screen.getByText("Research pending for Kotak Mahindra Bank.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Research it" }).getAttribute("href")).toBe("#/ask/KOTAKBANK");
  });

  it("sends previous symbols as context", async () => {
    const fn = mockFetch(answer, { ...answer, pending: [] });
    render(<Chat apiBase="https://api.test" />);
    const box = screen.getByRole("textbox");
    fireEvent.change(box, { target: { value: "Is Polycab's debt a concern?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText("Polycab is nearly debt-free.");
    fireEvent.change(box, { target: { value: "what about its margins?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(2));
    expect(JSON.parse(fn.mock.calls[1][1].body)).toEqual({ question: "what about its margins?", context: ["POLYCAB"] });
  });

  it("suggestion chip sends the question", async () => {
    const fn = mockFetch(answer);
    render(<Chat apiBase="https://api.test" />);
    fireEvent.click(screen.getByRole("button", { name: "Which holdings missed guidance?" }));
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(1));
    expect(JSON.parse(fn.mock.calls[0][1].body).question).toBe("Which holdings missed guidance?");
  });
});

describe("chatError", () => {
  it("maps index_loading and limits to fixed copy", () => {
    expect(chatError(503, "index_loading")).toBe("Chat is starting up; try again in a minute.");
    expect(chatError(429, "rate_limited")).toBe("You've asked 30 questions this hour. Try again later.");
    expect(chatError(0, undefined)).toBe("Couldn't reach the research server.");
  });
});

describe("conversation", () => {
  it("survives leaving the tab and coming back", async () => {
    mockFetch(answer);
    const first = render(<Chat apiBase="https://api.test" />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Is Polycab's debt a concern?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText("Polycab is nearly debt-free.");
    first.unmount();
    render(<Chat apiBase="https://api.test" />);
    expect(screen.getByText("Polycab is nearly debt-free.")).toBeTruthy();
  });
});
