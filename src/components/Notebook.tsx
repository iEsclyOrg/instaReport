import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useApp, type ModuleDef } from "../store";
import ModuleCard from "./ModuleCard";

const gridVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.02 } },
};

const MODULE_TABS = new Set([
  "Auto-Ban Engine",
  "Unban Tools",
  "Lookups",
  "Advanced",
]);

const TAB_ICONS: Record<string, string> = {
  "Auto-Ban Engine": "⚡",
  "Unban Tools": "🔓",
  Lookups: "🔍",
  Advanced: "🧠",
  Plugins: "🧩",
  "Run History": "🕘",
  "⭐ Favorites": "⭐",
};

function ModulesPanel({ modules, favorite = false }: { modules: ModuleDef[]; favorite?: boolean }) {
  return (
    <motion.div
      className="card-grid"
      variants={gridVariants}
      initial="hidden"
      animate="visible"
    >
      {modules.map((def, i) => (
        <ModuleCard key={def[4]} def={def} index={i} favorite={favorite} />
      ))}
    </motion.div>
  );
}

function PluginsPanel() {
  const plugins = useApp((s) => s.plugins);
  const toggle = useApp((s) => s.togglePlugin);
  const enableAll = useApp((s) => s.enableAllPlugins);
  const disableAll = useApp((s) => s.disableAllPlugins);
  const refresh = useApp((s) => s.refreshPlugins);
  return (
    <div>
      <div className="toolbar">
        <span className="panel-title" style={{ marginBottom: 0, marginRight: "auto" }}>
          Plugin Manager
        </span>
        <button className="btn btn-ghost" onClick={() => void refresh()}>
          Refresh
        </button>
        <button className="btn btn-ghost" onClick={() => void enableAll()}>
          Enable All
        </button>
        <button className="btn btn-ghost" onClick={() => void disableAll()}>
          Disable All
        </button>
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Name</th>
              <th>Key</th>
              <th>Status</th>
              <th>Version</th>
              <th>Description</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {plugins.map((p) => (
              <tr key={p.key}>
                <td>{p.name}</td>
                <td>{p.key}</td>
                <td>{p.enabled ? "● ON" : "○ OFF"}</td>
                <td>{p.version}</td>
                <td>{p.description}</td>
                <td className="row-actions">
                  <input
                    type="checkbox"
                    className="switch"
                    checked={p.enabled}
                    title={p.enabled ? "Disable plugin" : "Enable plugin"}
                    onChange={(e) => void toggle(p.key, e.target.checked)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function HistoryPanel() {
  const history = useApp((s) => s.history);
  const historyTotal = useApp((s) => s.historyTotal);
  const historyPage = useApp((s) => s.historyPage);
  const historyPageSize = useApp((s) => s.historyPageSize);
  const pageDelta = useApp((s) => s.historyPageDelta);
  const refreshHistory = useApp((s) => s.refreshHistory);
  const clearHistory = useApp((s) => s.clearHistory);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  const maxPage = Math.max(0, Math.ceil(historyTotal / historyPageSize) - 1);

  return (
    <div>
      <div className="panel-title">Run History</div>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Time</th>
              <th>Target</th>
              <th>Platform</th>
              <th>Reason</th>
              <th>Succeeded</th>
              <th>Attempted</th>
              <th>Elapsed</th>
            </tr>
          </thead>
          <tbody>
            {history.map((r, i) => {
              const ts = r.timestamp.length > 19 ? r.timestamp.slice(11, 19) : r.timestamp.slice(-8);
              return (
                <tr key={`${r.timestamp}-${i}`}>
                  <td>{ts}</td>
                  <td>{r.target}</td>
                  <td>{r.platform}</td>
                  <td>{r.reason}</td>
                  <td>{r.successes}</td>
                  <td>{r.total}</td>
                  <td>{r.elapsed_s}s</td>
                </tr>
              );
            })}
            {history.length === 0 && (
              <tr>
                <td colSpan={7} style={{ color: "var(--fg-dim)" }}>
                  No runs yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <button className="btn btn-ghost" onClick={() => void pageDelta(-1)} disabled={historyPage <= 0}>
          &lt; Prev
        </button>
        <span>
          Page {historyPage + 1}/{maxPage + 1} ({historyTotal} total)
        </span>
        <button
          className="btn btn-ghost"
          onClick={() => void pageDelta(1)}
          disabled={historyPage >= maxPage}
        >
          Next &gt;
        </button>
        <div className="spacer" style={{ flex: 1 }} />
        <button
          className="btn btn-ghost"
          style={{ color: "var(--danger)" }}
          onClick={() => void clearHistory()}
          disabled={historyTotal === 0}
        >
          Clear History
        </button>
      </div>
    </div>
  );
}

export default function Notebook() {
  const boot = useApp((s) => s.boot);
  const activeTab = useApp((s) => s.activeTab);
  const selectTab = useApp((s) => s.selectTab);

  if (!boot) return null;

  const modules = boot.modules;
  const favorites = boot.config.favorites;

  function renderPanel(name: string) {
    if (name === "Plugins") return <PluginsPanel />;
    if (name === "Run History") return <HistoryPanel />;
    if (name === "⭐ Favorites") {
      const favs: ModuleDef[] = [];
      for (const list of Object.values(modules)) {
        for (const def of list) {
          if (favorites.includes(def[4])) favs.push(def);
        }
      }
      return favs.length ? (
        <ModulesPanel modules={favs} favorite />
      ) : (
        <div style={{ color: "var(--fg-dim)", padding: 24 }}>
          No favorites yet — click ☆ on any module to add it here.
        </div>
      );
    }
    return <ModulesPanel modules={modules[name] ?? []} />;
  }

  return (
    <div className="notebook">
      <nav className="nav-rail">
        {boot.tabs.map(([name, count]) => (
          <button
            key={name}
            className={`nav-item ${activeTab === name ? "active" : ""}`}
            onClick={() => selectTab(name)}
          >
            <span className="nav-icon">{TAB_ICONS[name] ?? "▪"}</span>
            <span className="nav-label">{name}</span>
            {MODULE_TABS.has(name) && count > 0 && (
              <span className="count">{count}</span>
            )}
          </button>
        ))}
      </nav>
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          className="tab-panel"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
        >
          {renderPanel(activeTab)}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
