import { useEffect, useState } from "react";
import { loadData, NotFound } from "../api/client";

export type DataState<T> = { status: "loading" } | { status: "empty" } | { status: "error" } | { status: "ok"; data: T };

export function useData<T>(path: string): DataState<T> {
  const [state, setState] = useState<DataState<T>>({ status: "loading" });
  useEffect(() => {
    let cancelled = false;
    loadData<T>(path)
      .then((data) => !cancelled && setState({ status: "ok", data }))
      .catch((e) => !cancelled && setState({ status: e instanceof NotFound ? "empty" : "error" }));
    return () => {
      cancelled = true;
    };
  }, [path]);
  return state;
}
