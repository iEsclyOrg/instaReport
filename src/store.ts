import { create } from "zustand";
import { call, initEvents } from "./api";

export interface Account {
  user: string;
  pass: string;
}

export interface PluginInfo {
  name: string;
  key: string;
  enabled: boolean;
  version: string;
  description: string;
}

export interface LicenseInfo {
  ok: boolean;
  code: string | null;
  msg: string | null;
}

export interface Stats {
  total: number;
  successes: number;
}

export interface ConfigState {
  target: string;
  workers: number;
  platform: string;
  reason: string;
  headless: boolean;
  api_mode: string;
  cooldown_secs: number;
  favorites: string[];
  sched_enabled: boolean;
  sched_time: string;
  sched_interval: number;
}

export interface BootstrapData {
  version: string;
  tabs: [string, number][];
  modules: Record<string, [string, string, string, string, string][]>;
  platforms: [string, string][];
  reasons: [string, string][];
  config: ConfigState;
  accounts: Account[];
  proxies_count: number;
  license: LicenseInfo;
  plugins: PluginInfo[];
  stats: Stats;
}

export type ModuleDef = [label: string, status: string, icon: string, desc: string, key: string];

export interface LogLine {
  msg: string;
  tag: string;
  id: number;
}

export interface HistoryRow {
  timestamp: string;
  target: string;
  platform: string;
  reason: string;
  successes: number;
  total: number;
  elapsed_s: number;
}

interface OtpPrompt {
  key: string;
  platform: string;
  user: string;
}

interface CaptchaPrompt {
  key: string;
  type: string;
  url: string;
}

export interface ToolField {
  key: string;
  label: string;
  type: string;
  required?: boolean;
  placeholder?: string;
  default?: string | number | boolean;
  options?: string[];
  min?: number;
  max?: number;
  mono?: boolean;
}

export interface ToolColumn {
  key: string;
  label: string;
  hidden?: boolean;
}

export interface ToolActionDef {
  label: string;
  param: string;
  danger?: boolean;
}

export interface ToolSchema {
  key: string;
  title: string;
  kind: "action" | "form" | "table";
  desc?: string;
  button?: string;
  danger?: boolean;
  available?: boolean;
  fields?: ToolField[];
  inputs?: ToolField[];
  columns?: ToolColumn[];
  actions?: ToolActionDef[];
  row_actions?: ToolActionDef[];
}

export interface ToolResult {
  message?: string;
  url?: string;
  columns?: string[];
  rows?: unknown[][];
}

const MAX_CONSOLE = 800;

interface AppState {
  boot: BootstrapData | null;
  loading: boolean;
  error: string | null;
  activeTab: string;
  console: LogLine[];
  running: boolean;
  accountsCount: number;
  proxiesCount: number;
  license: LicenseInfo | null;
  stats: Stats;
  history: HistoryRow[];
  historyTotal: number;
  historyPage: number;
  historyPageSize: number;
  otpPrompt: OtpPrompt | null;
  captchaPrompt: CaptchaPrompt | null;
  showAccounts: boolean;
  accountsDraft: Account[];
  toolDialog: { schema: ToolSchema } | null;
  showLicense: boolean;
  plugins: PluginInfo[];

  init: () => Promise<void>;
  selectTab: (name: string) => void;
  pushLog: (msg: string, tag: string) => void;
  clearConsole: () => void;
  startRun: (target: string, platform: string, reason: string, workers: number) => Promise<void>;
  stopRun: () => Promise<void>;
  refreshHistory: () => Promise<void>;
  historyPageDelta: (delta: number) => Promise<void>;
  clearHistory: () => Promise<void>;
  submitOtp: (key: string, code: string) => Promise<void>;
  submitCaptcha: (key: string, answer: string) => Promise<void>;
  dismissPrompt: () => void;
  openAccounts: () => void;
  closeAccounts: () => void;
  updateAccountsDraft: (accounts: Account[]) => void;
  saveAccounts: () => Promise<void>;
  openToolDialog: (key: string) => Promise<void>;
  closeToolDialog: () => void;
  runTool: (key: string, values: Record<string, unknown>) => Promise<ToolResult>;
  toggleFavorite: (key: string) => Promise<void>;
  openLicense: () => void;
  closeLicense: () => void;
  activateLicense: (code: string) => Promise<boolean>;
  togglePlugin: (key: string, enabled: boolean) => Promise<void>;
  enableAllPlugins: () => Promise<void>;
  disableAllPlugins: () => Promise<void>;
  refreshPlugins: () => Promise<void>;
}

export const useApp = create<AppState>((set, get) => {
  let logId = 0;

  function pushLog(msg: string, tag: string) {
    logId += 1;
    const entry: LogLine = { msg, tag, id: logId };
    set((s) => {
      const consoleLines = [...s.console, entry];
      if (consoleLines.length > MAX_CONSOLE) {
        consoleLines.splice(0, consoleLines.length - MAX_CONSOLE);
      }
      return { console: consoleLines };
    });
  }

  async function bootstrap(): Promise<BootstrapData> {
    return await call<BootstrapData>("bootstrap");
  }

  async function refreshHistory() {
    const s = get();
    const res = await call<{ rows: HistoryRow[]; total: number }>("history", {
      page: s.historyPage,
      size: s.historyPageSize,
    });
    set({ history: res.rows, historyTotal: res.total });
  }

  return {
    boot: null,
    loading: true,
    error: null,
    activeTab: "",
    console: [],
    running: false,
    accountsCount: 0,
    proxiesCount: 0,
    license: null,
    stats: { total: 0, successes: 0 },
    history: [],
    historyTotal: 0,
    historyPage: 0,
    historyPageSize: 100,
    otpPrompt: null,
    captchaPrompt: null,
    showAccounts: false,
    accountsDraft: [],
    toolDialog: null,
    showLicense: false,
    plugins: [],

    init: async () => {
      await initEvents((name, data) => {
        const d = data as Record<string, unknown>;
        switch (name) {
          case "log":
            get().pushLog(String(d.msg ?? ""), String(d.tag ?? "dim"));
            break;
          case "status":
            set({ running: d.state === "running" });
            break;
          case "stats":
            set({
              stats: {
                total: Number(d.total ?? 0),
                successes: Number(d.successes ?? 0),
              },
            });
            break;
          case "otp":
            set({
              otpPrompt: {
                key: String(d.key),
                platform: String(d.platform),
                user: String(d.user),
              },
            });
            break;
          case "captcha":
            set({
              captchaPrompt: {
                key: String(d.key),
                type: String(d.type),
                url: String(d.url),
              },
            });
            break;
        }
      });

      try {
        const boot = await bootstrap();
        set({
          boot,
          loading: false,
          activeTab: boot.tabs[0]?.[0] ?? "",
          accountsCount: boot.accounts.length,
          proxiesCount: boot.proxies_count,
          license: boot.license,
          stats: boot.stats,
          accountsDraft: boot.accounts,
          plugins: boot.plugins,
          error: null,
        });
        await get().refreshHistory();
        pushLog(`InstaReport v${boot.version} — sidecar connected`, "ok");
      } catch (e) {
        set({ loading: false, error: String(e) });
        pushLog(`Backend failed to start: ${e}`, "err");
      }
    },

    selectTab: (name) => set({ activeTab: name }),

    pushLog,
    clearConsole: () => set({ console: [] }),

    startRun: async (target, platform, reason, workers) => {
      if (!target) {
        pushLog("No target set — enter a username", "warn");
        return;
      }
      set({ running: true });
      pushLog(
        `[START] Reporting @${target} on ${platform} (${reason}, ${workers} workers)`,
        "sys",
      );
      try {
        await call("start_run", { target, platform, reason, workers });
      } catch (e) {
        set({ running: false });
        pushLog(`Failed to start: ${e}`, "err");
      }
    },

    stopRun: async () => {
      try {
        await call("stop_run");
        pushLog("⏹ STOP pressed — signalling all sessions", "err");
      } catch (e) {
        pushLog(`Stop failed: ${e}`, "err");
      }
    },

    refreshHistory,
    historyPageDelta: async (delta) => {
      const max = Math.max(0, Math.ceil(get().historyTotal / get().historyPageSize) - 1);
      const page = Math.max(0, Math.min(get().historyPage + delta, max));
      set({ historyPage: page });
      await get().refreshHistory();
    },

    clearHistory: async () => {
      try {
        await call("clear_history");
        set({ history: [], historyTotal: 0, historyPage: 0, stats: { total: 0, successes: 0 } });
        pushLog("Run history cleared", "ok");
      } catch (e) {
        pushLog(`Clear history failed: ${e}`, "err");
      }
    },

    submitOtp: async (key, code) => {
      try {
        await call("otp_submit", { key, code });
      } catch (e) {
        pushLog(`OTP submit failed: ${e}`, "err");
      }
      set({ otpPrompt: null });
    },

    submitCaptcha: async (key, answer) => {
      try {
        await call("captcha_submit", { key, answer });
      } catch (e) {
        pushLog(`Captcha submit failed: ${e}`, "err");
      }
      set({ captchaPrompt: null });
    },

    dismissPrompt: () => set({ otpPrompt: null, captchaPrompt: null }),

    openAccounts: () => set({ showAccounts: true, accountsDraft: get().accountsDraft }),
    closeAccounts: () => set({ showAccounts: false }),
    updateAccountsDraft: (accounts) => set({ accountsDraft: accounts }),

    saveAccounts: async () => {
      const accounts = get().accountsDraft;
      try {
        const res = await call<{ count: number }>("save_accounts", { accounts });
        set({ accountsCount: res.count, showAccounts: false });
        pushLog(`Accounts saved: ${res.count}`, "ok");
      } catch (e) {
        pushLog(`Save accounts failed: ${e}`, "err");
      }
    },

    openToolDialog: async (key) => {
      try {
        const schema = await call<ToolSchema>("tool_schema", { key });
        set({ toolDialog: { schema } });
      } catch (e) {
        pushLog(`Tool unavailable: ${e}`, "err");
      }
    },

    closeToolDialog: () => set({ toolDialog: null }),

    runTool: async (key, values) => {
      try {
        const res = await call<ToolResult>("tool_run", { key, values });
        if (res.message) pushLog(`[${key}] ${res.message}`, "ok");
        return res;
      } catch (e) {
        pushLog(`[${key}] failed: ${e}`, "err");
        throw e;
      }
    },

    toggleFavorite: async (key) => {
      try {
        const res = await call<{ favorite: boolean; favorites: string[] }>("favorite_toggle", {
          key,
        });
        set((s) => {
          if (!s.boot) return {};
          return { boot: { ...s.boot, config: { ...s.boot.config, favorites: res.favorites } } };
        });
      } catch (e) {
        pushLog(`Favorite toggle failed: ${e}`, "err");
      }
    },

    openLicense: () => set({ showLicense: true }),
    closeLicense: () => set({ showLicense: false }),

    activateLicense: async (code) => {
      try {
        const res = await call<{ ok: boolean; msg: string }>("license_activate", { code });
        if (res.ok) {
          set({ license: { ok: true, code, msg: res.msg }, showLicense: false });
          pushLog(`License activated: ${res.msg}`, "ok");
        } else {
          pushLog(`Activation failed: ${res.msg}`, "err");
        }
        return res.ok;
      } catch (e) {
        pushLog(`Activation error: ${e}`, "err");
        return false;
      }
    },

    togglePlugin: async (key, enabled) => {
      set((s) => ({
        plugins: s.plugins.map((p) => (p.key === key ? { ...p, enabled } : p)),
      }));
      try {
        await call("plugin_toggle", { key, enabled });
      } catch (e) {
        set((s) => ({
          plugins: s.plugins.map((p) =>
            p.key === key ? { ...p, enabled: !enabled } : p,
          ),
        }));
        pushLog(`Plugin toggle failed: ${e}`, "err");
      }
    },

    enableAllPlugins: async () => {
      for (const p of get().plugins) {
        await call("plugin_toggle", { key: p.key, enabled: true }).catch(() => null);
      }
      set((s) => ({ plugins: s.plugins.map((p) => ({ ...p, enabled: true })) }));
      pushLog("All plugins enabled", "ok");
    },

    disableAllPlugins: async () => {
      for (const p of get().plugins) {
        await call("plugin_toggle", { key: p.key, enabled: false }).catch(() => null);
      }
      set((s) => ({ plugins: s.plugins.map((p) => ({ ...p, enabled: false })) }));
      pushLog("All plugins disabled", "err");
    },

    refreshPlugins: async () => {
      try {
        const res = await call<{ plugins: PluginInfo[] }>("plugins_refresh");
        set({ plugins: res.plugins });
      } catch (e) {
        pushLog(`Plugin refresh failed: ${e}`, "err");
      }
    },
  };
});
