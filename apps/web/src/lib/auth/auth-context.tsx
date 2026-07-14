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
  defaultAuthApi,
  type AuthApi,
  type AuthSession,
  type ChangePasswordRequest,
  type LoginRequest,
} from "../api-client/auth";
import { ApiError, setAuthEventHandlers } from "../api-client/client";
import {
  LOGOUT_MARKER_KEY,
  logoutTransitionError,
  readLogoutMarker,
  writeLogoutMarker,
} from "./logout-state";

type AuthStatus =
  "loading" | "authenticated" | "anonymous" | "expired" | "logging_out" | "logout_unconfirmed";

type AuthContextValue = {
  status: AuthStatus;
  session: AuthSession | null;
  login: (request: LoginRequest) => Promise<AuthSession>;
  changePassword: (request: ChangePasswordRequest) => Promise<AuthSession>;
  logout: () => Promise<boolean>;
  refreshSession: () => Promise<AuthSession>;
};

type AuthProviderProps = PropsWithChildren<{
  authApi?: AuthApi;
  clearSensitiveCache?: () => void;
  initialSession?: AuthSession | null;
}>;

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({
  children,
  clearSensitiveCache = () => undefined,
  authApi = defaultAuthApi,
  initialSession,
}: AuthProviderProps) {
  const logoutWasPending = useRef(readLogoutMarker() !== null).current;
  const [session, setSession] = useState<AuthSession | null>(
    logoutWasPending ? null : (initialSession ?? null),
  );
  const [status, setStatus] = useState<AuthStatus>(() => {
    if (logoutWasPending) {
      return "logout_unconfirmed";
    }
    return initialSession === undefined
      ? "loading"
      : initialSession === null
        ? "anonymous"
        : "authenticated";
  });
  const statusRef = useRef(status);
  const authEpochRef = useRef(0);
  const logoutCsrfRef = useRef<string | undefined>(undefined);
  const logoutPromiseRef = useRef<Promise<boolean> | null>(null);
  statusRef.current = status;

  useEffect(() => {
    if (initialSession !== undefined || logoutWasPending) {
      if (logoutWasPending) {
        clearSensitiveCache();
      }
      return;
    }
    let active = true;
    const operationEpoch = authEpochRef.current;
    async function loadCurrentUser() {
      try {
        const currentSession = await authApi.getCurrentUser();
        if (active && authEpochRef.current === operationEpoch) {
          setSession(currentSession);
          setStatus("authenticated");
        }
      } catch (error) {
        if (active && authEpochRef.current === operationEpoch) {
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
  }, [authApi, clearSensitiveCache, initialSession, logoutWasPending]);

  useEffect(() => {
    function handleLogoutMarker(event: StorageEvent) {
      if (event.key !== LOGOUT_MARKER_KEY) {
        return;
      }
      authEpochRef.current += 1;
      setSession(null);
      clearSensitiveCache();
      const nextStatus =
        event.newValue === null
          ? "anonymous"
          : event.newValue.startsWith("pending")
            ? "logging_out"
            : "logout_unconfirmed";
      statusRef.current = nextStatus;
      setStatus(nextStatus);
    }
    window.addEventListener("storage", handleLogoutMarker);
    return () => window.removeEventListener("storage", handleLogoutMarker);
  }, [clearSensitiveCache]);

  const markLogoutUnconfirmed = useCallback(
    (csrfToken?: string) => {
      authEpochRef.current += 1;
      if (csrfToken !== undefined) {
        logoutCsrfRef.current = csrfToken;
      }
      writeLogoutMarker("unconfirmed");
      clearSensitiveCache();
      setSession(null);
      statusRef.current = "logout_unconfirmed";
      setStatus("logout_unconfirmed");
    },
    [clearSensitiveCache],
  );

  const quarantineStaleSession = useCallback(
    (staleSession: AuthSession) => markLogoutUnconfirmed(staleSession.csrfToken),
    [markLogoutUnconfirmed],
  );

  // Mirror the initial-load handling for calls made after login: a 401 from
  // any endpoint means the backend session is gone, and a password-change
  // demand locks the app to the change-password screen.
  useEffect(() => {
    setAuthEventHandlers({
      onUnauthorized: () => {
        if (statusRef.current !== "authenticated") {
          return;
        }
        authEpochRef.current += 1;
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
      if (
        statusRef.current === "logging_out" ||
        statusRef.current === "logout_unconfirmed" ||
        readLogoutMarker() !== null
      ) {
        throw logoutTransitionError();
      }
      const operationEpoch = ++authEpochRef.current;
      const nextSession = await authApi.login(request);
      if (authEpochRef.current !== operationEpoch) {
        quarantineStaleSession(nextSession);
        throw logoutTransitionError();
      }
      logoutCsrfRef.current = undefined;
      writeLogoutMarker(null);
      clearSensitiveCache();
      setSession(nextSession);
      statusRef.current = "authenticated";
      setStatus("authenticated");
      return nextSession;
    },
    [authApi, clearSensitiveCache, quarantineStaleSession],
  );

  const changePassword = useCallback(
    async (request: ChangePasswordRequest) => {
      if (
        statusRef.current !== "authenticated" ||
        session === null ||
        readLogoutMarker() !== null
      ) {
        throw logoutTransitionError();
      }
      const operationEpoch = ++authEpochRef.current;
      const nextSession = await authApi.changePassword(request, session.csrfToken);
      if (authEpochRef.current !== operationEpoch) {
        quarantineStaleSession(nextSession);
        throw logoutTransitionError();
      }
      logoutCsrfRef.current = undefined;
      writeLogoutMarker(null);
      clearSensitiveCache();
      setSession(nextSession);
      statusRef.current = "authenticated";
      setStatus("authenticated");
      return nextSession;
    },
    [authApi, clearSensitiveCache, quarantineStaleSession, session],
  );

  const logout = useCallback(() => {
    if (logoutPromiseRef.current !== null) {
      return logoutPromiseRef.current;
    }
    authEpochRef.current += 1;
    const operation = (async () => {
      let csrfToken = logoutCsrfRef.current ?? session?.csrfToken;
      writeLogoutMarker("pending");
      clearSensitiveCache();
      setSession(null);
      statusRef.current = "logging_out";
      setStatus("logging_out");
      if (csrfToken === undefined) {
        const verificationEpoch = authEpochRef.current;
        try {
          const currentSession = await authApi.getCurrentUser();
          if (authEpochRef.current !== verificationEpoch) {
            markLogoutUnconfirmed();
            return false;
          }
          csrfToken = currentSession.csrfToken;
        } catch (error) {
          if (error instanceof ApiError && error.status === 401) {
            if (authEpochRef.current !== verificationEpoch) {
              markLogoutUnconfirmed();
              return false;
            }
            logoutCsrfRef.current = undefined;
            writeLogoutMarker(null);
            statusRef.current = "expired";
            setStatus("expired");
            return false;
          }
          markLogoutUnconfirmed();
          return false;
        }
      }
      logoutCsrfRef.current = csrfToken;
      try {
        await authApi.logout(csrfToken);
        logoutCsrfRef.current = undefined;
        writeLogoutMarker(null);
        statusRef.current = "anonymous";
        setStatus("anonymous");
        return true;
      } catch {
        const verificationEpoch = authEpochRef.current;
        try {
          const currentSession = await authApi.getCurrentUser();
          if (authEpochRef.current !== verificationEpoch) {
            markLogoutUnconfirmed();
            return false;
          }
          logoutCsrfRef.current = currentSession.csrfToken;
        } catch (refreshError) {
          if (refreshError instanceof ApiError && refreshError.status === 401) {
            if (authEpochRef.current !== verificationEpoch) {
              markLogoutUnconfirmed();
              return false;
            }
            logoutCsrfRef.current = undefined;
            writeLogoutMarker(null);
            statusRef.current = "expired";
            setStatus("expired");
            return false;
          }
        }
        markLogoutUnconfirmed();
        return false;
      }
    })();
    logoutPromiseRef.current = operation;
    void operation.finally(() => {
      if (logoutPromiseRef.current === operation) {
        logoutPromiseRef.current = null;
      }
    });
    return operation;
  }, [authApi, clearSensitiveCache, markLogoutUnconfirmed, session?.csrfToken]);

  const refreshSession = useCallback(async () => {
    if (statusRef.current !== "authenticated" || readLogoutMarker() !== null) {
      throw logoutTransitionError();
    }
    const operationEpoch = ++authEpochRef.current;
    const currentSession = await authApi.getCurrentUser();
    if (authEpochRef.current !== operationEpoch) {
      quarantineStaleSession(currentSession);
      throw logoutTransitionError();
    }
    setSession(currentSession);
    setStatus("authenticated");
    return currentSession;
  }, [authApi, quarantineStaleSession]);

  const value = useMemo(
    () => ({
      status,
      session,
      login,
      changePassword,
      logout,
      refreshSession,
    }),
    [changePassword, login, logout, refreshSession, session, status],
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
