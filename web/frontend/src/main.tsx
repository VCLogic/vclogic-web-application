import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/barlow-condensed/500.css";
import "@fontsource/barlow-condensed/600.css";
import "@fontsource-variable/inter";
import "@fontsource-variable/source-serif-4";
import { App } from "./app/App";
import "./styles/global.css";

createRoot(document.getElementById("root")!).render(<StrictMode><App/></StrictMode>);
