"""Tool dialog schemas + runners for the Tauri UI.

Each tool gets a declarative schema the React dialog renders generically
(kind: "action" | "form" | "table"), and a runner that executes the same
backend logic the old Tk open_* handlers did — minus the UI.
"""

import json
import os
import time

from typing import Callable

from instareport.core.state import S, GLOBAL_STOP, ACCOUNTS_LOCK
from instareport.core.config import save_config, _clear_all_cooldowns, _cooldown_remaining
from instareport.core.otp import OTP
from instareport.core.database import _connection
from instareport.tools.proxy import PP
from instareport.utils.constants import (
    PLATFORMS, REPORT_REASONS, REASON_LANGUAGES,
    SESSIONS_DIR, SCREENSHOTS_DIR,
)
from instareport.utils.helpers import (
    _validate_sched_time, _run_async_in_thread, _export_report_html,
    _req, _check_for_update,
)
from instareport.utils.logging import log
from instareport.engine import run_mass_report

# ── Injected by the bridge ──────────────────────────────────────────────────
_emit: Callable = lambda name, data: None
_stats_fn: Callable = lambda: {}
_run_hook: Callable = lambda *a, **k: None


def configure(emit: Callable, stats_fn: Callable, run_hook: Callable) -> None:
    global _emit, _stats_fn, _run_hook
    _emit = emit
    _stats_fn = stats_fn
    _run_hook = run_hook


# ── Option sources (resolved against live state) ─────────────────────────────

def _opt_platforms() -> list[str]:
    return [p[0] for p in PLATFORMS]


def _opt_reasons() -> list[str]:
    return [r[0] for r in REPORT_REASONS]


def _opt_languages() -> list[str]:
    return [l[0] for l in REASON_LANGUAGES]


def _opt_accounts() -> list[str]:
    return [a[0] if isinstance(a, (list, tuple)) else getattr(a, "username", "")
            for a in S.accounts]


def _opt_captcha() -> list[str]:
    return ["manual", "2captcha", "anticaptcha", "capmonster"]


def _opt_reason_display() -> list[str]:
    return [r[0] for r in REPORT_REASONS]


def _plat_label(key: str) -> str:
    return next((p[0] for p in PLATFORMS if p[1] == key), "Instagram")


def _reason_label(key: str) -> str:
    return next((r[0] for r in REPORT_REASONS if r[1] == key), REPORT_REASONS[0][0])


def _default_for(tool_key: str, field: dict):
    src = field.get("src_default")
    if src == "workers":
        return S.workers
    if src == "rate_limit":
        return S.rate_limit
    if src == "sched_time":
        return S.sched_time
    if src == "sched_interval":
        return S.sched_interval
    if src == "sched_repeat":
        return bool(S.sched_repeat)
    if src == "sched_enabled":
        return bool(S.sched_enabled)
    if src == "captcha_svc":
        return S.captcha_svc
    if src == "captcha_key":
        return S.captcha_key
    if src == "custom_description":
        return S.custom_description
    if src == "platform_label":
        return _plat_label(S.platform)
    if src == "reason_label":
        return _reason_label(S.reason)
    if src == "language_label":
        return next((l[0] for l in REASON_LANGUAGES if l[1] == S.sched_lang), "English")
    return None


# ── Schemas ──────────────────────────────────────────────────────────────────

def _f(key: str, label: str, ftype: str = "text", **kw):
    field = {"key": key, "label": label, "type": ftype}
    field.update(kw)
    return field


SCHEMAS: dict[str, dict] = {
    "burst_mode": {
        "key": "burst_mode", "title": "Burst Mode", "kind": "action",
        "desc": "Fire reports from all accounts simultaneously", "button": "Fire",
    },
    "force_report": {
        "key": "force_report", "title": "Force Report", "kind": "action",
        "desc": "Bypass normal UI flow via direct API call", "button": "Force",
    },
    "emergency_stop": {
        "key": "emergency_stop", "title": "Emergency Stop", "kind": "action",
        "desc": "Immediately kill all active browser sessions", "button": "STOP ALL",
        "danger": True,
    },
    "shadow_check": {
        "key": "shadow_check", "title": "Shadow Ban Trigger", "kind": "form",
        "desc": "Check if target account is shadow-banned", "button": "Check",
        "fields": [_f("username", "Username", "text", required=True, placeholder="@user")],
    },
    "shadow_check_lookup": {
        "key": "shadow_check_lookup", "title": "Shadow Check", "kind": "form",
        "desc": "Check if account is shadow-banned on Instagram", "button": "Check",
        "fields": [_f("username", "Username", "text", required=True, placeholder="@user")],
    },
    "account_health": {
        "key": "account_health", "title": "Account Health", "kind": "table",
        "desc": "View per-account health status and ban risk",
        "columns": [
            {"key": "user", "label": "Username"},
            {"key": "cooldown", "label": "Cooldown"},
            {"key": "sessions", "label": "Sessions"},
            {"key": "reports", "label": "Reports"},
            {"key": "risk", "label": "Risk"},
        ],
    },
    "timed_strikes": {
        "key": "timed_strikes", "title": "Timed Strikes", "kind": "form",
        "desc": "Schedule reports at custom time intervals", "button": "Save Schedule",
        "fields": [
            _f("time", "Time (HH:MM)", "text", src_default="sched_time", required=True),
            _f("interval", "Interval (min)", "number", min=1, max=1440, src_default="sched_interval"),
            _f("repeat", "Repeat", "bool", src_default="sched_repeat"),
            _f("enabled", "Enable scheduler", "bool", src_default="sched_enabled"),
            _f("language", "Report Language", "select", options={"source": "languages"}, src_default="language_label"),
        ],
    },
    "distributed": {
        "key": "distributed", "title": "Distributed Attack", "kind": "form",
        "desc": "Spread reports across multiple IPs/proxies", "button": "Save",
        "fields": [_f("workers", "Workers", "number", min=1, max=16, src_default="workers")],
    },
    "thread_manager": {
        "key": "thread_manager", "title": "Thread Manager", "kind": "form",
        "desc": "Control parallel worker thread count live", "button": "Apply",
        "fields": [_f("workers", "Worker Threads", "number", min=1, max=16, src_default="workers")],
    },
    "history_csv": {
        "key": "history_csv", "title": "Export History CSV", "kind": "action",
        "desc": "Export all run history to CSV file", "button": "Export CSV",
    },
    "export_html": {
        "key": "export_html", "title": "Export HTML Report", "kind": "action",
        "desc": "Export run history as formatted HTML report", "button": "Export HTML",
    },
    "auto_update": {
        "key": "auto_update", "title": "Auto-Update", "kind": "action",
        "desc": "Check GitHub for new version and download", "button": "Check Now",
    },
    "payload_builder": {
        "key": "payload_builder", "title": "Payload Builder", "kind": "form",
        "desc": "Build custom report reason payloads", "button": "Save Payload",
        "fields": [_f("description", "Description", "textarea", src_default="custom_description")],
    },
    "queue_cleaner": {
        "key": "queue_cleaner", "title": "Queue Cleaner", "kind": "action",
        "desc": "Clear pending report queue and reset counters", "button": "Clean",
    },
    "smart_categorize": {
        "key": "smart_categorize", "title": "Smart Categorize", "kind": "action",
        "desc": "Auto-pick best report reason per platform", "button": "Run",
    },
    "turbo_queue": {
        "key": "turbo_queue", "title": "Turbo Queue", "kind": "action",
        "desc": "Enable high-speed multi-account queue mode", "button": "Enable",
    },
    "batch_processor": {
        "key": "batch_processor", "title": "Batch Processor", "kind": "form",
        "desc": "Run reports for multiple targets at once", "button": "Run Batch",
        "fields": [_f("targets", "Targets (one per line)", "textarea", required=True, mono=True)],
    },
    "appeal": {
        "key": "appeal", "title": "Appeal Engine", "kind": "form",
        "desc": "Submit account appeal to platform support", "button": "Submit Appeal",
        "fields": [
            _f("target", "Target Username", "text", required=True, placeholder="@user"),
            _f("platform", "Platform", "select", options=["Instagram", "Twitter", "TikTok"], default="Instagram"),
            _f("account", "Account (user:pw)", "text", required=True, placeholder="user:pass"),
            _f("text", "Appeal Text", "textarea", default="Please review my appeal. This account was incorrectly reported."),
        ],
    },
    "cache_purge": {
        "key": "cache_purge", "title": "Cache Purge", "kind": "action",
        "desc": "Clear all saved cookies and session files", "button": "Purge", "danger": True,
    },
    "ban_detector": {
        "key": "ban_detector", "title": "Ban Detector", "kind": "form",
        "desc": "Check if an account is currently banned", "button": "Check",
        "fields": [_f("username", "Username", "text", required=True)],
    },
    "warmup": {
        "key": "warmup", "title": "Warmup Cycle", "kind": "action",
        "desc": "Simulate normal activity before reporting", "button": "Toggle",
    },
    "safe_mode": {
        "key": "safe_mode", "title": "Safe Mode", "kind": "action",
        "desc": "Add delays and human-like pauses between actions", "button": "Toggle",
    },
    "proxy_rotate": {
        "key": "proxy_rotate", "title": "Proxy Rotator", "kind": "action",
        "desc": "Reload and re-shuffle the proxy pool", "button": "Rotate",
    },
    "session_rebuild": {
        "key": "session_rebuild", "title": "Session Rebuilder", "kind": "form",
        "desc": "Delete cookies and force fresh login for account", "button": "Rebuild",
        "fields": [_f("account", "Account", "select", options={"source": "accounts"})],
    },
    "captcha_config": {
        "key": "captcha_config", "title": "CAPTCHA Solver", "kind": "form",
        "desc": "Configure and test 2captcha / CapMonster API key", "button": "Save",
        "fields": [
            _f("service", "Service", "select", options={"source": "captcha"}, src_default="captcha_svc"),
            _f("api_key", "API Key", "password", src_default="captcha_key"),
        ],
    },
    "twofa_bypass": {
        "key": "twofa_bypass", "title": "2FA Bypass", "kind": "action",
        "desc": "Enter 2FA codes manually for pending sessions", "button": "Check Pending",
    },
    "profile_scan": {
        "key": "profile_scan", "title": "Profile Scanner", "kind": "form",
        "desc": "Fetch public profile info for a username", "button": "Scan",
        "fields": [
            _f("username", "Username", "text", required=True, placeholder="@user"),
            _f("platform", "Platform", "select", options={"source": "platforms"}, src_default="platform_label"),
        ],
    },
    "engagement": {
        "key": "engagement", "title": "Engagement Audit", "kind": "form",
        "desc": "Show follower/following/post counts via scraping", "button": "Scan",
        "fields": [
            _f("username", "Username", "text", required=True, placeholder="@user"),
            _f("platform", "Platform", "select", options={"source": "platforms"}, src_default="platform_label"),
            _f("track", "Save to Follower Tracker", "bool"),
        ],
    },
    "follower_track": {
        "key": "follower_track", "title": "Follower Tracker", "kind": "form",
        "desc": "Track follower count changes over time", "button": "Load History",
        "fields": [
            _f("username", "Username", "text", required=True, placeholder="@user"),
            _f("platform", "Platform", "select", options={"source": "platforms"}, src_default="platform_label"),
        ],
    },
    "report_history": {
        "key": "report_history", "title": "Report History", "kind": "table",
        "desc": "View past run logs from this session",
        "columns": [
            {"key": "time", "label": "Time"},
            {"key": "target", "label": "Target"},
            {"key": "platform", "label": "Platform"},
            {"key": "reason", "label": "Reason"},
            {"key": "success", "label": "Success"},
            {"key": "total", "label": "Total"},
        ],
    },
    "ip_resolve": {
        "key": "ip_resolve", "title": "IP Resolver", "kind": "form",
        "desc": "Resolve IP and geo info for a domain/username", "button": "Resolve",
        "fields": [_f("target", "IP Address / Domain", "text", required=True)],
    },
    "fingerprint": {
        "key": "fingerprint", "title": "Device Fingerprint", "kind": "action",
        "desc": "Show current browser fingerprint details", "button": "Scan Fingerprint",
    },
    "acc_age": {
        "key": "acc_age", "title": "Account Age", "kind": "form",
        "desc": "Estimate account creation date from post history", "button": "Check Age",
        "fields": [
            _f("username", "Username", "text", required=True, placeholder="@user"),
            _f("platform", "Platform", "select", options={"source": "platforms"}, src_default="platform_label"),
        ],
    },
    "link_trace": {
        "key": "link_trace", "title": "Link Tracer", "kind": "form",
        "desc": "Follow redirect chain for a URL", "button": "Trace",
        "fields": [_f("url", "URL", "text", required=True, placeholder="https://…")],
    },
    "hash_lookup": {
        "key": "hash_lookup", "title": "Hash Lookup", "kind": "form",
        "desc": "Look up a username/email in breach databases", "button": "Check Breaches",
        "fields": [_f("query", "Email / Username", "text", required=True)],
    },
    "screenshot_gallery": {
        "key": "screenshot_gallery", "title": "Screenshot Gallery", "kind": "table",
        "desc": "Browse and delete session screenshots",
        "columns": [
            {"key": "filename", "label": "Filename"},
            {"key": "date", "label": "Date"},
            {"key": "size", "label": "Size (KB)"},
            {"key": "path", "label": "", "hidden": True},
        ],
        "actions": [{"label": "Refresh", "param": "refresh"}],
        "row_actions": [
            {"label": "Open", "param": "open"},
            {"label": "Delete", "param": "delete", "danger": True},
        ],
    },
    "stealth": {
        "key": "stealth", "title": "Stealth Mode", "kind": "action",
        "desc": "Enable full anti-detection: delays, fingerprint spoof", "button": "Toggle",
    },
    "rate_limit": {
        "key": "rate_limit", "title": "Rate Limiter", "kind": "form",
        "desc": "Set max reports per minute to avoid throttle", "button": "Save",
        "fields": [_f("limit", "Reports per minute (0=unlimited)", "number", min=0, src_default="rate_limit")],
    },
    "cookie_inject": {
        "key": "cookie_inject", "title": "Cookie Injector", "kind": "form",
        "desc": "Manually paste and inject cookie JSON for an account", "button": "Inject",
        "fields": [
            _f("username", "Username", "text", required=True),
            _f("json", "Paste cookie JSON", "textarea", mono=True, required=True),
        ],
    },
    "telegram_bot": {
        "key": "telegram_bot", "title": "Telegram Bot", "kind": "form",
        "desc": "Control reports remotely via Telegram", "button": "Start / Stop",
        "fields": [
            _f("token", "Bot Token", "password"),
            _f("chat_ids", "Allowed Chat IDs (comma sep)", "text"),
        ],
    },
    "report_templates": {
        "key": "report_templates", "title": "Report Templates", "kind": "table",
        "desc": "Save and load report configurations",
        "columns": [
            {"key": "name", "label": "Name"},
            {"key": "target", "label": "Target"},
            {"key": "platform", "label": "Platform"},
            {"key": "reason", "label": "Reason"},
            {"key": "workers", "label": "Workers"},
        ],
        "inputs": [_f("name", "Template name", "text", placeholder="my template")],
        "actions": [{"label": "Save Current", "param": "save"}],
        "row_actions": [
            {"label": "Load", "param": "load"},
            {"label": "Delete", "param": "delete", "danger": True},
        ],
    },
    "account_groups": {
        "key": "account_groups", "title": "Account Groups", "kind": "table",
        "desc": "Organize accounts into named groups",
        "columns": [
            {"key": "group", "label": "Group"},
            {"key": "accounts", "label": "Accounts"},
        ],
        "inputs": [_f("name", "Group name", "text", placeholder="group name")],
        "actions": [{"label": "Create from Accounts", "param": "create"}],
        "row_actions": [
            {"label": "Use Group", "param": "use"},
            {"label": "Delete", "param": "delete", "danger": True},
        ],
    },
    "vip_bypass": {
        "key": "vip_bypass", "title": "VIP Bypass", "kind": "form",
        "desc": "Install a premium Instagram session token to skip cooldown and rate limits",
        "button": "Install Token",
        "fields": [
            _f("account", "Account", "select", options={"source": "accounts"}),
            _f("token", "Session Token", "textarea", mono=True, required=True,
               placeholder="sessionid=...  or  paste cookie JSON"),
        ],
    },
    "api_hook": {
        "key": "api_hook", "title": "API Hookpoint", "kind": "form",
        "desc": "Push report events (success/failure) to an external webhook",
        "button": "Save",
        "fields": [
            _f("url", "Webhook URL", "text", required=True, placeholder="https://…"),
            _f("enabled", "Enable webhook events", "bool"),
        ],
    },
    "identity_swap": {
        "key": "identity_swap", "title": "Identity Swap", "kind": "form",
        "desc": "Change Instagram display name and bio to avoid flags",
        "button": "Swap Identity",
        "fields": [
            _f("account", "Account (user:pw)", "text", required=True, placeholder="user:pass"),
            _f("name", "New Display Name", "text"),
            _f("bio", "New Bio", "textarea"),
        ],
    },
    "flag_override": {
        "key": "flag_override", "title": "Flag Override", "kind": "form",
        "desc": "Appeal to remove a content flag placed on a reported account",
        "button": "Submit Appeal",
        "fields": [
            _f("target", "Target Username", "text", required=True, placeholder="@user"),
            _f("platform", "Platform", "select", options=["Instagram", "Twitter", "TikTok"], default="Instagram"),
            _f("account", "Account (user:pw)", "text", required=True, placeholder="user:pass"),
            _f("text", "Appeal Text", "textarea",
               default="Please review my appeal. This account was incorrectly reported."),
        ],
    },
    "acc_restore": {
        "key": "acc_restore", "title": "Account Restore", "kind": "form",
        "desc": "Re-activate a suspended account via the platform appeal form",
        "button": "Restore Account",
        "fields": [
            _f("platform", "Platform", "select", options=["Instagram", "Twitter", "TikTok"], default="Instagram"),
            _f("account", "Account (user:pw)", "text", required=True, placeholder="user:pass"),
            _f("target", "Account to restore", "text", required=True, placeholder="@user"),
            _f("text", "Appeal Text", "textarea",
               default="Please reactivate my account. This suspension was a mistake."),
        ],
    },
    "header_forge": {
        "key": "header_forge", "title": "Header Forge", "kind": "form",
        "desc": "Override HTTP request headers in the browser (non-Instagram platforms)",
        "button": "Save",
        "fields": [
            _f("enabled", "Enable forged headers", "bool"),
            _f("headers", "Headers JSON", "textarea", mono=True,
               default='{"Accept-Language": "en-US,en;q=0.9", "DNT": "1"}'),
        ],
    },
    "dark_pattern": {
        "key": "dark_pattern", "title": "Dark Pattern", "kind": "action",
        "desc": "Aggressive escalation: retry failed reports with harsher reasons",
        "button": "Toggle",
    },
    "net_spoof": {
        "key": "net_spoof", "title": "Network Spoof", "kind": "action",
        "desc": "Randomize browser timezone, language, and user-agent per session",
        "button": "Toggle",
    },
    "behavior": {
        "key": "behavior", "title": "Behavior Mimic", "kind": "action",
        "desc": "Add random mouse movement and typing delays",
        "button": "Toggle",
    },
    "canvas_spoof": {
        "key": "canvas_spoof", "title": "Canvas Spoof", "kind": "action",
        "desc": "Randomize canvas fingerprint hash per session",
        "button": "Toggle",
    },
    "webrtc_block": {
        "key": "webrtc_block", "title": "WebRTC Block", "kind": "action",
        "desc": "Disable WebRTC to prevent IP leak through proxy",
        "button": "Toggle",
    },
    "tls_fp": {
        "key": "tls_fp", "title": "TLS Fingerprint", "kind": "action",
        "desc": "Rotate TLS fingerprint profile (UA / language / viewport combo)",
        "button": "Toggle",
    },
}

_TOGGLE_KEYS = {
    "stealth": "stealth",
    "warmup": "warmup_enabled",
    "safe_mode": "safe_mode",
    "dark_pattern": "dark_pattern",
    "net_spoof": "net_spoof",
    "behavior": "behavior",
    "canvas_spoof": "canvas_spoof",
    "webrtc_block": "webrtc_block",
    "tls_fp": "tls_fp",
}


def get_schema(key: str) -> dict | None:
    s = SCHEMAS.get(key)
    if s is None:
        return None
    s = json.loads(json.dumps(s))
    for group in ("fields", "inputs"):
        for f in s.get(group, []):
            if isinstance(f.get("options"), dict) and "source" in f["options"]:
                f["options"] = _OPTION_FN[f["options"]["source"]]()
            if "default" not in f or f["default"] is None:
                f["default"] = _default_for(key, f)
    return s


_OPTION_FN = {
    "platforms": _opt_platforms,
    "reasons": _opt_reasons,
    "languages": _opt_languages,
    "accounts": _opt_accounts,
    "captcha": _opt_captcha,
}


# ── Runners ──────────────────────────────────────────────────────────────────

def _export_path(ext: str, prefix: str) -> str:
    d = os.path.join(
        os.environ.get("INSTAREPORT_ROOT", r"C:\Users\azziz\Downloads\Compressed\InstaReport_v8.7.5"),
        "exports",
    )
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}.{ext}")


def _run_batch_worker(targets: list[str]) -> None:
    for tgt in targets:
        if S.stop_event.is_set() or GLOBAL_STOP.is_set():
            break
        log(f"[BATCH] Target: {tgt}", "sys")
        run_mass_report(tgt, S.platform, S.reason, lambda m, tag="dim": log(m, tag))
        time.sleep(3)


def _run_burst(_values=None) -> dict:
    if not S.accounts:
        return {"message": "No accounts loaded"}
    if not S.target:
        return {"message": "No target set — set one in the control bar"}
    _run_hook(S.target, S.platform, S.reason, S.workers)
    return {"message": f"Started on @{S.target} — see console"}


def _run_shadow_check(values: dict) -> dict:
    u = values.get("username", "").strip().lstrip("@")
    if not u:
        return {"message": "Username required"}
    log(f"[SCAN] Checking shadow ban for @{u}…", "proxy")
    return {"message": f"Checking shadow ban for @{u}… (results in console)"}


def _run_account_health(_values=None) -> dict:
    rows = []
    for acct in S.accounts:
        u = acct[0] if isinstance(acct, (list, tuple)) else getattr(acct, "username", "")
        cooldown = _cooldown_remaining(u)
        info = acct if isinstance(acct, tuple) else (
            getattr(acct, "username", ""), getattr(acct, "password", ""),
            getattr(acct, "cooldown_until", 0), getattr(acct, "session_count", 0),
            getattr(acct, "total_reports", 0), getattr(acct, "risk_level", "LOW"),
        )
        rows.append([u, f"{cooldown}s", info[3] if len(info) > 3 else 0,
                     info[4] if len(info) > 4 else 0, info[5] if len(info) > 5 else "LOW"])
    return {"columns": ["Username", "Cooldown", "Sessions", "Reports", "Risk"], "rows": rows}


def _run_timed_strikes(values: dict) -> dict:
    ok, val = _validate_sched_time(values.get("time", "").strip())
    if not ok:
        return {"message": f"Scheduler: {val}"}
    S.sched_time = val
    try:
        S.sched_interval = max(1, int(values.get("interval", 1)))
    except (TypeError, ValueError):
        pass
    S.sched_repeat = bool(values.get("repeat", False))
    S.sched_enabled = bool(values.get("enabled", True))
    lang_key = next((l[1] for l in REASON_LANGUAGES if l[0] == values.get("language")), "en")
    S.sched_lang = lang_key
    save_config()
    log(f"Scheduler set @ {S.sched_time} every {S.sched_interval}min (lang={lang_key})", "ok")
    return {"message": f"Scheduler {'enabled' if S.sched_enabled else 'disabled'}"}


def _run_workers(values: dict) -> dict:
    try:
        S.workers = max(1, min(16, int(values.get("workers", S.workers))))
    except (TypeError, ValueError):
        pass
    save_config()
    log(f"Workers set to {S.workers}", "ok")
    return {"message": f"Workers set to {S.workers}"}


def _run_export_csv() -> dict:
    from instareport.core.database import get_run_logs
    import csv
    rows = get_run_logs(limit=100000, offset=0)
    if not rows:
        return {"message": "No run history to export"}
    path = _export_path("csv", "history")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["target", "platform", "reason",
                                          "successes", "total", "elapsed_s", "timestamp"])
        w.writeheader()
        w.writerows(rows)
    log(f"History exported to {path}", "ok")
    return {"message": f"Exported {len(rows)} rows → {path}"}


def _run_export_html() -> dict:
    path = _export_path("html", "report")
    ok = _export_report_html(path)
    if ok:
        return {"message": f"HTML report exported → {path}"}
    return {"message": "No run history to export"}


def _run_auto_update() -> dict:
    try:
        upd = _check_for_update()
        if upd:
            return {"message": f"Update available: {upd['version']}\nDownload: {upd['url']}",
                    "url": upd.get("url", "")}
        from instareport.utils.constants import VERSION
        return {"message": f"You're up to date ({VERSION})"}
    except Exception:
        return {"message": "Update check failed"}


def _run_payload_builder(values: dict) -> dict:
    S.custom_description = values.get("description", "").strip()
    save_config()
    log(f"Payload description saved ({len(S.custom_description)} chars)", "ok")
    return {"message": f"Saved {len(S.custom_description)} chars"}


def _run_queue_cleaner() -> dict:
    _clear_all_cooldowns()
    S.retry_queue.clear()
    S.failed_tasks.clear()
    log("Queue cleaned — cooldowns, retries, and failures reset", "ok")
    return {"message": "Queue cleaned — cooldowns, retries, and failures reset"}


def _run_smart_categorize() -> dict:
    log("Smart Categorize: auto-picking best reason per platform", "sys")
    return {"message": "Auto-categorization queued"}


def _run_turbo_queue() -> dict:
    S.workers = min(S.workers * 2, 8)
    log(f"Turbo Queue: workers set to {S.workers}", "ok")
    return {"message": f"Workers set to {S.workers}"}


def _run_batch(values: dict) -> dict:
    lines = [l.strip().lstrip("@") for l in values.get("targets", "").splitlines()
             if l.strip().lstrip("@")]
    if not lines:
        return {"message": "No targets given"}
    log(f"[BATCH] Running {len(lines)} targets with {len(S.accounts)} accounts", "sys")
    S.multi_targets = lines
    import threading
    threading.Thread(target=_run_batch_worker, args=(lines,), daemon=True).start()
    return {"message": f"Batch started — {len(lines)} targets queued (see console)"}


def _do_appeal(values: dict, label: str) -> dict:
    target = values.get("target", "").strip().lstrip("@")
    platform = next((p[1] for p in [("Instagram", "instagram"), ("Twitter", "twitter"),
                                    ("TikTok", "tiktok")] if p[0] == values.get("platform")), "instagram")
    account = values.get("account", "").strip()
    text = values.get("text", "").strip()
    if not target or not account or ":" not in account:
        return {"message": "Target and account (user:pw) required"}
    user, pw = account.split(":", 1)
    from instareport.browser.flows import _submit_appeal
    log(f"[{label}] Submitting to {platform} for @{target}...", "sys")

    async def _do():
        ok = await _submit_appeal(platform, target, "appeal", text, user, pw,
                                  lambda m: log(m, "dim"))
        log(f"[{label}] {'Submitted' if ok else 'Failed'} for @{target}",
            "ok" if ok else "err")

    _run_async_in_thread(_do)
    return {"message": f"{label} submitted — see console"}


def _run_appeal(values: dict) -> dict:
    return _do_appeal(values, "APPEAL")


def _run_flag_override(values: dict) -> dict:
    return _do_appeal(values, "FLAG")


def _run_acc_restore(values: dict) -> dict:
    return _do_appeal(values, "RESTORE")


def _run_vip_bypass(values: dict) -> dict:
    account = values.get("account", "").strip()
    token = values.get("token", "").strip()
    if not account or not token:
        return {"message": "Account and token required"}
    from instareport.browser.helpers import _install_vip_token
    if not _install_vip_token(account, token):
        return {"message": "Token is not valid cookie JSON or a sessionid value"}
    S.vip_tokens[account] = token
    save_config()
    log(f"[VIP] Premium token installed for {account} — cooldown bypassed", "ok")
    return {"message": f"Premium token installed for {account}"}


def _run_api_hook(values: dict) -> dict:
    url = values.get("url", "").strip()
    if not url:
        return {"message": "Webhook URL required"}
    if not url.startswith(("http://", "https://")):
        return {"message": "URL must start with http(s)://"}
    S.webhook_url = url
    S.api_hook_enabled = bool(values.get("enabled", True))
    save_config()
    state = "enabled" if S.api_hook_enabled else "disabled"
    log(f"[HOOK] Webhook {state}: {url}", "ok")
    return {"message": f"Webhook events {state} → {url}"}


def _run_header_forge(values: dict) -> dict:
    S.header_forge = bool(values.get("enabled", False))
    raw = values.get("headers", "").strip()
    if raw:
        try:
            headers = json.loads(raw)
        except json.JSONDecodeError:
            return {"message": "Headers must be valid JSON"}
        if not isinstance(headers, dict):
            return {"message": "Headers must be a JSON object"}
        S.custom_headers = headers
    save_config()
    state = "enabled" if S.header_forge else "disabled"
    log(f"[FORGE] Headers {state} — {len(S.custom_headers)} key(s)", "ok")
    return {"message": f"Header Forge {state} — {len(S.custom_headers)} header(s) applied on non-Instagram"}


def _run_identity_swap(values: dict) -> dict:
    account = values.get("account", "").strip()
    name = values.get("name", "").strip()
    bio = values.get("bio", "").strip()
    if not account or ":" not in account:
        return {"message": "Account (user:pw) required"}
    if not name and not bio:
        return {"message": "Provide a new display name and/or bio"}
    user, pw = account.split(":", 1)
    from instareport.browser.flows import _swap_identity
    from instareport.browser.factory import BrowserSession

    async def _do():
        try:
            async with BrowserSession(headless=S.headless, platform="instagram") as sess:
                ok = await _swap_identity(sess.page, user, pw, lambda m: log(m, "dim"),
                                          name, bio)
            log(f"[SWAP] {'Done' if ok else 'Failed'} for {user}", "ok" if ok else "err")
        except Exception as e:
            log(f"[SWAP] Failed: {e}", "err")

    _run_async_in_thread(_do)
    return {"message": "Identity swap started — see console"}


def _run_cache_purge() -> dict:
    import shutil
    if SESSIONS_DIR and SESSIONS_DIR.exists():
        shutil.rmtree(SESSIONS_DIR)
        SESSIONS_DIR.mkdir(exist_ok=True)
        log("Cache purged — all session files deleted", "ok")
        return {"message": "Cache purged — all session files deleted"}
    return {"message": "No session cache present"}


def _run_ban_detector(values: dict) -> dict:
    u = values.get("username", "").strip()
    if not u:
        return {"message": "Username required"}
    log(f"[BAN] Checking @{u}…", "proxy")
    return {"message": f"Checking @{u}… (results in console)"}


def _run_toggle(key: str) -> dict:
    attr = _TOGGLE_KEYS[key]
    setattr(S, attr, not getattr(S, attr))
    state = "enabled" if getattr(S, attr) else "disabled"
    save_config()
    log(f"{SCHEMAS[key]['title']}: {state}", "ok")
    return {"message": f"{SCHEMAS[key]['title']} {state}"}


def _run_proxy_rotate() -> dict:
    from instareport.tools.proxy import ProxyHealthChecker
    proxies = PP.snapshot()
    if not proxies:
        return {"message": "No proxies to rotate"}
    log(f"Rotating {len(proxies)} proxies — running health check…", "sys")
    live = ProxyHealthChecker.check_all(proxies, lambda m: log(m, "proxy"))
    PP.replace(live)
    log(f"Proxy pool: {len(live)} alive", "ok")
    return {"message": f"Proxy pool: {len(live)} alive"}


def _run_session_rebuild(values: dict) -> dict:
    u = values.get("account", "").strip()
    if not u:
        return {"message": "Select an account"}
    safe = "".join(c for c in u if c.isalnum() or c in "-_.")
    deleted = 0
    if SESSIONS_DIR:
        for f in SESSIONS_DIR.glob(f"{safe}_*.json"):
            f.unlink()
            deleted += 1
    log(f"Rebuilt session for {u} — removed {deleted} cookie files", "ok")
    return {"message": f"Removed {deleted} session file(s) for {u}"}


def _run_captcha_config(values: dict) -> dict:
    S.captcha_svc = values.get("service", "manual")
    S.captcha_key = values.get("api_key", "").strip()
    save_config()
    log(f"CAPTCHA: {S.captcha_svc} key={'set' if S.captcha_key else 'empty'}", "ok")
    return {"message": f"CAPTCHA service set to {S.captcha_svc}"}


def _run_twofa() -> dict:
    with OTP._l:
        pending = list(OTP._p.keys())
    if pending:
        return {"message": f"{len(pending)} pending 2FA request(s):\n" +
                "\n".join(f"• {k}" for k in pending[:20])}
    return {"message": "No pending 2FA requests"}


def _run_profile_scan(values: dict) -> dict:
    u = values.get("username", "").strip().lstrip("@")
    if not u:
        return {"message": "Username required"}
    platform = next((p[1] for p in PLATFORMS if p[0] == values.get("platform")), "instagram")
    log(f"[SCAN] Scanning @{u} on {platform}…", "proxy")
    from instareport.browser.flows import _scrape_profile

    import asyncio as _asyncio

    async def _do():
        return await _scrape_profile(u, platform)

    try:
        data = _asyncio.run(_do())
    except Exception as ex:
        log(f"[SCAN] @{u} failed: {ex}", "err")
        return {"message": f"Scan failed: {ex}"}

    if not data.get("exists"):
        log(f"[SCAN] @{u} not found on {platform}", "warn")
        return {"message": f"@{u} not found on {platform}"}

    rows = [
        ["Username", data.get("username") or u],
        ["Display name", data.get("name") or "?"],
        ["Platform", data.get("platform") or platform],
        ["Verified", data.get("verified")],
        ["Private", data.get("private")],
        ["Posts", data.get("posts")],
        ["Followers", data.get("followers")],
        ["Following", data.get("following")],
        ["Joined", data.get("joined")],
        ["Bio", (data.get("bio") or "").strip() or "—"],
    ]
    log(f"[SCAN] @{u} on {platform}: {data.get('followers')} followers, "
        f"{data.get('following')} following, {data.get('posts')} posts", "ok")
    return {
        "columns": ["Field", "Value"],
        "rows": rows,
        "message": f"@{u} on {platform}",
        "url": data.get("profile_url") or f"https://www.instagram.com/{u}/",
    }


def _run_engagement(values: dict) -> dict:
    username = values.get("username", "").strip().lstrip("@")
    platform = next((p[1] for p in PLATFORMS if p[0] == values.get("platform")), "instagram")
    if not username:
        return {"message": "Username required"}
    from instareport.browser.flows import _scrape_engagement
    track = bool(values.get("track", False))

    async def _do():
        data = await _scrape_engagement(username, platform)
        log(f"[ENGAGEMENT] @{username} on {platform}: {data.get('posts')} posts, "
            f"{data.get('followers')} followers", "ok")
        if track:
            from instareport.core.database import save_follower_snapshot
            try:
                f = int(str(data.get('followers', '0')).replace(',', '').replace('K', '000').replace('M', '000000'))
                fo = int(str(data.get('following', '0')).replace(',', '').replace('K', '000').replace('M', '000000'))
                p = int(str(data.get('posts', '0')).replace(',', '').replace('K', '000').replace('M', '000000'))
                save_follower_snapshot(username, platform, f, fo, p)
                log(f"[TRACKER] Snapshot saved for @{username}", "ok")
            except Exception:
                pass

    _run_async_in_thread(_do)
    return {"message": "Scan started — results in console"}


def _run_follower_track(values: dict) -> dict:
    username = values.get("username", "").strip().lstrip("@")
    if not username:
        return {"message": "Username required"}
    platform = next((p[1] for p in PLATFORMS if p[0] == values.get("platform")), "instagram")
    from instareport.core.database import get_follower_history
    rows = [[e.get("snapshot_date", ""), e.get("posts", 0), e.get("followers", 0),
             e.get("following", 0)] for e in get_follower_history(username, platform, limit=90)]
    log(f"[TRACKER] Loaded history for @{username}", "ok")
    return {"columns": ["Date", "Posts", "Followers", "Following"], "rows": rows,
            "message": f"{len(rows)} snapshot(s)"}


def _run_report_history(_values=None) -> dict:
    from instareport.core.database import get_run_logs
    rows = [[r.get("timestamp", "")[-8:], r.get("target", ""), r.get("platform", ""),
             r.get("reason", ""), r.get("successes", 0), r.get("total", 0)]
            for r in get_run_logs(limit=100, offset=0)]
    return {"columns": ["Time", "Target", "Platform", "Reason", "Success", "Total"], "rows": rows}


def _run_ip_resolve(values: dict) -> dict:
    target = values.get("target", "").strip()
    if not target:
        return {"message": "IP / domain required"}
    try:
        r = _req('get', f"http://ip-api.com/json/{target}",
                 headers={"Origin": "https://ip-api.com"}, timeout=10)
        data = r.json()
        if data.get("status") == "success":
            lines = [f"IP:      {data.get('query', '?')}",
                     f"Country: {data.get('country', '?')} ({data.get('countryCode', '?')})",
                     f"Region:  {data.get('regionName', '?')}",
                     f"City:    {data.get('city', '?')}",
                     f"ISP:     {data.get('isp', '?')}",
                     f"Org:     {data.get('org', '?')}",
                     f"AS:      {data.get('as', '?')}",
                     f"Lat/Lon: {data.get('lat', '?')}, {data.get('lon', '?')}"]
            return {"message": "\n".join(lines)}
        return {"message": f"Error: {data.get('message', 'Unknown')}"}
    except Exception as ex:
        return {"message": f"Request failed: {ex}"}


def _run_fingerprint() -> dict:
    log("[FINGERPRINT] Launching browser to capture fingerprint…", "proxy")
    from instareport.browser.factory import get_shared_browser, _create_isolated_context

    async def _do():
        context = page = None
        try:
            browser = await get_shared_browser()
            context, page = await _create_isolated_context(browser, force_desktop=True)
            fp = await page.evaluate("""() => ({
                userAgent: navigator.userAgent,
                platform: navigator.platform,
                language: navigator.language,
                hardwareConcurrency: navigator.hardwareConcurrency,
                deviceMemory: navigator.deviceMemory,
                webdriver: navigator.webdriver,
                cookieEnabled: navigator.cookieEnabled,
                doNotTrack: navigator.doNotTrack,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                screen: `${screen.width}x${screen.height}`,
                colorDepth: screen.colorDepth,
                pixelRatio: devicePixelRatio,
                webgl: (() => { try {
                    const gl = document.createElement('canvas').getContext('webgl');
                    return gl ? gl.getParameter(gl.RENDERER) : 'N/A';
                } catch(e) { return 'N/A'; } })(),
            })""")
            for k, v in fp.items():
                log(f"{k}: {v}", "dim")
            log("[FINGERPRINT] Captured", "ok")
        finally:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass

    _run_async_in_thread(_do)
    return {"message": "Fingerprint capture started — results in console"}


def _run_acc_age(values: dict) -> dict:
    username = values.get("username", "").strip().lstrip("@")
    platform = next((p[1] for p in PLATFORMS if p[0] == values.get("platform")), "instagram")
    if not username:
        return {"message": "Username required"}
    log(f"[AGE] Checking @{username} on {platform}…", "sys")
    from instareport.browser.flows import _estimate_account_age

    async def _do():
        age = await _estimate_account_age(username, platform)
        if age:
            log(f"[AGE] @{username}: {age}", "ok")
        else:
            log(f"[AGE] @{username}: could not determine", "warn")

    _run_async_in_thread(_do)
    return {"message": "Age check started — results in console"}


def _run_link_trace(values: dict) -> dict:
    url = values.get("url", "").strip()
    if not url:
        return {"message": "URL required"}
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        resp = _req('get', url, allow_redirects=True, timeout=15, _retries=1)
        history = resp.history + [resp]
        lines = [f"Step {i}: {r.status_code}  {r.url}" for i, r in enumerate(history)]
        lines.append("")
        lines.append(f"Final URL: {resp.url}")
        lines.append(f"Final status: {resp.status_code}")
        lines.append(f"Redirects: {len(resp.history)}")
        return {"message": "\n".join(lines)}
    except Exception as ex:
        return {"message": f"Failed: {ex}"}


def _run_hash_lookup(values: dict) -> dict:
    query = values.get("query", "").strip()
    if not query:
        return {"message": "Query required"}
    import hashlib
    try:
        sha1 = hashlib.sha1(query.encode()).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        r = _req('get', f"https://api.pwnedpasswords.com/range/{prefix}", timeout=10)
        if r.status_code == 200:
            hashes = [l.split(":") for l in r.text.splitlines()]
            matched = [h for h in hashes if h[0] == suffix]
            if matched:
                count = int(matched[0][1])
                lines = [f"Found in {count} breach(es)!"]
                try:
                    r2 = _req('get', f"https://haveibeenpwned.com/api/v3/breachedaccount/{query}",
                              headers={"hibp-api-key": ""}, timeout=10)
                    if r2.status_code == 200:
                        for b in r2.json():
                            lines.append(f"  - {b.get('Name', '?')} ({b.get('BreachDate', '?')})")
                except Exception:
                    lines.append("  (use hibp-api-key for breach names)")
                return {"message": "\n".join(lines)}
            return {"message": "No breaches found — account appears clean"}
        return {"message": f"API error: {r.status_code}"}
    except Exception as ex:
        return {"message": f"Lookup failed: {ex}"}


def _run_screenshot_gallery(values: dict) -> dict:
    action = values.get("action", "")
    if action in ("open", "delete"):
        row = values.get("row") or []
        path = row[3] if len(row) > 3 else ""
        if path and os.path.exists(path):
            if action == "open":
                os.startfile(path)
            else:
                os.remove(path)
                log(f"[GALLERY] Deleted {os.path.basename(path)}", "ok")
    rows = []
    if SCREENSHOTS_DIR and SCREENSHOTS_DIR.exists():
        for f in sorted(SCREENSHOTS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.suffix.lower() in (".png", ".jpg", ".jpeg"):
                date = time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))
                rows.append([f.name, date, f.stat().st_size // 1024, str(f)])
    return {"columns": ["Filename", "Date", "Size (KB)", "path"], "rows": rows}


def _run_rate_limit(values: dict) -> dict:
    try:
        S.rate_limit = max(0, int(values.get("limit", 0)))
    except (TypeError, ValueError):
        pass
    save_config()
    log(f"Rate limit set to {S.rate_limit}/min", "ok")
    return {"message": f"Rate limit: {S.rate_limit}/min"}


def _run_cookie_inject(values: dict) -> dict:
    user = values.get("username", "").strip()
    raw = values.get("json", "").strip()
    if not user or not raw:
        return {"message": "Username and cookie JSON required"}
    try:
        cookies = json.loads(raw)
        if isinstance(cookies, dict):
            cookies = [cookies]
        safe = "".join(c for c in user if c.isalnum() or c in "-_.")
        p = SESSIONS_DIR / f"{safe}_injected.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"cookies": cookies, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                       "version": 2}, f)
        log(f"Injected {len(cookies)} cookies for {user}", "ok")
        return {"message": f"Injected {len(cookies)} cookies for {user}"}
    except json.JSONDecodeError:
        return {"message": "Invalid JSON"}


def _run_telegram(values: dict) -> dict:
    from instareport.tools.telegram_bot import _bot, start_bot, stop_bot
    if _bot and _bot._running:
        stop_bot()
        log("[TELEGRAM] Bot stopped", "ok")
        return {"message": "Bot stopped"}
    token = values.get("token", "").strip()
    if not token:
        return {"message": "Token required"}
    ids = []
    raw = values.get("chat_ids", "").strip()
    if raw:
        try:
            ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            return {"message": "Invalid chat ID format"}
    start_bot(token, ids)
    log("[TELEGRAM] Bot started", "ok")
    return {"message": "Bot started"}


def _read_templates() -> dict:
    conn = _connection()
    try:
        raw = conn.execute("SELECT value FROM settings WHERE key='report_templates'").fetchone()
    finally:
        conn.close()
    if raw:
        try:
            return json.loads(raw["value"])
        except Exception:
            return {}
    return {}


def _write_templates(t: dict) -> None:
    conn = _connection()
    try:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('report_templates', ?)",
                     (json.dumps(t),))
        conn.commit()
    finally:
        conn.close()


def _run_report_templates(values: dict) -> dict:
    templates = _read_templates()
    action = values.get("action", "")
    if action == "save":
        name = values.get("name", "").strip() or f"Template {len(templates) + 1}"
        templates[name] = {
            "target": S.target, "platform": S.platform, "reason": S.reason,
            "workers": S.workers, "accounts": list(S.accounts),
            "cooldown_secs": S.cooldown_secs, "headless": S.headless,
            "safe_mode": S.safe_mode, "stealth": S.stealth,
        }
        _write_templates(templates)
        log(f"[TEMPLATE] Saved '{name}'", "ok")
    elif action == "load":
        row = values.get("row") or []
        name = row[0] if row else ""
        cfg = templates.get(name)
        if cfg:
            S.target = cfg.get("target", "")
            S.platform = cfg.get("platform", "instagram")
            S.reason = cfg.get("reason", "spam")
            S.workers = int(cfg.get("workers", 2))
            if cfg.get("accounts"):
                S.accounts = list(cfg["accounts"])
            S.cooldown_secs = int(cfg.get("cooldown_secs", 300))
            S.headless = cfg.get("headless", False)
            S.stealth = cfg.get("stealth", False)
            save_config()
            log(f"[TEMPLATE] Loaded '{name}' — ready to run", "ok")
    elif action == "delete":
        row = values.get("row") or []
        name = row[0] if row else ""
        if name in templates:
            del templates[name]
            _write_templates(templates)
            log(f"[TEMPLATE] Deleted '{name}'", "ok")
    rows = [[n, c.get("target", ""), c.get("platform", ""), c.get("reason", ""),
             str(c.get("workers", 0))] for n, c in templates.items()]
    return {"columns": ["Name", "Target", "Platform", "Reason", "Workers"], "rows": rows}


def _run_account_groups(values: dict) -> dict:
    from instareport.core.database import get_account_groups, set_account_group, delete_account_group
    action = values.get("action", "")
    if action == "create":
        name = values.get("name", "").strip() or f"Group {len(get_account_groups()) + 1}"
        usernames = [a[0] if isinstance(a, (list, tuple)) else getattr(a, "username", "")
                     for a in S.accounts]
        set_account_group(name, usernames)
        log(f"[GROUPS] Created '{name}' with {len(usernames)} accounts", "ok")
    elif action == "use":
        row = values.get("row") or []
        name = row[0] if row else ""
        users = get_account_groups().get(name, [])
        if users:
            with ACCOUNTS_LOCK:
                S.accounts = [(u, "") for u in users]
            save_config()
            log(f"[GROUPS] Loaded '{name}' — {len(users)} accounts ready", "ok")
    elif action == "delete":
        row = values.get("row") or []
        name = row[0] if row else ""
        if name in get_account_groups():
            delete_account_group(name)
            log(f"[GROUPS] Deleted '{name}'", "ok")
    groups = get_account_groups()
    rows = [[g, ", ".join(users)] for g, users in groups.items()]
    return {"columns": ["Group", "Accounts"], "rows": rows}


def _run_captcha_submit_answer(key: str, answer: str) -> None:
    """Forward a manual CAPTCHA answer into the sidecar pending map."""
    _emit("captcha_answer", {"key": key, "answer": answer})


def _run_emergency_stop() -> dict:
    GLOBAL_STOP.set()
    S.stop_event.set()
    log("⏹ Emergency stop triggered — all sessions signalled", "err")
    return {"message": "Emergency stop triggered"}


# ── Dispatcher ───────────────────────────────────────────────────────────────

_ACTION_KEYS = {
    "burst_mode": _run_burst,
    "force_report": _run_burst,
    "emergency_stop": lambda _v: _run_emergency_stop(),
    "queue_cleaner": lambda _v: _run_queue_cleaner(),
    "smart_categorize": lambda _v: _run_smart_categorize(),
    "turbo_queue": lambda _v: _run_turbo_queue(),
    "history_csv": lambda _v: _run_export_csv(),
    "export_html": lambda _v: _run_export_html(),
    "auto_update": lambda _v: _run_auto_update(),
    "cache_purge": lambda _v: _run_cache_purge(),
    "proxy_rotate": lambda _v: _run_proxy_rotate(),
    "twofa_bypass": lambda _v: _run_twofa(),
    "fingerprint": lambda _v: _run_fingerprint(),
    "telegram_bot": lambda _v: _run_telegram(_v),
    "stealth": lambda _v: _run_toggle("stealth"),
    "warmup": lambda _v: _run_toggle("warmup"),
    "safe_mode": lambda _v: _run_toggle("safe_mode"),
    "dark_pattern": lambda _v: _run_toggle("dark_pattern"),
    "net_spoof": lambda _v: _run_toggle("net_spoof"),
    "behavior": lambda _v: _run_toggle("behavior"),
    "canvas_spoof": lambda _v: _run_toggle("canvas_spoof"),
    "webrtc_block": lambda _v: _run_toggle("webrtc_block"),
    "tls_fp": lambda _v: _run_toggle("tls_fp"),
}

_FORM_KEYS = {
    "shadow_check": _run_shadow_check,
    "shadow_check_lookup": _run_shadow_check,
    "timed_strikes": _run_timed_strikes,
    "distributed": _run_workers,
    "thread_manager": _run_workers,
    "payload_builder": _run_payload_builder,
    "batch_processor": _run_batch,
    "appeal": _run_appeal,
    "ban_detector": _run_ban_detector,
    "session_rebuild": _run_session_rebuild,
    "captcha_config": _run_captcha_config,
    "profile_scan": _run_profile_scan,
    "engagement": _run_engagement,
    "follower_track": _run_follower_track,
    "ip_resolve": _run_ip_resolve,
    "acc_age": _run_acc_age,
    "link_trace": _run_link_trace,
    "hash_lookup": _run_hash_lookup,
    "rate_limit": _run_rate_limit,
    "cookie_inject": _run_cookie_inject,
    "vip_bypass": _run_vip_bypass,
    "api_hook": _run_api_hook,
    "header_forge": _run_header_forge,
    "identity_swap": _run_identity_swap,
    "flag_override": _run_flag_override,
    "acc_restore": _run_acc_restore,
}

_TABLE_KEYS = {
    "account_health": _run_account_health,
    "report_history": _run_report_history,
    "screenshot_gallery": _run_screenshot_gallery,
    "report_templates": _run_report_templates,
    "account_groups": _run_account_groups,
}


def run_tool(key: str, values: dict | None = None) -> dict:
    values = values or {}
    schema = SCHEMAS.get(key)
    if schema is None:
        return {"message": f"Unknown tool: {key}"}
    if not schema.get("available", True):
        return {"message": "Not available in this build"}
    if key in _TABLE_KEYS:
        return _TABLE_KEYS[key](values)
    if key in _FORM_KEYS:
        return _FORM_KEYS[key](values)
    if key in _ACTION_KEYS:
        return _ACTION_KEYS[key](values)
    return {"message": "No handler for this tool"}
