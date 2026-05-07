import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import "./styles/globals.css";
import { AppContextProvider } from "./context/AppContext.jsx";
import { RepoContextProvider } from "./context/RepoContext.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppContextProvider>
        <RepoContextProvider>
          <App />
        </RepoContextProvider>
      </AppContextProvider>
    </BrowserRouter>
  </React.StrictMode>
);
