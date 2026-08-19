import { FluentProvider } from "@fluentui/react-components";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./index.css";
import { monitouTheme } from "./theme";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <FluentProvider theme={monitouTheme} style={{ height: "100vh" }}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </FluentProvider>
  </React.StrictMode>,
);
