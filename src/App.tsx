import { useEffect } from "react";
import { useApp } from "./store";
import Header from "./components/Header";
import Controls from "./components/Controls";
import Notebook from "./components/Notebook";
import Console from "./components/Console";
import { Modals } from "./components/Modals";

let didInit = false;

export default function App() {
  const loading = useApp((s) => s.loading);
  const error = useApp((s) => s.error);
  const init = useApp((s) => s.init);

  useEffect(() => {
    if (!didInit) {
      didInit = true;
      void init();
    }
  }, [init]);

  if (loading) {
    return (
      <div className="boot-screen">
        <div className="spinner" />
        <div style={{ color: "var(--fg-secondary)" }}>Starting InstaReport backend…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="boot-screen">
        <div style={{ color: "var(--danger)", fontWeight: 600 }}>Backend failed to start</div>
        <div style={{ color: "var(--fg-dim)", maxWidth: 520, textAlign: "center", fontSize: 12 }}>
          {error}
          <br />
          <br />
          Run <code>python sidecar\sidecar_bridge.py</code> from the project folder to see the
          error, or make sure the InstaReport Python repo is available.
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <Header />
      <Controls />
      <Notebook />
      <Console />
      <Modals />
    </div>
  );
}
