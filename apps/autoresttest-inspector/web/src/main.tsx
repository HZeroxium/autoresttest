import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";

import { router } from "@/app/router";
import { AppProviders } from "@/app/providers";
import "@/styles/globals.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element #root was not found.");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  </React.StrictMode>,
);
