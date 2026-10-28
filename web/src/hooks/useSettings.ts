import { CATEGORY_LABEL } from "../lib/format";
import { DEFAULT_SETTINGS, LIMITS, type Settings } from "../lib/signals";
import { useStoredState } from "./useStoredState";

const clamp = (v: unknown, { min, max }: { min: number; max: number }, fallback: number) =>
  typeof v === "number" && Number.isFinite(v) ? Math.min(max, Math.max(min, v)) : fallback;

/** Thresholds and alert categories, kept on this device. Anything stored that is out of range is repaired. */
export function useSettings(): [Settings, (s: Settings) => void] {
  const [stored, setStored] = useStoredState<Partial<Settings>>("finn.settings", DEFAULT_SETTINGS);
  const settings: Settings = {
    price_move_pct: clamp(stored.price_move_pct, LIMITS.price_move_pct, DEFAULT_SETTINGS.price_move_pct),
    volume_multiple: clamp(stored.volume_multiple, LIMITS.volume_multiple, DEFAULT_SETTINGS.volume_multiple),
    alert_categories: Array.isArray(stored.alert_categories)
      ? stored.alert_categories.filter((c) => c in CATEGORY_LABEL)
      : DEFAULT_SETTINGS.alert_categories,
  };
  return [settings, setStored];
}
