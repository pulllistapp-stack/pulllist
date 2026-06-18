"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import {
  clearToken,
  fetchMe,
  getToken,
  login as apiLogin,
  loginWithGoogle as apiLoginWithGoogle,
  saveToken,
  signup as apiSignup,
  User,
} from "@/lib/auth";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  signup: (email: string, password: string, name?: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await fetchMe();
      setUser(me);
    } catch {
      clearToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signup = useCallback(
    async (email: string, password: string, name?: string) => {
      const res = await apiSignup(email, password, name);
      saveToken(res.access_token);
      setUser(res.user);
    },
    [],
  );

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiLogin(email, password);
    saveToken(res.access_token);
    setUser(res.user);
  }, []);

  const loginWithGoogle = useCallback(async (credential: string) => {
    const res = await apiLoginWithGoogle(credential);
    saveToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, loading, signup, login, loginWithGoogle, logout, refresh }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
