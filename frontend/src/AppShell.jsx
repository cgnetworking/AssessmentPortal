import React from "react";

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 11l9-8 9 8" />
      <path d="M5 10v10h14V10" />
    </svg>
  );
}

function AssessmentIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 11l2 2 4-5" />
      <path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9" />
      <path d="M16 4h4v4" />
    </svg>
  );
}

function AuditIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M8 13h8" />
      <path d="M8 17h6" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="7" />
      <path d="m16 16 4 4" />
    </svg>
  );
}

function NavItem({ activePage, href, id, icon, children }) {
  const active = activePage === id;
  return (
    <a className={`nav-item${active ? " active" : ""}`} href={href} aria-current={active ? "page" : undefined}>
      <span className="nav-icon" aria-hidden="true">
        {icon}
      </span>
      {children}
    </a>
  );
}

export function AppShell({
  activePage,
  auth,
  onLogout,
  title,
  eyebrow,
  authTitle,
  authEyebrow,
  heroAction,
  heroClassName = "",
  contentClassName = "",
  requireAuth = true,
  children
}) {
  const permissions = auth.user?.permissions || [];
  const canViewAuditLog = permissions.includes("viewAuditLog");
  const mainClassName = ["content", contentClassName].filter(Boolean).join(" ");

  if (requireAuth && (auth.loading || !auth.authenticated)) {
    return (
      <AuthScreen
        title={authTitle || title}
        eyebrow={authEyebrow || eyebrow}
        error={auth.error}
        loginUrl={auth.loginUrl}
        loading={auth.loading}
      />
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">ComplianceApp</div>
        {auth.authenticated ? (
          <button className="profile-button" aria-label="Sign out" onClick={onLogout}>
            {auth.user?.name?.[0] || "A"}
          </button>
        ) : null}
      </header>

      <div className="workspace">
        <aside className="sidebar" aria-label="Primary navigation">
          <div className="search" aria-label="Find">
            <SearchIcon />
            <span>Find...</span>
          </div>
          <nav className="nav">
            <NavItem activePage={activePage} href="/" id="home" icon={<HomeIcon />}>
              Home
            </NavItem>
            <NavItem activePage={activePage} href="/assessments.html" id="assessments" icon={<AssessmentIcon />}>
              Assessments
            </NavItem>
            {canViewAuditLog || activePage === "auditLog" ? (
              <NavItem activePage={activePage} href="/audit-log.html" id="auditLog" icon={<AuditIcon />}>
                Audit Log
              </NavItem>
            ) : null}
          </nav>
        </aside>

        <main className={mainClassName} aria-label={title}>
          {auth.error ? <div className="error-banner">{auth.error}</div> : null}
          {title && requireAuth ? (
            <section className={["hero", heroClassName].filter(Boolean).join(" ")}>
              <div>
                {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
                <h1>{title}</h1>
              </div>
              {heroAction ? <div className="hero-action">{heroAction}</div> : null}
            </section>
          ) : null}
          {children}
        </main>
      </div>
    </div>
  );
}

function AuthScreen({ title, eyebrow, error, loginUrl, loading }) {
  return (
    <main className="auth-screen" aria-label={title}>
      <section className="login-panel">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {error ? <div className="error-banner">{error}</div> : null}
        {!loading ? (
          <div className="auth-actions">
            <button className="button primary" type="button" onClick={() => { window.location.href = loginUrl; }}>
              Sign in with Microsoft Entra ID
            </button>
            <a className="button" href="/admin/login/?next=/admin/">
              Admin sign in
            </a>
          </div>
        ) : null}
      </section>
    </main>
  );
}
