import { TabBar } from "./components/TabBar";
import { useAlerts } from "./hooks/useAlerts";
import { useHashRoute } from "./hooks/useHashRoute";
import { useSettings } from "./hooks/useSettings";
import { Ask } from "./screens/Ask";
import { Brief } from "./screens/Brief";
import { Portfolio } from "./screens/Portfolio";
import { Watch } from "./screens/Watch";

export default function App() {
  const { tab, param, query } = useHashRoute();
  const [settings, setSettings] = useSettings();
  const inbox = useAlerts(settings); // one instance, so the badge and the Watch list stay in step
  return (
    <div className="min-h-dvh">
      <main className="mx-auto w-full max-w-xl px-4 pt-[calc(env(safe-area-inset-top)+28px)] pb-[calc(env(safe-area-inset-bottom)+88px)]">
        {tab === "brief" && <Brief settings={settings} focusId={param} />}
        {tab === "portfolio" && <Portfolio />}
        {tab === "watch" && <Watch inbox={inbox} settings={settings} onSettings={setSettings} />}
        {tab === "ask" && <Ask symbol={param} eventId={query.event ?? null} />}
      </main>
      <TabBar active={tab} unread={inbox.unread} />
    </div>
  );
}
