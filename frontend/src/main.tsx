import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AgentApp } from "./app/AgentApp";
import "./styles.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Root element #root was not found.");
}

createRoot(root).render(
  <StrictMode>
    <AgentApp />
  </StrictMode>,
);
