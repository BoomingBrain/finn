import { TabBar } from "./components/TabBar";
import { useHashRoute } from "./hooks/useHashRoute";
import { Ask } from "./screens/Ask";
import { Brief } from "./screens/Brief";
import { Watch } from "./screens/Watch";

export default function App() {
  const { tab, param } = useHashRoute();
  return (
    <div className="min-h-dvh">
      <main className="mx-auto w-full max-w-xl px-4 pt-[calc(env(safe-area-inset-top)+28px)] pb-[calc(env(safe-area-inset-bottom)+88px)]">
        {tab === "brief" && <Brief />}
        {tab === "watch" && <Watch />}
        {tab === "ask" && <Ask symbol={param} />}
      </main>
      <TabBar active={tab} />
    </div>
  );
}
