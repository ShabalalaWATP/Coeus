/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import {
  ApiClient,
  ApiError,
  apiClient,
  type AuthSession,
  type LoginRequest,
} from "../api-client/client";

type AuthStatus = "loading" | "authenticated" | "anonymous" | "expired";

type AuthContextValue = {
  status: AuthStatus;
  session: AuthSession | null;
  login: (request: LoginRequest) => Promise<AuthSession>;
  logout: () => Promise<void>;
};

type AuthProviderProps = PropsWithChildren<{
  client?: ApiClient;
  initialSession?: AuthSession | null;
}>;

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children, client = apiClient, initialSession }: AuthProviderProps) {
  const [session, setSession] = useState<AuthSession | null>(initialSession ?? null);
  const [status, setStatus] = useState<AuthStatus>(() =>
    initialSession === undefined
      ? "loading"
      : initialSession === null
        ? "anonymous"
        : "authenticated",
  );

  useEffect(() => {
    if (initialSession !== undefined) {
      return;
    }
    let active = true;
    async function loadCurrentUser() {
      try {
        const currentSession = await client.getCurrentUser();
        if (active) {
          setSession(currentSession);
          setStatus("authenticated");
        }
      } catch (error) {
        if (active) {
          setSession(null);
          setStatus(
            error instanceof ApiError && error.code === "session_expired" ? "expired" : "anonymous",
          );
        }
      }
    }
    void loadCurrentUser();
    return () => {
      active = false;
    };
  }, [client, initialSession]);

  const login = useCallback(
    async (request: LoginRequest) => {
      const nextSession = await client.login(request);
      setSession(nextSession);
      setStatus("authenticated");
      return nextSession;
    },
    [client],
  );

  const logout = useCallback(async () => {
    const csrfToken = session?.csrfToken;
    if (csrfToken !== undefined) {
      await client.logout(csrfToken);
    }
    setSession(null);
    setStatus("anonymous");
  }, [client, session?.csrfToken]);

  const value = useMemo(
    () => ({
      status,
      session,
      login,
      logout,
    }),
    [login, logout, session, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (value === undefined) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return value;
}
