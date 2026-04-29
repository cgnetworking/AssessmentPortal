import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const emptyTenant = {
  displayName: "",
  tenantId: "",
  clientId: "",
  certificateThumbprint: "",
  keyVaultCertificateUri: "",
  exchangeOrganization: "",
  sharePointAdminUrl: ""
};

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
  if (response.status === 204) {
    return {};
  }
  return response.json();
}

function App() {
  const [auth, setAuth] = useState({ loading: true, authenticated: false, loginUrl: "/auth/login/azuread-tenant-oauth2/" });
  const [summary, setSummary] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [selectedTenantId, setSelectedTenantId] = useState(null);
  const [form, setForm] = useState(emptyTenant);
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [error, setError] = useState("");

  const selectedTenant = useMemo(
    () => tenants.find((tenant) => tenant.id === selectedTenantId) || null,
    [tenants, selectedTenantId]
  );
  const permissions = auth.user?.permissions || [];
  const canManageTenants = permissions.includes("manageTenantProfiles");
  const canConfigureKeyVaultCertificates = permissions.includes("configureKeyVaultCertificates");
  const canDeleteTenants = permissions.includes("deleteTenants");
  const canRunAssessments = permissions.includes("runAssessments");
  const canViewTenants = permissions.includes("viewTenantProfiles") || canManageTenants;
  const canViewResults = permissions.includes("viewResults");

  async function refresh() {
    const [summaryData, tenantData] = await Promise.all([api("/summary/"), api("/tenants/")]);
    setSummary(summaryData);
    setTenants(tenantData.tenants);
    if (!selectedTenantId && tenantData.tenants.length > 0) {
      setSelectedTenantId(tenantData.tenants[0].id);
    }
  }

  useEffect(() => {
    api("/auth/session/")
      .then((data) => {
        setAuth({ loading: false, authenticated: true, user: data.user, loginUrl: "/auth/login/azuread-tenant-oauth2/" });
        return refresh();
      })
      .catch((err) => {
        if (err.status === 401) {
          setAuth({ loading: false, authenticated: false, loginUrl: err.payload?.loginUrl || "/auth/login/azuread-tenant-oauth2/" });
          return;
        }
        setAuth((current) => ({ ...current, loading: false }));
        setError(err.message);
      });
  }, []);

  async function logoutUser() {
    await api("/auth/logout/", { method: "POST", body: "{}" });
    setAuth({ loading: false, authenticated: false, loginUrl: "/auth/login/azuread-tenant-oauth2/" });
    setSummary(null);
    setTenants([]);
    setRuns([]);
    setSelectedTenantId(null);
    setSelectedRun(null);
  }

  useEffect(() => {
    if (!selectedTenantId) {
      setForm(emptyTenant);
      setRuns([]);
      setSelectedRun(null);
      return;
    }

    const tenant = tenants.find((item) => item.id === selectedTenantId);
    if (tenant) {
      setForm({
        displayName: tenant.displayName || "",
        tenantId: tenant.tenantId || "",
        clientId: tenant.clientId || "",
        certificateThumbprint: tenant.certificateThumbprint || "",
        keyVaultCertificateUri: tenant.keyVaultCertificateUri || "",
        exchangeOrganization: tenant.exchangeOrganization || "",
        sharePointAdminUrl: tenant.sharePointAdminUrl || ""
      });
      api(`/runs/?tenantProfileId=${tenant.id}`)
        .then((data) => setRuns(data.runs))
        .catch((err) => setError(err.message));
    }
  }, [selectedTenantId, tenants]);

  async function saveTenant(event) {
    event.preventDefault();
    if (!canManageTenants) return;
    setError("");
    const payload = JSON.stringify(form);
    if (selectedTenant) {
      const data = await api(`/tenants/${selectedTenant.id}/`, { method: "PATCH", body: payload });
      setTenants((items) => items.map((item) => (item.id === data.tenant.id ? data.tenant : item)));
    } else {
      const data = await api("/tenants/", { method: "POST", body: payload });
      setTenants((items) => [...items, data.tenant]);
      setSelectedTenantId(data.tenant.id);
    }
    await refresh();
  }

  async function createNewTenant() {
    if (!canManageTenants) return;
    setSelectedTenantId(null);
    setForm(emptyTenant);
    setRuns([]);
    setSelectedRun(null);
  }

  async function runAssessment() {
    if (!selectedTenant || !canRunAssessments) return;
    const data = await api("/runs/", {
      method: "POST",
      body: JSON.stringify({ tenantProfileId: selectedTenant.id, pillar: "All" })
    });
    setRuns((items) => [data.run, ...items]);
    setSelectedRun(data.run);
    await refresh();
  }

  async function loadRun(run) {
    if (!canViewResults) return;
    const data = await api(`/runs/${run.id}/`);
    setSelectedRun({ ...data.run, logs: data.logs, results: data.results });
  }

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
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
            <a className="nav-item active" href="/assessments.html" aria-current="page">
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

        <main className="content">
          {auth.loading ? (
            <section className="login-panel">
              <h1>Zero Trust assessment workspace</h1>
            </section>
          ) : null}

          {!auth.loading && !auth.authenticated ? (
            <section className="login-panel">
              <p className="eyebrow">Assessments</p>
              <h1>Zero Trust assessment workspace</h1>
              <button className="button primary" type="button" onClick={() => { window.location.href = auth.loginUrl; }}>
                Sign in with Microsoft Entra ID
              </button>
            </section>
          ) : null}

          {auth.authenticated ? (
          <>
          <section className="hero">
            <div>
              <p className="eyebrow">Assessments</p>
              <h1>Zero Trust assessment workspace</h1>
            </div>
            <div className="hero-action">
              {canManageTenants ? <button className="button" type="button" onClick={createNewTenant}>New Tenant Profile</button> : null}
              <p>{auth.user?.roles?.length ? auth.user.roles.join(", ") : "No application role assigned."}</p>
            </div>
          </section>

          {error ? <div className="error-banner">{error}</div> : null}

          <section className="stats-grid" aria-label="Assessment summary">
            <SummaryCard label="Saved Tenants" value={summary?.savedTenants} />
            <SummaryCard label="Active Runs" value={summary?.activeRuns} />
            <SummaryCard label="Reports Stored" value={summary?.reportsStored} />
            <SummaryCard label="Most Recent Run" value={summary?.mostRecentRun?.status} />
          </section>

          <section className="workspace-grid">
            <article className="panel tenant-panel">
              <p className="eyebrow">Tenant Profiles</p>
              <h2>Saved assessment targets</h2>
              <div className="tenant-list">
                {canViewTenants ? tenants.map((tenant) => (
                  <button
                    key={tenant.id}
                    className={`tenant-card ${tenant.id === selectedTenantId ? "selected" : ""}`}
                    type="button"
                    onClick={() => setSelectedTenantId(tenant.id)}
                  >
                    <div>
                      <h3>{tenant.displayName}</h3>
                      <p>{tenant.tenantId}</p>
                    </div>
                    {tenant.certificateThumbprint ? <span className="tag right">{tenant.certificateThumbprint}</span> : null}
                  </button>
                )) : null}
              </div>
            </article>

            <article className="panel config-panel">
              <p className="eyebrow">Tenant Configuration</p>
              <form className="settings-form" onSubmit={saveTenant}>
                <Field label="Display Name" value={form.displayName} onChange={(value) => updateField("displayName", value)} disabled={!canManageTenants} />
                <Field label="Tenant ID" value={form.tenantId} onChange={(value) => updateField("tenantId", value)} disabled={!canManageTenants} />
                <Field label="Client ID" value={form.clientId} onChange={(value) => updateField("clientId", value)} disabled={!canManageTenants} />
                <Field label="Certificate Thumbprint" value={form.certificateThumbprint} onChange={(value) => updateField("certificateThumbprint", value)} disabled={!canManageTenants} />
                {canConfigureKeyVaultCertificates ? (
                  <Field label="Key Vault Certificate URI" value={form.keyVaultCertificateUri} onChange={(value) => updateField("keyVaultCertificateUri", value)} wide />
                ) : null}
                <Field label="Exchange Organization" value={form.exchangeOrganization} onChange={(value) => updateField("exchangeOrganization", value)} disabled={!canManageTenants} />
                <Field label="SharePoint Admin URL" value={form.sharePointAdminUrl} onChange={(value) => updateField("sharePointAdminUrl", value)} disabled={!canManageTenants} />
                <div className="actions form-actions">
                  {canManageTenants ? <button className="button primary" type="submit">Save Settings</button> : null}
                  {canManageTenants ? <button className="button" type="button">Create Certificate</button> : null}
                  {canManageTenants ? <button className="button" type="button">Download .cer</button> : null}
                  {canRunAssessments ? <button className="button" type="button" onClick={runAssessment} disabled={!selectedTenant}>Run Assessment</button> : null}
                  {canDeleteTenants ? <button className="button" type="button">Delete Tenant</button> : null}
                </div>
              </form>

              {canViewResults ? (
                <>
                  <h3 className="subheading">Run history</h3>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Open</th>
                          <th>Started</th>
                          <th>Completed</th>
                          <th>Status</th>
                          <th>Report</th>
                        </tr>
                      </thead>
                      <tbody>
                        {runs.map((run) => (
                          <tr key={run.id}>
                            <td><button className="link-button" type="button" onClick={() => loadRun(run)}>Open</button></td>
                            <td>{formatDate(run.startedAt)}</td>
                            <td>{formatDate(run.completedAt)}</td>
                            <td><span className={`status ${statusClass(run.status)}`}>{run.status}</span></td>
                            <td>{run.outputPath ? "Stored" : ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <h3 className="subheading">Selected run logs</h3>
                  <pre className="logs">{selectedRun?.logs?.map((log) => log.message).join("\n") || ""}</pre>
                </>
              ) : null}
            </article>
          </section>
          </>
          ) : null}
        </main>
      </div>
    </div>
  );
}

function SummaryCard({ label, value }) {
  return (
    <article className="stat-card">
      <p className="eyebrow">{label}</p>
      {value !== undefined && value !== null ? <strong>{value}</strong> : null}
    </article>
  );
}

function Field({ label, value, onChange, wide = false, disabled = false }) {
  return (
    <label className={wide ? "wide-field" : ""}>
      <span>{label}</span>
      <input type="text" value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} />
    </label>
  );
}

function formatDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function statusClass(status) {
  if (status === "completed") return "success";
  if (status === "running" || status === "queued") return "active";
  if (status === "failed") return "danger";
  return "neutral";
}

createRoot(document.getElementById("root")).render(<App />);
