"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { apiClient, ApiError } from "@/lib/api/client";
import type { AuthLoginBody, AuthLoginResponse, AuthMeResponse, UserSummary } from "@/lib/api/types";

type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  status: AuthStatus;
  user: UserSummary | null;
  allDomains: boolean;
  domainIds: string[];
  refresh: () => Promise<void>;
  login: (values: AuthLoginBody) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<UserSummary | null>(null);
  const [allDomains, setAllDomains] = useState(false);
  const [domainIds, setDomainIds] = useState<string[]>([]);

  async function refresh() {
    try {
      const data = await apiClient.get<AuthMeResponse>("/api/v1/auth/me");
      setUser(data.user);
      setAllDomains(data.all_domains);
      setDomainIds(data.domain_ids);
      setStatus("authenticated");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setUser(null);
        setAllDomains(false);
        setDomainIds([]);
        setStatus("anonymous");
        return;
      }
      throw error;
    }
  }

  async function login(values: AuthLoginBody) {
    const data = await apiClient.post<AuthLoginResponse>("/api/v1/auth/login", values, { skipCsrf: true });
    setUser(data.user);
    setStatus("authenticated");
  }

  async function logout() {
    try {
      await apiClient.post("/api/v1/auth/logout");
    } finally {
      setUser(null);
      setAllDomains(false);
      setDomainIds([]);
      setStatus("anonymous");
    }
  }

  useEffect(() => {
    refresh().catch(() => {
      setStatus("anonymous");
    });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      allDomains,
      domainIds,
      refresh,
      login,
      logout,
    }),
    [allDomains, domainIds, status, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return value;
}
