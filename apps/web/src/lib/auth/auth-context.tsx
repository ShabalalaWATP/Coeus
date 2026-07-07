/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

import {
  ApiClient,
  ApiError,
  apiClient,
  setAuthEventHandlers,
  type AuthSession,
  type LoginRequest,
} from "../api-client/client";

type AuthStatus = "loading" | "authenticated" | "anonymous" | "expired";

type AuthContextValue = {
  status: AuthStatus;
  session: AuthSession | null;
  login: (request: LoginRequest) => Promise<AuthSession>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<AuthSession>;
};

type AuthProviderProps = PropsWithChildren<{
  client?: ApiClient;
  clearSensitiveCache?: () => void;
  initialSession?: AuthSession | null;
}>;

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({
  children,
  clearSensitiveCache = () => undefined,
  client = apiClient,
  initialSession,
}: AuthProviderProps) {
  const [session, setSession] = useState<AuthSession | null>(initialSession ?? null);
  const [status, setStatus] = useState<AuthStatus>(() =>
    initialSession === undefined
      ? "loading"
      : initialSession === null
        ? "anonymous"
        : "authenticated",
  );
  const statusRef = useRef(status);
  statusRef.current = status;

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
          clearSensitiveCache();
        }
      }
    }
    void loadCurrentUser();
    return () => {
      active = false;
    };
  }, [clearSensitiveCache, client, initialSession]);

  // Mirror the initial-load handling for calls made after login: a 401 from
  // any endpoint means the backend session is gone, and a password-change
  // demand locks the app to the change-password screen.
  useEffect(() => {
    setAuthEventHandlers({
      onUnauthorized: () => {
        if (statusRef.current !== "authenticated") {
          return;
        }
        setSession(null);
        setStatus("expired");
        clearSensitiveCache();
      },
      onPasswordChangeRequired: () => {
        setSession((current) =>
          current === null || current.passwordResetRequired === true
            ? current
            : { ...current, passwordResetRequired: true },
        );
      },
    });
    return () => setAuthEventHandlers({});
  }, [clearSensitiveCache]);

  const login = useCallback(
    async (request: LoginRequest) => {
      const nextSession = await client.login(request);
      clearSensitiveCache();
      setSession(nextSession);
      setStatus("authenticated");
      return nextSession;
    },
    [clearSensitiveCache, client],
  );

  const logout = useCallback(async () => {
    const csrfToken = session?.csrfToken;
    try {
      if (csrfToken !== undefined) {
        await client.logout(csrfToken);
      }
    } finally {
      clearSensitiveCache();
      setSession(null);
      setStatus("anonymous");
    }
  }, [clearSensitiveCache, client, session?.csrfToken]);

  const refreshSession = useCallback(async () => {
    const currentSession = await client.getCurrentUser();
    setSession(currentSession);
    setStatus("authenticated");
    return currentSession;
  }, [client]);

  const value = useMemo(
    () => ({
      status,
      session,
      login,
      logout,
      refreshSession,
    }),
    [login, logout, refreshSession, session, status],
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
