"""InstaReport sidecar bridge — JSON-RPC over stdio between the Tauri shell
and the existing Python backend (instareport package).

Protocol (one JSON object per line, newline-delimited):
  Request :  {"id": int, "method": str, "params": {...}}
  Response:  {"type":"response","id":int,"ok":bool,"data":...|"error":str}
  Event   :  {"type":"event","name":str,"data":...}

Dev launch:  python sidecar\\sidecar_bridge.py   (INSTAREPORT_ROOT env or
the repo path below is used to import the instareport package).
"""
import json
import os
import sys
import threading
import traceback

REPO = os.environ.get(
    "INSTAREPORT_ROOT",
    r"C:\Users\azziz\Downloads\Compressed\InstaReport_v8.7.5",
)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

for _stream in (sys.stdin, sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _resolve_browsers_dir() -> str | None:
    """Locate the bundled Playwright browser cache so the engine never depends
    on a per-user ms-playwright install. Overrides win; otherwise look beside
    the sidecar script (dev) or the sidecar binary (bundled install)."""
    for _key in ("INSTAREPORT_BROWSERS_DIR", "PLAYWRIGHT_BROWSERS_PATH"):
        _val = os.environ.get(_key)
        if _val and os.path.isdir(_val):
            return _val
    if getattr(sys, "frozen", False):
        _base = os.path.dirname(sys.executable)
    else:
        _base = os.path.dirname(os.path.abspath(__file__))
    _candidates = [os.path.join(_base, "browsers")]
    if os.path.dirname(_base) != _base:
        _candidates.append(os.path.join(os.path.dirname(_base), "browsers"))
    _candidates.append(os.path.join(os.getcwd(), "browsers"))
    for _c in _candidates:
        if os.path.isdir(_c):
            return _c
    return None


_br_dir = _resolve_browsers_dir()
if _br_dir:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _br_dir

# ── Early init (paths first, then persistence + config) ─────────────────────
from instareport.utils.constants import (  # noqa: E402
    VERSION, PLATFORMS, REPORT_REASONS, MODULES, TABS, init_paths,
)
init_paths()
from instareport.utils.logging import init_file_logger, log, dlog  # noqa: E402
init_file_logger()

_out_lock = threading.Lock()


def _emit(name: str, data) -> None:
    with _out_lock:
        sys.stdout.write(json.dumps(
            {"type": "event", "name": name, "data": data},
            ensure_ascii=False,
        ) + "\n")
        sys.stdout.flush()


def _respond(rid, ok: bool, data=None, error: str | None = None) -> None:
    with _out_lock:
        sys.stdout.write(json.dumps(
            {"type": "response", "id": rid, "ok": ok,
             "data": data, "error": error},
            ensure_ascii=False,
        ) + "\n")
        sys.stdout.flush()


def _log_cb(msg: str, tag: str = "dim") -> None:
    _emit("log", {"msg": str(msg), "tag": tag})


def _otp_cb(key: str, plat: str, user: str) -> None:
    _emit("otp", {"key": key, "platform": plat, "user": user})


_captcha_pending: dict[str, dict] = {}
_captcha_lock = threading.Lock()


def _captcha_cb(key: str, cap_type: str, page_url: str) -> str:
    evt = threading.Event()
    with _captcha_lock:
        _captcha_pending[key] = {"event": evt, "answer": ""}
    _emit("captcha", {"key": key, "type": cap_type, "url": page_url})
    evt.wait(timeout=120)
    with _captcha_lock:
        entry = _captcha_pending.pop(key, None)
    return entry["answer"] if entry else ""


from instareport.core.state import S, GLOBAL_STOP, ACCOUNTS_LOCK  # noqa: E402
S.log_cb = _log_cb
S.otp_cb = _otp_cb
S.captcha_cb = _captcha_cb

from instareport.core.database import (  # noqa: E402
    setup_persistence, get_run_logs, get_run_logs_count,
)
from instareport.core.config import save_config  # noqa: E402
from instareport.core.license import LS  # noqa: E402
from instareport.core.otp import OTP  # noqa: E402
from instareport.tools.proxy import PP  # noqa: E402
from instareport.engine import run_mass_report, start_scheduler, stop_scheduler  # noqa: E402

setup_persistence()
start_scheduler(S.sched_interval)


def _proxy_path() -> str:
    pf = S.proxy_file
    return pf if os.path.isabs(pf) else os.path.join(REPO, pf)


def _stats() -> dict:
    from instareport.core.database import _connection
    conn = _connection()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(total),0), COALESCE(SUM(successes),0) FROM run_logs"
        ).fetchone()
        return {"total": row[0], "successes": row[1]}
    finally:
        conn.close()


def _watch_run(th: threading.Thread) -> None:
    th.join()
    _emit("status", {"state": "idle"})
    _emit("stats", _stats())


# ── Command handlers ─────────────────────────────────────────────────────────

def _bootstrap() -> dict:
    from instareport.plugins.loader import discover_plugins, get_all_plugins
    discover_plugins()
    PP.load(_proxy_path())
    ok, code, msg = LS.load()
    plugins = [{
        "name": p.display_name,
        "key": p.platform_key,
        "enabled": bool(p.enabled),
        "version": getattr(p, "version", ""),
        "description": p.description,
    } for p in get_all_plugins()]
    return {
        "version": VERSION,
        "tabs": [[name, count] for name, count in TABS],
        "modules": {k: [list(x) for x in v] for k, v in MODULES.items()},
        "platforms": PLATFORMS,
        "reasons": REPORT_REASONS,
        "config": {
            "target": S.target,
            "workers": S.workers,
            "platform": S.platform,
            "reason": S.reason,
            "headless": S.headless,
            "api_mode": S.api_mode,
            "cooldown_secs": S.cooldown_secs,
            "favorites": sorted(S.favorites),
            "sched_enabled": S.sched_enabled,
            "sched_time": S.sched_time,
            "sched_interval": S.sched_interval,
        },
        "accounts": [{"user": u, "pass": p} for u, p in S.accounts],
        "proxies_count": PP.count(),
        "license": {"ok": ok, "code": code, "msg": msg},
        "plugins": plugins,
        "stats": _stats(),
    }


def _start_run(target: str, platform: str, reason: str, workers: int) -> dict:
    S.target = target
    S.platform = platform
    S.reason = reason
    S.workers = max(1, min(16, int(workers)))
    th = run_mass_report(target, platform, reason, _log_cb)
    threading.Thread(target=_watch_run, args=(th,), daemon=True).start()
    return {"started": True}


def _stop_run() -> dict:
    GLOBAL_STOP.set()
    S.stop_event.set()
    return {"stopped": True}


def _history(page: int, size: int, date_from: str = "",
             date_to: str = "", search: str = "") -> dict:
    rows = get_run_logs(limit=size, offset=page * size,
                        date_from=date_from, date_to=date_to, search=search)
    total = get_run_logs_count(date_from=date_from, date_to=date_to, search=search)
    return {"rows": rows, "total": total}


def _clear_history() -> dict:
    from instareport.core.database import _connection
    conn = _connection()
    try:
        conn.execute("DELETE FROM run_logs")
        conn.commit()
    finally:
        conn.close()
    S.run_logs.clear()
    return {"cleared": True}


def _save_accounts(accounts: list[dict]) -> dict:
    cleaned = [(a["user"], a["pass"]) for a in accounts if a.get("user")]
    with ACCOUNTS_LOCK:
        S.accounts = cleaned
    save_config()
    _log_cb(f"Accounts saved: {len(cleaned)}", "ok")
    return {"count": len(cleaned)}


def _proxy_refresh() -> dict:
    n = PP.load(_proxy_path())
    _log_cb(f"Proxies loaded: {n}", "ok")
    return {"count": n}


def _license_activate(code: str) -> dict:
    ok, msg = LS.validate(code)
    if ok:
        LS.save(code)
        _log_cb("License activated", "ok")
    return {"ok": ok, "msg": msg}


def _plugin_toggle(key: str, enabled: bool) -> dict:
    from instareport.plugins.loader import set_plugin_enabled, get_plugin
    set_plugin_enabled(key, bool(enabled))
    p = get_plugin(key)
    _log_cb(f"Plugin '{p.display_name if p else key}' "
            f"{'enabled' if enabled else 'disabled'}", "ok")
    return {"ok": True}


def _plugins_refresh() -> dict:
    from instareport.plugins.loader import discover_plugins, get_all_plugins
    discover_plugins()
    plugins = [{
        "name": p.display_name,
        "key": p.platform_key,
        "enabled": bool(p.enabled),
        "version": getattr(p, "version", ""),
        "description": p.description,
    } for p in get_all_plugins()]
    _log_cb(f"Plugins refreshed: {len(plugins)} total", "ok")
    return {"plugins": plugins}


def _favorite_toggle(key: str) -> dict:
    if key in S.favorites:
        S.favorites.discard(key)
    else:
        S.favorites.add(key)
    save_config()
    _log_cb(f"{'★' if key in S.favorites else '☆'} {key}", "ok")
    return {"favorite": key in S.favorites, "favorites": sorted(S.favorites)}


def _otp_submit(key: str, code: str) -> dict:
    OTP.submit(key, code)
    return {"submitted": True}


def _captcha_submit(key: str, answer: str) -> dict:
    with _captcha_lock:
        entry = _captcha_pending.get(key)
        if entry:
            entry["answer"] = answer
            entry["event"].set()
    return {"submitted": True}


def _set_target(target: str) -> dict:
    S.target = target
    return {"target": S.target}


def _set_workers(workers: int) -> dict:
    S.workers = max(1, min(16, int(workers)))
    return {"workers": S.workers}


def _save_config() -> dict:
    save_config()
    return {"saved": True}


def _tool_schema(key: str) -> dict:
    schema = tools.get_schema(key)
    if schema is None:
        raise ValueError(f"unknown tool: {key}")
    return schema


def _tool_run(key: str, values: dict | None = None) -> dict:
    return tools.run_tool(key, values or {})


def _shutdown() -> dict:
    stop_scheduler()
    save_config()
    return {"bye": True}


HANDLERS = {
    "bootstrap": _bootstrap,
    "start_run": _start_run,
    "stop_run": _stop_run,
    "history": _history,
    "clear_history": _clear_history,
    "save_accounts": _save_accounts,
    "proxy_refresh": _proxy_refresh,
    "license_activate": _license_activate,
    "plugin_toggle": _plugin_toggle,
    "plugins_refresh": _plugins_refresh,
    "favorite_toggle": _favorite_toggle,
    "otp_submit": _otp_submit,
    "captcha_submit": _captcha_submit,
    "set_target": _set_target,
    "set_workers": _set_workers,
    "save_config": _save_config,
    "tool_schema": _tool_schema,
    "tool_run": _tool_run,
    "shutdown": _shutdown,
}


import tools  # noqa: E402

tools.configure(_emit, _stats, _start_run)


def main() -> None:
    log("Sidecar ready", "ok")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        rid = req.get("id")
        name = req.get("method")
        params = req.get("params") or {}
        try:
            handler = HANDLERS.get(name)
            if handler is None:
                _respond(rid, False, error=f"unknown method: {name}")
                continue
            result = handler(**params) if isinstance(params, dict) else handler(*params)
            _respond(rid, True, result)
        except Exception as e:
            _respond(rid, False, error=f"{type(e).__name__}: {e}")
            dlog(traceback.format_exc())
    stop_scheduler()
    save_config()


if __name__ == "__main__":
    main()
