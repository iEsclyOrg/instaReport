import { useState } from "react";
import { motion } from "framer-motion";
import { useApp, type Account } from "../store";
import ToolDialog from "./ToolDialog";

export function AccountsModal() {
  const draft = useApp((s) => s.accountsDraft);
  const update = useApp((s) => s.updateAccountsDraft);
  const save = useApp((s) => s.saveAccounts);
  const close = useApp((s) => s.closeAccounts);

  function patch(i: number, field: "user" | "pass", value: string) {
    const next = draft.map((a, idx) => (idx === i ? { ...a, [field]: value } : a));
    update(next);
  }

  function addRow() {
    update([...draft, { user: "", pass: "" }]);
  }

  function removeRow(i: number) {
    update(draft.filter((_, idx) => idx !== i));
  }

  return (
    <div className="overlay">
      <motion.div
        className="modal wide"
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.16, ease: "easeOut" }}
      >
        <h3>Accounts</h3>
        <p className="hint">
          {draft.length} account{draft.length === 1 ? "" : "s"} — usernames and passwords are
          encrypted when saved.
        </p>
        <div className="accounts-table">
          {draft.map((a: Account, i: number) => (
            <div className="accounts-row" key={i}>
              <input
                className="field"
                placeholder="username"
                value={a.user}
                onChange={(e) => patch(i, "user", e.target.value)}
                spellCheck={false}
              />
              <input
                className="field"
                placeholder="password"
                type="password"
                value={a.pass}
                onChange={(e) => patch(i, "pass", e.target.value)}
                spellCheck={false}
              />
              <button
                className="btn btn-danger"
                style={{ padding: "6px 8px" }}
                onClick={() => removeRow(i)}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        <button className="btn btn-ghost" onClick={addRow}>
          + Add account
        </button>
        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={close}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={() => void save()}>
            Save
          </button>
        </div>
      </motion.div>
    </div>
  );
}

function LicenseModal() {
  const license = useApp((s) => s.license);
  const activate = useApp((s) => s.activateLicense);
  const close = useApp((s) => s.closeLicense);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function submit() {
    if (!code.trim()) {
      setMsg("Please enter a license key");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const ok = await activate(code.trim());
      if (!ok) setMsg("Activation failed — check the key and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="overlay">
      <motion.div
        className="modal"
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.16, ease: "easeOut" }}
      >
        <h3>License Activation</h3>
        <p className="hint">
          {license?.ok
            ? `Licensed — ${license.code ?? "key saved"}. Enter a new key to re-activate.`
            : "Enter your license key to activate InstaReport."}
        </p>
        <input
          className="field"
          style={{ width: "100%" }}
          placeholder="License key"
          value={code}
          autoFocus
          spellCheck={false}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        {msg && <p className="tool-msg warn">{msg}</p>}
        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={close}>
            {license?.ok ? "Close" : "Skip for now"}
          </button>
          <button className="btn btn-primary" onClick={submit} disabled={busy || !code.trim()}>
            {busy ? "Activating…" : "Activate"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

function PromptModal() {  const otp = useApp((s) => s.otpPrompt);
  const captcha = useApp((s) => s.captchaPrompt);
  const submitOtp = useApp((s) => s.submitOtp);
  const submitCaptcha = useApp((s) => s.submitCaptcha);
  const dismiss = useApp((s) => s.dismissPrompt);
  const [value, setValue] = useState("");

  const isOtp = Boolean(otp);
  const title = isOtp ? "2FA code required" : "Manual CAPTCHA solve";
  const hint = isOtp
    ? `Enter the 2FA code for @${otp?.user} (${otp?.platform})`
    : `Solve the CAPTCHA on ${captcha?.url ?? ""}`;

  function submit() {
    if (!value.trim()) return;
    if (isOtp && otp) void submitOtp(otp.key, value.trim());
    else if (captcha) void submitCaptcha(captcha.key, value.trim());
    setValue("");
  }

  return (
    <div className="overlay">
      <motion.div
        className="modal"
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.16, ease: "easeOut" }}
      >
        <h3>{title}</h3>
        <p className="hint">{hint}</p>
        <input
          className="field"
          style={{ width: "100%" }}
          value={value}
          autoFocus
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={dismiss}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={submit} disabled={!value.trim()}>
            Submit
          </button>
        </div>
      </motion.div>
    </div>
  );
}

export function Modals() {
  const showAccounts = useApp((s) => s.showAccounts);
  const showLicense = useApp((s) => s.showLicense);
  const hasOtp = useApp((s) => Boolean(s.otpPrompt));
  const hasCaptcha = useApp((s) => Boolean(s.captchaPrompt));
  const hasTool = useApp((s) => Boolean(s.toolDialog));

  if (showAccounts) return <AccountsModal />;
  if (showLicense) return <LicenseModal />;
  if (hasOtp || hasCaptcha) return <PromptModal />;
  if (hasTool) return <ToolDialog />;
  return null;
}
