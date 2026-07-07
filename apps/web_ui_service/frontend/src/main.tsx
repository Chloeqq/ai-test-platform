import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import "./styles.css";

function resolveRouterBasename(): string | undefined {
  const configured = String(import.meta.env.VITE_ROUTER_BASENAME || "").trim();
  const fallback = import.meta.env.DEV ? "/" : "/react";
  const basename = configured || fallback;
  if (basename === "/") {
    return undefined;
  }
  return basename.endsWith("/") ? basename.slice(0, -1) : basename;
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter basename={resolveRouterBasename()}>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
