<div align="center">

# 📝 Changelog

### InstaReport — Release History

[← Back to README](README.md) &nbsp;·&nbsp; [Online Changelog](https://iescly.duckdns.org/changelog)

</div>

---

## [9.0.4] - 2026-10-20

### 🍎 macOS Build (Apple Silicon)

- **Python backend restored on macOS** — the macOS bundle no longer strips `externalBin`/`resources`, so the DMG now ships the `sidecar-bridge` binary and the Playwright `browsers` folder. The app no longer fails with "Backend failed to start" / "The sidecar was not found"
- **Fixed sidecar launch under hardened runtime** — ad-hoc signing with hardened runtime (`adhoc,runtime`) made PyInstaller's onefile bootloader fail to `dlopen` the extracted Python with a "different Team IDs" error, which the app silently swallowed. The macOS build is now ad-hoc signed **without** hardened runtime, so the sidecar loads reliably without notarization
- **Fixed frozen path resolution** — `sidecar_bridge.py` `_proxy_path()` called `os.path.join(REPO, ...)` with `REPO = None` in frozen builds, raising `TypeError: expected str, bytes or os.PathLike object, not NoneType` during bootstrap. Relative paths are now resolved against the engine data dir when frozen
- **Sidecar now built in CI** — `build-macos.yml` sets up Python, checks out the engine and builds the `aarch64-apple-darwin` sidecar before the Tauri build, instead of shipping a DMG with no backend
- **Portable sidecar packaging** — the hardcoded `C:\Users\...` paths in `sidecar_bridge.py`, `sidecar-bridge.spec` and `tools.py` (`_export_path`) are removed; the engine root is resolved from `INSTAREPORT_ROOT` or sibling layouts and the whole `instareport` package is bundled into the frozen binary
- **New `sidecar/build_sidecar.py`** — a single command installs deps, downloads the platform Chromium, runs PyInstaller and places `sidecar-bridge-<triple>` into `src-tauri/binaries/`

> Windows and Linux remain on **9.0.3**, which is stable — this release only ships the fixed **macOS** DMG (`InstaReport_9.0.4_aarch64.dmg`).

## [9.0.2] - 2026-09-13

### Bug Fixes

- **Sidecar dead-pipe fix** - if the built-in engine sidecar process dies or its IPC pipe closes mid-session ("os error 232 / Activation error: sidecar write failed"), the Tauri bridge now detects the dead sidecar, automatically respawns it, and retries the pending request. No more stuck activation or frozen tools
- **Linux build fix** - explicit type annotation in sidecar.rs so the Linux release compiles cleanly

## [9.0.1] - 2026-08-16

### ?? Bug Fixes

- **Profile Scanner fully functional** - the Lookup tab previously showed no results; it now returns display name, bio, verified/private status, posts, followers, following and join date
- **Fixed browser context error** - an `accept_language` TypeError broke profile scanning, engagement and other lookup tools whenever TLS Fingerprinting was enabled
- **Linux browser alignment** - bundled Chromium now matches the engine (chromium-1134)
## [9.0.0] — 2026-08-14

### 🚀 New Release

- **All 12 previously-stubbed tools fully implemented** — VIP Bypass, API Hookpoint, Identity Swap, Flag Override, Account Restore, Dark Pattern, Network Spoof, Behavior Mimic, Header Forge, Canvas Spoof, WebRTC Block, TLS Fingerprint
- **New desktop UI** — Tauri 2 + React 19 shell with a Python sidecar engine
- **Self-contained Windows installer** — Playwright Chromium bundled, no Python/browser install needed (~228 MB)
- **Self-signed code signing** — signature (CN=InstaReport); SmartScreen may still warn

## [8.7.5] — 2026-08-08

### 🔧 Improvements

- **Linux notify-send guard** — desktop notifications check `shutil.which("notify-send")` first and skip gracefully on minimal distros instead of failing silently
- **Portable shebang** — `main.py` uses `#!/usr/bin/env python3`, so `./main.py` works on any Linux box regardless of Python install path
- **Dockerfile** — added `libnotify-bin` for notify support inside containers
- **Distribution sync** — desktop build brought to full parity with the v8.7.5 distribution tree (API server, split dialogs, cross-platform fonts)

## [8.7.0] — 2026-07-07

### 🚀 New Features

- **Randomized Action Delays** — all timing constants (`T_PAGE_LOAD`, `T_POST_CLICK`, etc.) now apply ±30% jitter automatically to mimic human behavior and avoid detection patterns
- **Exponential Backoff on Retry** — account retries now use `min(10 × 2^attempt, 300s)` + random jitter instead of linear 5s steps, greatly improving success rate under rate limits
- **Account Health Pre-Check** — before each campaign run, every account is tested for a valid login session. Dead accounts are skipped automatically
- **Bulk Target Import** — new "📂 Import .txt" button in the Batch Processor dialog loads targets from a file (one per line, `#` for comments)
- **Auto-Update Check** — on startup, the app checks GitHub for new releases. If a newer version is found, a dialog offers to open the download page
- **Campaign Resume Support** — campaign progress (targets completed, success count) is saved to SQLite. Infrastructure ready for a "Resume" button in a future release

### 🐛 Bug Fixes

- **Nuitka Frozen Loop** — infinite "Missing Dependencies" popup when running Nuitka-compiled binary fixed by adding `if not getattr(sys, 'frozen', False)` guard and static imports
- **Constants `import sys`** — `constants.py` now explicitly imports `sys` for `_get_data_dir()`, fixing crash when run as frozen binary
- **Dep Check Loop** — `main.py` no longer attempts `sys.executable -m pip` when compiled (binary has no pip), preventing hang
- **Version Sync** — `__init__.py` and `constants.py` now report the same version number

### 🔧 Improvements

- Auto `.venv` creation on first run — no system Python pollution
- `--no-dep-check` flag to skip dependency verification entirely
- `run.bat` / `run.sh` now prefer `.venv` Python when available, skipping re-exec overhead
- All module-based sleeps (`T_PAGE_LOAD`, `T_POST_CLICK`, `T_POST_LOGIN`, `T_REFRESH_WAIT`, `T_TYPE_DELAY`, `T_TELEGRAM_OTP`) now routed through `_delay()` with jitter

## [8.6.8] — 2026-06-13

### 🐛 Bug Fixes

- Dialogs split into `dialogs_basic.py`, `dialogs_pro.py`, `dialogs_misc.py` (73 functions organized)
- API base URL updated to `iescly.duckdns.org`

## [8.6.5-PRESTIGE] — Initial Release
