import { motion } from "framer-motion";
import { useApp } from "../store";

function formatCount(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

export default function Header() {
  const boot = useApp((s) => s.boot);
  const license = useApp((s) => s.license);
  const stats = useApp((s) => s.stats);
  const accountsCount = useApp((s) => s.accountsCount);
  const proxiesCount = useApp((s) => s.proxiesCount);
  const openLicense = useApp((s) => s.openLicense);

  const licOk = license?.ok;
  const successRate =
    stats.total > 0 ? `${Math.round((stats.successes / stats.total) * 100)}%` : "0%";

  return (
    <motion.header
      className="header"
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <div className="logo-tile">IR</div>
      <div className="brand-block">
        <div className="brand-title">InstaReport</div>
        <div className="brand-sub">
          {boot ? `v${boot.version}  •  ${accountsCount} accounts  •  ${proxiesCount} proxies` : "connecting…"}
        </div>
      </div>
      <div className="header-right">
        <button
          className={`license-pill ${licOk ? "ok" : "warn"} clickable`}
          onClick={openLicense}
          title="Manage license"
        >
          <span className="dot">●</span>
          {license === null ? "Checking…" : licOk ? "Licensed" : "Unlicensed"}
          <span className="chev">▾</span>
        </button>
        <div className="stat-row">
          <motion.div className="stat-tile" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
            <span className="label">Reports</span>
            <span className="value" style={{ color: "var(--accent-green)" }}>
              {formatCount(stats.total)}
            </span>
          </motion.div>
          <motion.div className="stat-tile" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.18 }}>
            <span className="label">Success</span>
            <span className="value" style={{ color: "var(--accent-blue)" }}>
              {successRate}
            </span>
          </motion.div>
        </div>
      </div>
    </motion.header>
  );
}
