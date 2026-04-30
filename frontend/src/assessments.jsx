import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api.js";
import { AppShell } from "./AppShell.jsx";
import { useAuth } from "./auth.jsx";
import "./styles.css";

const emptyTenant = {
  displayName: "",
  tenantId: "",
  clientId: "",
  certificateThumbprint: ""
};
const guidPattern = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";

function App() {
  const { auth, logout, permissions } = useAuth();
  const [summary, setSummary] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [selectedTenantId, setSelectedTenantId] = useState(null);
  const [form, setForm] = useState(emptyTenant);
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [error, setError] = useState("");
  const [certificateBusy, setCertificateBusy] = useState("");
  const [cancelingRunId, setCancelingRunId] = useState("");

  const selectedTenant = useMemo(
    () => tenants.find((tenant) => tenant.id === selectedTenantId) || null,
    [tenants, selectedTenantId]
  );
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
    if (!auth.authenticated) return;

    refresh().catch((err) => setError(err.payload?.detail || err.message));
  }, [auth.authenticated]);

  async function logoutUser() {
    await logout();
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
        certificateThumbprint: tenant.certificateThumbprint || ""
      });
      api(`/runs/?tenantProfileId=${tenant.id}`)
        .then((data) => setRuns(data.runs))
        .catch((err) => setError(err.payload?.detail || err.message));
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

  async function cancelAssessment(run) {
    if (!canRunAssessments || !isRunCancellable(run) || cancelingRunId) return;
    setError("");
    setCancelingRunId(run.id);
    try {
      const data = await api(`/runs/${run.id}/cancel/`, { method: "POST", body: "{}" });
      setRuns((items) => items.map((item) => (item.id === data.run.id ? data.run : item)));
      setSelectedRun((current) => (current?.id === data.run.id ? { ...current, ...data.run } : current));
      await refresh();
    } catch (err) {
      setError(err.payload?.detail || err.message);
    } finally {
      setCancelingRunId("");
    }
  }

  async function createCertificate() {
    if (!selectedTenant || !canManageTenants || !canConfigureKeyVaultCertificates) return;
    setError("");
    setCertificateBusy("create");
    try {
      const data = await api(`/tenants/${selectedTenant.id}/certificate/`, { method: "POST", body: "{}" });
      setTenants((items) => items.map((item) => (item.id === data.tenant.id ? data.tenant : item)));
      setForm({
        displayName: data.tenant.displayName || "",
        tenantId: data.tenant.tenantId || "",
        clientId: data.tenant.clientId || "",
        certificateThumbprint: data.tenant.certificateThumbprint || ""
      });
      await refresh();
    } catch (err) {
      setError(err.payload?.detail || err.message);
    } finally {
      setCertificateBusy("");
    }
  }

  async function downloadCertificate() {
    if (!selectedTenant || !canManageTenants || !canConfigureKeyVaultCertificates) return;
    setError("");
    setCertificateBusy("download");
    try {
      const response = await fetch(`/api/tenants/${selectedTenant.id}/certificate/download/`, {
        credentials: "include"
      });
      if (!response.ok) {
        let payload = {};
        try {
          payload = await response.json();
        } catch {
          payload = {};
        }
        throw new Error(payload.detail || `Certificate download failed: ${response.status}`);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${selectedTenant.displayName || selectedTenant.tenantId}.cer`.replace(/[\\/]/g, "-");
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setCertificateBusy("");
    }
  }

  async function deleteTenant() {
    if (!selectedTenant || !canDeleteTenants) return;
    setError("");
    try {
      await api(`/tenants/${selectedTenant.id}/`, { method: "DELETE" });
      const remainingTenants = tenants.filter((tenant) => tenant.id !== selectedTenant.id);
      setTenants(remainingTenants);
      setSelectedTenantId(remainingTenants[0]?.id || null);
      setForm(emptyTenant);
      setRuns([]);
      setSelectedRun(null);
      await refresh();
    } catch (err) {
      setError(err.payload?.detail || err.message);
    }
  }

  async function loadRun(run) {
    if (!canViewResults) return;
    const data = await api(`/runs/${run.id}/`);
    setSelectedRun({ ...data.run, logs: data.logs, results: data.results });
  }

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  const heroAction = (
    <>
      {canManageTenants ? <button className="button" type="button" onClick={createNewTenant}>New Tenant Profile</button> : null}
      <p>{auth.user?.roles?.length ? auth.user.roles.join(", ") : "No application role assigned."}</p>
    </>
  );

  return (
    <AppShell
      activePage="assessments"
      auth={auth}
      onLogout={logoutUser}
      title="Zero Trust assessment workspace"
      eyebrow="Assessments"
      heroAction={heroAction}
    >
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
            <Field label="Tenant ID" value={form.tenantId} onChange={(value) => updateField("tenantId", value)} disabled={!canManageTenants} maxLength={36} pattern={guidPattern} />
            <Field label="Client ID" value={form.clientId} onChange={(value) => updateField("clientId", value)} disabled={!canManageTenants} maxLength={36} pattern={guidPattern} />
            <Field label="Certificate Thumbprint" value={form.certificateThumbprint} onChange={(value) => updateField("certificateThumbprint", value)} disabled={!canManageTenants} />
            <div className="actions form-actions">
              {canManageTenants ? <button className="button primary" type="submit">Save Settings</button> : null}
              {canManageTenants && canConfigureKeyVaultCertificates ? (
                <button className="button" type="button" onClick={createCertificate} disabled={!selectedTenant || Boolean(certificateBusy)}>
                  {certificateBusy === "create" ? "Creating..." : "Create Certificate"}
                </button>
              ) : null}
              {canManageTenants && canConfigureKeyVaultCertificates ? (
                <button className="button" type="button" onClick={downloadCertificate} disabled={!selectedTenant || !form.certificateThumbprint || Boolean(certificateBusy)}>
                  {certificateBusy === "download" ? "Downloading..." : "Download .cer"}
                </button>
              ) : null}
              {canRunAssessments ? <button className="button" type="button" onClick={runAssessment} disabled={!selectedTenant}>Run Assessment</button> : null}
              {canDeleteTenants ? <button className="button" type="button" onClick={deleteTenant} disabled={!selectedTenant}>Delete Tenant</button> : null}
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
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr key={run.id}>
                        <td><button className="link-button" type="button" onClick={() => loadRun(run)}>Open</button></td>
                        <td>{formatDate(run.startedAt)}</td>
                        <td>{formatDate(run.completedAt)}</td>
                        <td><span className={`status ${statusClass(run.status)}`}>{run.status}</span></td>
                        <td>
                          {run.hasReport ? (
                            <a className="link-button" href={`/api/runs/${run.id}/report/download/`}>Download</a>
                          ) : null}
                        </td>
                        <td>
                          {canRunAssessments && isRunCancellable(run) ? (
                            <button className="link-button danger-link" type="button" onClick={() => cancelAssessment(run)} disabled={Boolean(cancelingRunId)}>
                              {cancelingRunId === run.id ? "Cancelling..." : "Cancel"}
                            </button>
                          ) : null}
                        </td>
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
    </AppShell>
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

function Field({ label, value, onChange, disabled = false, maxLength, pattern }) {
  return (
    <label>
      <span>{label}</span>
      <input type="text" value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} maxLength={maxLength} pattern={pattern} />
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

function isRunCancellable(run) {
  return run?.status === "queued" || run?.status === "running";
}

createRoot(document.getElementById("root")).render(<App />);
