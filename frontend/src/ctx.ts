import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, errMsg, type SessionUser } from "./api";

export type ShopInfo = { name: string; phone: string; city: string };
export type AppCtxValue = {
  user: SessionUser | null;
  shop: ShopInfo;
  /** increments after every successful mutation so all screens refetch */
  bump: number;
  refresh: () => void;
};

export const AppCtx = createContext<AppCtxValue>({
  user: null,
  shop: { name: "", phone: "", city: "" },
  bump: 0,
  refresh: () => {},
});
export const useApp = () => useContext(AppCtx);

/** Fetch helper: reloads whenever `bump` changes or `path` changes. Pass null to skip. */
export function useFetch<T = any>(path: string | null) {
  const { bump } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!path) return;
    let alive = true;
    setLoading(true);
    api
      .get<T>(path)
      .then((d) => alive && (setData(d), setError("")))
      .catch((e) => alive && setError(errMsg(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [path, bump, tick]);
  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { data, loading, error, reload };
}

/** The invoice currently shown in the receipt modal (set right before opening it). */
export const receiptStore: { invoice: any } = { invoice: null };

/** Context handed to the next modal that opens (e.g. which debt to repay). */
export const modalStore: { data: any } = { data: null };
