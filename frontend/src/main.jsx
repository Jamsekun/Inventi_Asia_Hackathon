import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css"; // optional, create as empty or for custom styles

// Import chatscope styles
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);