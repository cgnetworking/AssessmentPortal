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

function AuditLogApp() {
  const [auth, setAuth] = useState({ loading: true, authenticated: false, loginUrl: "/auth/login/azuread-tenant-oauth2/" });
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");

  const permissions = auth.user?.permissions || [];
  const canViewAuditLog = permissions.includes("viewAuditLog");

  useEffect(() => {
    api("/auth/session/")
      .then((data) => {
        setAuth({ loading: false, authenticated: true, user: data.user, loginUrl: "/auth/login/azuread-tenant-oauth2/" });
        return api("/audit-log/");
      })
      .then((data) => setEvents(data.events || []))
      .catch((err) => {
        if (err.status === 401) {
          setAuth({ loading: false, authenticated: false, loginUrl: err.payload?.loginUrl || "/auth/login/azuread-tenant-oauth2/" });
          return;
        }
        setAuth((current) => ({ ...current, loading: false }));
        setError(err.payload?.detail || err.message);
      });
  }, []);

  async function logoutUser() {
    await api("/auth/logout/", { method: "POST", body: "{}" });
    setAuth({ loading: false, authenticated: false, loginUrl: "/auth/login/azuread-tenant-oauth2/" });
    setEvents([]);
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
            <a className="nav-item" href="/">
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
            <a className="nav-item active" href="/audit-log.html" aria-current="page">
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
          </nav>
        </aside>

        <main className="content">
          {auth.loading ? (
            <section className="login-panel">
              <h1>Audit Log</h1>
            </section>
          ) : null}

          {!auth.loading && !auth.authenticated ? (
            <section className="login-panel">
              <p className="eyebrow">Audit Log</p>
              <h1>Audit Log</h1>
              <button className="button primary" type="button" onClick={() => { window.location.href = auth.loginUrl; }}>
                Sign in with Microsoft Entra ID
              </button>
            </section>
          ) : null}

          {auth.authenticated ? (
            <>
              <section className="hero audit-hero">
                <div>
                  <p className="eyebrow">Audit Log</p>
                  <h1>Audit Log</h1>
                </div>
                <div className="hero-action">
                  <p>{auth.user?.roles?.length ? auth.user.roles.join(", ") : "No application role assigned."}</p>
                </div>
              </section>

              {error ? <div className="error-banner">{error}</div> : null}

              {canViewAuditLog ? (
                <section className="panel audit-panel">
                  <div className="audit-summary">
                    <p className="eyebrow">Events</p>
                    <strong>{events.length}</strong>
                  </div>
                  <div className="table-wrap audit-table-wrap">
                    <table className="audit-table">
                      <thead>
                        <tr>
                          <th>Event ID</th>
                          <th>Time</th>
                          <th>Actor</th>
                          <th>Action</th>
                          <th>Target</th>
                          <th>Linked Records</th>
                          <th>Source IP</th>
                          <th>User Agent</th>
                          <th>Metadata</th>
                        </tr>
                      </thead>
                      <tbody>
                        {events.map((event) => (
                          <tr key={event.id}>
                            <td className="audit-id">{event.id}</td>
                            <td>{formatDate(event.createdAt)}</td>
                            <td>
                              <div className="audit-cell-main">{event.actor.username || "System"}</div>
                              <div className="audit-cell-muted">{event.actor.email || ""}</div>
                            </td>
                            <td>{event.actionLabel || event.action}</td>
                            <td>
                              <div className="audit-cell-main">{event.targetLabel || event.targetType || ""}</div>
                              <div className="audit-cell-muted">{event.targetId || ""}</div>
                            </td>
                            <td>
                              <div className="audit-cell-muted">Tenant: {event.tenantProfileId || ""}</div>
                              <div className="audit-cell-muted">Run: {event.assessmentRunId || ""}</div>
                            </td>
                            <td>{event.sourceIp || ""}</td>
                            <td className="audit-user-agent">{event.userAgent || ""}</td>
                            <td>
                              <pre className="metadata-block">{JSON.stringify(event.metadata || {}, null, 2)}</pre>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ) : error ? null : (
                <div className="error-banner">You do not have permission to view the audit log.</div>
              )}
            </>
          ) : null}
        </main>
      </div>
    </div>
  );
}

function formatDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

createRoot(document.getElementById("root")).render(<AuditLogApp />);
