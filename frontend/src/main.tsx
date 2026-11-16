import "@astryxdesign/core/reset.css";
import "@astryxdesign/core/astryx.css";
import "./app.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { DesignSystemProvider } from "./ui/DesignSystemProvider";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <DesignSystemProvider>
        <App />
      </DesignSystemProvider>
    </BrowserRouter>
  </StrictMode>,
);
