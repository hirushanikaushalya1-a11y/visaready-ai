"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, post } from "./api";
import type { Me } from "./types";

type AuthState = { me: Me | null; loading: boolean; reload: () => Promise<Me | null>; logout: () => Promise<void> };
const Ctx = createContext<AuthState>({ me: null, loading: true, reload: async () => null, logout: async () => {} });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    try {
      const m = await api<Me>("/auth/me");
      setMe(m);
      return m;
    } catch {
      setMe(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);
  const logout = useCallback(async () => {
    await post("/auth/logout").catch(() => {});
    setMe(null);
  }, []);
  useEffect(() => {
    api<Me>("/auth/me")
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setLoading(false));
  }, []);
  return <Ctx.Provider value={{ me, loading, reload, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);

/** Redirects to /login when not signed in; optionally requires a permission. */
export function useRequireAuth(permission?: string) {
  const { me, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (loading) return;
    if (!me) router.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`);
    else if (permission && !me.permissions.includes(permission)) router.replace("/dashboard");
  }, [me, loading, permission, router]);
  return { me, ready: !loading && !!me && (!permission || me.permissions.includes(permission)) };
}

/** Small data hook: data, error, loading, load() to refetch, setData. */
export function useLoad<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    api<T>(path)
      .then((d) => { if (!cancelled) { setData(d); setError(null); } })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [path, version]);
  const load = useCallback(() => setVersion((v) => v + 1), []);
  return { data, error, loading, load, setData };
}
