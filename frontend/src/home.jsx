import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

function getCookie(name) {
  return document.cookie
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(`${name}=`))
    ?.slice(name.length + 1) || "";
}

async function api(path, options = {}) {
  const { headers: optionHeaders, ...fetchOptions } = options;
  const method = (options.method || "GET").toUpperCase();
  const headers = {
    "Content-Type": "application/json",
    ...(optionHeaders || {})
  };

  if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
    headers["X-CSRFToken"] = decodeURIComponent(getCookie("csrftoken"));
  }

  const response = await fetch(`/api${path}`, {
    credentials: "include",
    headers,
    ...fetchOptions
  });
  if (!response.ok) {
    const error = new Error(`API request failed: ${response.status}`);
    error.status = response.status;
    try {
      error.payload = await response.json();
    } catch {
      error.payload = {};
    }
    throw error;
  }
  return response.status === 204 ? {} : response.json();
}

function HomeApp() {
  const [auth, setAuth] = useState({ loading: true, authenticated: false, loginUrl: "/auth/login/azuread-tenant-oauth2/" });
  const permissions = auth.user?.permissions || [];

  useEffect(() => {
    api("/auth/session/")
      .then((data) => setAuth({ loading: false, authenticated: true, user: data.user, loginUrl: "/auth/login/azuread-tenant-oauth2/" }))
      .catch((err) => {
        if (err.status === 401) {
          setAuth({ loading: false, authenticated: false, loginUrl: err.payload?.loginUrl || "/auth/login/azuread-tenant-oauth2/" });
          return;
        }
        setAuth((current) => ({ ...current, loading: false }));
      });
  }, []);

  async function logoutUser() {
    await api("/auth/logout/", { method: "POST", body: "{}" });
    setAuth({ loading: false, authenticated: false, loginUrl: "/auth/login/azuread-tenant-oauth2/" });
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">ComplianceApp</div>
        {auth.authenticated ? (
          <button className="profile-button" aria-label="Sign out" onClick={logoutUser}>
            {auth.user?.name?.[0] || "A"}
          </button>
        ) : null}
      </header>

      <div className="workspace">
        <aside className="sidebar" aria-label="Primary navigation">
          <div className="search" aria-label="Find">
            <svg aria-hidden="true" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="7" />
              <path d="m16 16 4 4" />
            </svg>
            <span>Find...</span>
          </div>
          <nav className="nav">
            <a className="nav-item active" href="/" aria-current="page">
              <span className="nav-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 11l9-8 9 8" />
                  <path d="M5 10v10h14V10" />
                </svg>
              </span>
              Home
            </a>
            <a className="nav-item" href="/assessments.html">
              <span className="nav-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 11l2 2 4-5" />
                  <path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9" />
                  <path d="M16 4h4v4" />
                </svg>
              </span>
              Assessments
            </a>
            {permissions.includes("viewAuditLog") ? (
              <a className="nav-item" href="/audit-log.html">
                <span className="nav-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6" />
                    <path d="M8 13h8" />
                    <path d="M8 17h6" />
                  </svg>
                </span>
                Audit Log
              </a>
            ) : null}
          </nav>
        </aside>
        <main className="content blank-home" aria-label="Home" />
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<HomeApp />);
