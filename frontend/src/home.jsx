import React from "react";
import { createRoot } from "react-dom/client";
import { AppShell } from "./AppShell.jsx";
import { useAuth } from "./auth.jsx";
import "./styles.css";

function HomeApp() {
  const { auth, logout } = useAuth();

  return (
    <AppShell
      activePage="home"
      auth={auth}
      onLogout={logout}
      title="Home"
      authTitle="Assessment Portal"
      contentClassName="blank-home"
    />
  );
}

createRoot(document.getElementById("root")).render(<HomeApp />);
