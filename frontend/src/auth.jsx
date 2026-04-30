import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

export const DEFAULT_LOGIN_URL = "/auth/login/azuread-tenant-oauth2/";

function signedOutAuth(loginUrl = DEFAULT_LOGIN_URL) {
  return { loading: false, authenticated: false, loginUrl };
}

function authErrorMessage(err, fallback) {
  return err?.payload?.detail || err?.message || fallback;
}

export function useAuth() {
  const [auth, setAuth] = useState({ loading: true, authenticated: false, loginUrl: DEFAULT_LOGIN_URL });

  useEffect(() => {
    let active = true;

    api("/auth/session/")
      .then((data) => {
        if (!active) return;
        setAuth({ loading: false, authenticated: true, user: data.user, loginUrl: DEFAULT_LOGIN_URL });
      })
      .catch((err) => {
        if (!active) return;
        if (err.status === 401) {
          setAuth(signedOutAuth(err.payload?.loginUrl || DEFAULT_LOGIN_URL));
          return;
        }
        setAuth((current) => ({ ...current, loading: false, error: err.payload?.detail || err.message }));
      });

    return () => {
      active = false;
    };
  }, []);

  const logout = useCallback(async () => {
    try {
      await api("/auth/logout/", { method: "POST", body: "{}" });
      setAuth(signedOutAuth());
      return { ok: true };
    } catch (err) {
      const error = authErrorMessage(err, "Unable to sign out. Please try again.");
      setAuth((current) => ({ ...current, loading: false, error }));
      return { ok: false, error };
    }
  }, []);

  const permissions = useMemo(() => auth.user?.permissions || [], [auth.user]);

  return { auth, logout, permissions };
}
