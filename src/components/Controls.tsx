import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useApp } from "../store";

export default function Controls() {
  const boot = useApp((s) => s.boot);
  const running = useApp((s) => s.running);
  const startRun = useApp((s) => s.startRun);
  const stopRun = useApp((s) => s.stopRun);
  const openAccounts = useApp((s) => s.openAccounts);
  const pushLog = useApp((s) => s.pushLog);

  const [target, setTarget] = useState("");
  const [platform, setPlatform] = useState("Instagram");
  const [reason, setReason] = useState("Spam");
  const [workers, setWorkers] = useState(2);

  useEffect(() => {
    if (!boot) return;
    const c = boot.config;
    setTarget(c.target);
    setPlatform(
      boot.platforms.find(([, k]) => k === c.platform)?.[0] ?? "Instagram",
    );
    setReason(
      boot.reasons.find(([, k]) => k === c.reason)?.[0] ?? "Spam",
    );
    setWorkers(c.workers);
  }, [boot]);

  if (!boot) return null;
  const b = boot;

  function platformKey(): string {
    return b.platforms.find(([n]) => n === platform)?.[1] ?? "instagram";
  }

  function reasonKey(): string {
    return b.reasons.find(([n]) => n === reason)?.[1] ?? "spam";
  }

  function handleRun() {
    const t = target.trim().replace(/^@/, "");
    if (!t) {
      pushLog("No target set — enter a username", "warn");
      return;
    }
    void startRun(t, platformKey(), reasonKey(), workers);
  }

  return (
    <motion.div
      className="controls"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3, delay: 0.05 }}
    >
      <div className="ctrl-group">
        <span className="ctrl-label">Target:</span>
        <input
          className="field"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleRun()}
          placeholder="username"
          spellCheck={false}
        />
      </div>

      <div className="ctrl-group">
        <span className="ctrl-label">Platform:</span>
        <select
          className="field"
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
        >
          {boot.platforms.map(([name]) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </div>

      <div className="ctrl-group">
        <span className="ctrl-label">Reason:</span>
        <select
          className="field"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        >
          {boot.reasons.map(([name]) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </div>

      <div className="ctrl-group">
        <span className="ctrl-label">Workers:</span>
        <input
          className="field narrow"
          type="number"
          min={1}
          max={16}
          value={workers}
          onChange={(e) => setWorkers(Math.max(1, Math.min(16, Number(e.target.value) || 1)))}
        />
      </div>

      <div className="actions-right">
        {running ? (
          <button className="btn btn-danger" onClick={() => void stopRun()}>
            ⏹ STOP
          </button>
        ) : (
          <button className="btn btn-primary" onClick={handleRun}>
            ▶ Run
          </button>
        )}
        <button className="btn btn-ghost" onClick={openAccounts}>
          Accounts
        </button>
      </div>
    </motion.div>
  );
}
