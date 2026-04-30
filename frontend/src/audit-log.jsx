import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api.js";
import { AppShell } from "./AppShell.jsx";
import { useAuth } from "./auth.jsx";
import "./styles.css";

function AuditLogApp() {
  const { auth, logout, permissions } = useAuth();
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");

  const canViewAuditLog = permissions.includes("viewAuditLog");

  useEffect(() => {
    if (!auth.authenticated) return;

    api("/audit-log/")
      .then((data) => setEvents(data.events || []))
      .catch((err) => setError(err.payload?.detail || err.message));
  }, [auth.authenticated]);

  async function logoutUser() {
    await logout();
    setEvents([]);
  }

  const heroAction = (
    <p>{auth.user?.roles?.length ? auth.user.roles.join(", ") : "No application role assigned."}</p>
  );

  return (
    <AppShell
      activePage="auditLog"
      auth={auth}
      onLogout={logoutUser}
      title="Audit Log"
      eyebrow="Audit Log"
      heroAction={heroAction}
      heroClassName="audit-hero"
    >
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
    </AppShell>
  );
}

function formatDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

createRoot(document.getElementById("root")).render(<AuditLogApp />);
