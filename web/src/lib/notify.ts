/** Whether to announce a finished analysis: not when the investor is already looking at it. */
export function shouldAnnounce(symbol: string, hash: string, hidden: boolean): boolean {
  const viewing = decodeURIComponent(hash.replace(/^#\/?/, "").split("?")[0]).toUpperCase() === `ASK/${symbol}`;
  return hidden || !viewing;
}

export function notificationsSupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

/** Asks once; resolves true when system notifications are allowed. */
export async function enableNotifications(): Promise<boolean> {
  if (!notificationsSupported()) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  return (await Notification.requestPermission()) === "granted";
}

/** A system notification that opens the dossier when tapped; silently skipped without permission. */
export function systemNotify(symbol: string, name: string) {
  if (!notificationsSupported() || Notification.permission !== "granted") return;
  try {
    const n = new Notification(`${name} research is ready`, {
      body: "Promised vs delivered, the business and bull vs bear, each with page citations.",
      tag: `finn-${symbol}`,
    });
    n.onclick = () => {
      window.focus();
      window.location.hash = `#/ask/${encodeURIComponent(symbol)}`;
      n.close();
    };
  } catch {
    // some mobile browsers only allow notifications from a service worker; the in-app banner still shows
  }
}
