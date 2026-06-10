"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import * as api from "@/lib/api";
import type { UserOut } from "@/lib/types";

interface AuthContextValue {
  user: UserOut | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  setUser: (user: UserOut) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function load() {
      if (!api.getToken()) {
        if (active) setLoading(false);
        return;
      }
      try {
        const current = await api.me();
        if (active) setUser(current);
      } catch {
        api.clearToken();
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    // The API client fires this when an authed request gets a 401 (expired/invalid token).
    function onUnauthorized() {
      setUser(null);
    }
    window.addEventListener("medexplain:unauthorized", onUnauthorized);
    return () => window.removeEventListener("medexplain:unauthorized", onUnauthorized);
  }, []);

  async function login(email: string, password: string) {
    const token = await api.login(email, password);
    api.setToken(token.access_token);
    setUser(token.user);
  }

  async function register(email: string, password: string, fullName?: string) {
    // Register returns the created user (201); then we log in to obtain a token.
    await api.register(email, password, fullName ?? null);
    await login(email, password);
  }

  function logout() {
    api.clearToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/** Redirect to /login if not authenticated. Use at the top of protected pages. */
export function useRequireAuth() {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);
  return { user, loading };
}
