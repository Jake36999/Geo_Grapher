import React from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/jetbrains-mono/400.css";
import App from "./App";
import Workspace from "./Workspace";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {document.querySelector('meta[name="geographer-workspace"]') ? (
      <Workspace />
    ) : (
      <App />
    )}
  </React.StrictMode>,
);
