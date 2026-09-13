use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{channel, Sender};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter};

/// One JSON frame on the wire (response or event from the sidecar).
#[derive(Debug, Clone, Serialize, Deserialize)]
struct Wire {
    #[serde(rename = "type")]
    kind: String,
    id: Option<i64>,
    name: Option<String>,
    ok: Option<bool>,
    data: Option<Value>,
    error: Option<String>,
}

struct BridgeInner {
    child: Mutex<Option<Child>>,
    stdin: Mutex<Option<ChildStdin>>,
    stdout: Mutex<Option<BufReader<ChildStdout>>>,
    next_id: Mutex<i64>,
    pending: Mutex<HashMap<i64, Sender<Result<Value, String>>>>,
    alive: AtomicBool,
    shutdown_flag: AtomicBool,
}

#[derive(Clone)]
pub struct BridgeState {
    inner: Arc<BridgeInner>,
    spawn_cmd: Arc<Mutex<Option<(String, Vec<String>)>>>,
    respawn_lock: Arc<Mutex<()>>,
    app_handle: Arc<Mutex<Option<AppHandle>>>,
}

/// Ordered candidates for launching the Python sidecar: explicit override,
/// PATH-resolvable `python`/`py`, then common absolute install locations.
fn python_candidates(script: &str) -> Vec<(String, Vec<String>)> {
    use std::path::Path;

    let mut out: Vec<(String, Vec<String>)> = Vec::new();
    if let Ok(c) = std::env::var("INSTAREPORT_SIDECAR_CMD") {
        out.push((c, vec![script.to_string()]));
    }
    out.push(("python".to_string(), vec![script.to_string()]));
    out.push(("python3".to_string(), vec![script.to_string()]));
    out.push(("py".to_string(), vec!["-3".to_string(), script.to_string()]));

    let mut roots = Vec::new();
    #[cfg(target_os = "windows")]
    {
        if let Ok(d) = std::env::var("LOCALAPPDATA") {
            roots.push(Path::new(&d).join("Programs").join("Python"));
        }
        for key in ["ProgramFiles", "ProgramFiles(x86)"] {
            if let Ok(d) = std::env::var(key) {
                roots.push(Path::new(&d).join("Python"));
            }
        }
    }
    #[cfg(target_os = "macos")]
    {
        let home = std::env::var("HOME").unwrap_or_default();
        let home_path = Path::new(&home);
        roots.push(home_path.join(".pyenv").join("versions"));
        roots.push(Path::new("/opt/homebrew/bin").to_path_buf());
        roots.push(Path::new("/usr/local/bin").to_path_buf());
    }
    for root in roots {
        let Ok(entries) = std::fs::read_dir(&root) else {
            continue;
        };
        let mut dirs: Vec<_> = entries.flatten().map(|e| e.path()).collect();
        dirs.sort_by_key(|p| p.file_name().map(|n| n.to_owned()).unwrap_or_default());
        for p in dirs.iter().rev() {
            #[cfg(target_os = "windows")]
            let exe = p.join("python.exe");
            #[cfg(not(target_os = "windows"))]
            let exe = p.join("python3");
            if exe.is_file() {
                out.push((exe.to_string_lossy().into_owned(), vec![script.to_string()]));
            }
        }
    }
    out
}

/// Locate a bundled sidecar binary (PyInstaller onefile). Tauri places
/// external binaries next to the app exe; also check common resource dirs.
fn resolve_bundled_exe() -> Option<String> {
    use std::path::Path;

    if let Ok(e) = std::env::var("INSTAREPORT_SIDECAR_EXE") {
        if Path::new(&e).is_file() {
            return Some(e);
        }
    }
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    #[cfg(target_os = "windows")]
    let name = "sidecar-bridge.exe";
    #[cfg(not(target_os = "windows"))]
    let name = "sidecar-bridge";
    let mut candidates = vec![dir.join(name)];
    for extra in ["resources", "_up_/resources", "_up_"] {
        candidates.push(dir.join(extra).join(name));
    }
    candidates
        .into_iter()
        .find(|c| c.is_file())
        .map(|c| c.to_string_lossy().into_owned())
}

/// Locate the bridge script: explicit override first, then common relative
/// layouts (project root from CWD, from `src-tauri`, and from the exe dir).
fn resolve_script() -> Option<String> {
    use std::path::Path;

    if let Ok(s) = std::env::var("INSTAREPORT_SIDECAR_SCRIPT") {
        if Path::new(&s).exists() {
            return Some(s);
        }
    }
    let relative = "sidecar/sidecar_bridge.py";
    let mut candidates = vec![relative.to_string(), format!("../{relative}")];
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            candidates.push(format!("{}/../../{relative}", dir.display()));
            candidates.push(format!("{}/../../../{relative}", dir.display()));
        }
    }
    candidates.into_iter().find(|c| Path::new(c).exists())
}

/// Build a BridgeState around an already-spawned child process.
fn build_state(
    mut child: Child,
    cmd: (String, Vec<String>),
) -> Result<BridgeState, String> {
    let stdin = child.stdin.take().ok_or("sidecar stdin unavailable")?;
    let stdout = child.stdout.take().ok_or("sidecar stdout unavailable")?;
    let stderr = child.stderr.take().ok_or("sidecar stderr unavailable")?;

    // Drain stderr so the child never blocks on a full pipe.
    std::thread::spawn(move || {
        for line in BufReader::new(stderr).lines() {
            if let Ok(line) = line {
                eprintln!("[sidecar] {line}");
            }
        }
    });

    Ok(BridgeState {
        inner: Arc::new(BridgeInner {
            child: Mutex::new(Some(child)),
            stdin: Mutex::new(Some(stdin)),
            stdout: Mutex::new(Some(BufReader::new(stdout))),
            next_id: Mutex::new(0),
            pending: Mutex::new(HashMap::new()),
            alive: AtomicBool::new(true),
            shutdown_flag: AtomicBool::new(false),
        }),
        spawn_cmd: Arc::new(Mutex::new(Some(cmd))),
        respawn_lock: Arc::new(Mutex::new(())),
        app_handle: Arc::new(Mutex::new(None)),
    })
}

impl BridgeState {
    pub fn spawn() -> Result<Self, String> {
        // Prefer a bundled sidecar binary (production installs).
        if let Some(exe) = resolve_bundled_exe() {
            let args: Vec<String> = vec![];
            match Command::new(&exe)
                .args(&args)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
            {
                Ok(child) => return build_state(child, (exe, args)),
                Err(e) => {
                    eprintln!("bundled sidecar '{exe}' failed to spawn: {e}");
                }
            }
        }

        let script = resolve_script().ok_or_else(|| {
            "failed to locate sidecar/sidecar_bridge.py (set INSTAREPORT_SIDECAR_SCRIPT)".to_string()
        })?;

        let mut last_err = "no python interpreter candidates".to_string();
        for (prog, args) in python_candidates(&script) {
            let mut cmd = Command::new(&prog);
            cmd.args(&args)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped());
            let child = match cmd.spawn() {
                Ok(child) => child,
                Err(e) => {
                    last_err = format!("'{prog}': {e}");
                    continue;
                }
            };
            return build_state(child, (prog, args));
        }
        Err(format!("failed to start Python sidecar ({last_err})"))
    }

    pub fn start_reader(&self, app: AppHandle) {
        *self.app_handle.lock().unwrap() = Some(app.clone());
        self.spawn_reader(Some(app));
    }

    fn spawn_reader(&self, app: Option<AppHandle>) {
        let inner = self.inner.clone();
        std::thread::spawn(move || {
            loop {
                let mut line = String::new();
                let n = {
                    let mut stdout_lock = match inner.stdout.lock() {
                        Ok(g) => g,
                        Err(_) => return,
                    };
                    let stdout = match stdout_lock.as_mut() {
                        Some(s) => s,
                        None => return,
                    };
                    match stdout.read_line(&mut line) {
                        Ok(0) => {
                            inner.alive.store(false, Ordering::SeqCst);
                            return;
                        }
                        Ok(_) => line,
                        Err(_) => {
                            inner.alive.store(false, Ordering::SeqCst);
                            return;
                        }
                    }
                };
                let wire: Wire = match serde_json::from_str(n.trim_end()) {
                    Ok(w) => w,
                    Err(_) => continue,
                };
                if wire.kind == "event" {
                    if let Some(app) = &app {
                        let _ = app.emit("sidecar", wire);
                    }
                    continue;
                }
                if let Some(id) = wire.id {
                    if let Some(tx) = inner.pending.lock().unwrap().remove(&id) {
                        let result = if wire.ok.unwrap_or(false) {
                            Ok(wire.data.unwrap_or(Value::Null))
                        } else {
                            Err(wire.error.unwrap_or_else(|| "sidecar error".into()))
                        };
                        let _ = tx.send(result);
                    }
                }
            }
        });
    }

    pub fn call(&self, method: &str, params: Value) -> Result<Value, String> {
        self.call_inner(method, params, 0)
    }

    fn call_inner(&self, method: &str, params: Value, depth: u32) -> Result<Value, String> {
        if depth > 2 {
            return Err("sidecar call failed after retries".to_string());
        }

        let id = {
            let mut n = self.inner.next_id.lock().unwrap();
            *n += 1;
            *n
        };
        let (tx, rx) = channel();
        self.inner.pending.lock().unwrap().insert(id, tx);
        let req = json!({ "id": id, "method": method, "params": params });

        {
            let mut stdin_opt = self.inner.stdin.lock().unwrap();
            match stdin_opt.as_mut() {
                Some(s) => {
                    if let Err(e) = writeln!(s, "{req}").and_then(|_| s.flush()) {
                        drop(stdin_opt);
                        self.inner.pending.lock().unwrap().remove(&id);
                        if e.kind() == std::io::ErrorKind::BrokenPipe
                            || !self.inner.alive.load(Ordering::SeqCst)
                        {
                            self.respawn()?;
                            return self.call_inner(method, params, depth + 1);
                        }
                        return Err(format!("sidecar write failed: {e}"));
                    }
                }
                None => {
                    drop(stdin_opt);
                    self.inner.pending.lock().unwrap().remove(&id);
                    self.respawn()?;
                    return self.call_inner(method, params, depth + 1);
                }
            }
        }

        match rx.recv_timeout(Duration::from_secs(120)) {
            Ok(result) => result,
            Err(_) => {
                self.inner.pending.lock().unwrap().remove(&id);
                if !self.inner.alive.load(Ordering::SeqCst) {
                    self.respawn()?;
                    return self.call_inner(method, params, depth + 1);
                }
                Err("sidecar call timed out".to_string())
            }
        }
    }

    fn respawn(&self) -> Result<(), String> {
        if self.inner.shutdown_flag.load(Ordering::SeqCst) {
            return Err("sidecar is shutting down".to_string());
        }

        let _guard = self.respawn_lock.lock().unwrap();

        if self.inner.alive.load(Ordering::SeqCst) {
            return Ok(());
        }
        if self.inner.shutdown_flag.load(Ordering::SeqCst) {
            return Err("sidecar is shutting down".to_string());
        }

        eprintln!("[sidecar-bridge] respawning sidecar...");

        if let Some(mut child) = self.inner.child.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        *self.inner.stdin.lock().unwrap() = None;
        *self.inner.stdout.lock().unwrap() = None;

        let (exe, args) = self
            .spawn_cmd
            .lock()
            .unwrap()
            .clone()
            .ok_or_else(|| "no spawn command stored".to_string())?;

        let mut cmd = Command::new(&exe);
        cmd.args(&args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("sidecar respawn failed: {e}"))?;

        let stdin = child
            .stdin
            .take()
            .ok_or("sidecar respawn: stdin unavailable")?;
        let stdout = child
            .stdout
            .take()
            .ok_or("sidecar respawn: stdout unavailable")?;
        let stderr = child
            .stderr
            .take()
            .ok_or("sidecar respawn: stderr unavailable")?;

        std::thread::spawn(move || {
            for line in BufReader::new(stderr).lines() {
                if let Ok(line) = line {
                    eprintln!("[sidecar-respawn] {line}");
                }
            }
        });

        *self.inner.child.lock().unwrap() = Some(child);
        *self.inner.stdin.lock().unwrap() = Some(stdin);
        *self.inner.stdout.lock().unwrap() = Some(BufReader::new(stdout));
        self.inner.alive.store(true, Ordering::SeqCst);

        if let Some(app) = self.app_handle.lock().unwrap().clone() {
            self.spawn_reader(Some(app));
        } else {
            self.spawn_reader(None);
        }

        Ok(())
    }

    pub fn shutdown(&self) {
        self.inner
            .shutdown_flag
            .store(true, Ordering::SeqCst);
        self.inner.alive.store(false, Ordering::SeqCst);

        if let Some(s) = self.inner.stdin.lock().unwrap().as_mut() {
            let req = json!({ "method": "shutdown", "params": {} });
            let _ = writeln!(s, "{req}");
            let _ = s.flush();
        }

        if let Some(mut child) = self.inner.child.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }

    /// CLI self-test (INSTAREPORT_BRIDGE_SELFTEST=1): spawns the real sidecar,
    /// calls `bootstrap`, then force-kills the child and verifies the bridge
    /// auto-respawns and the next call succeeds. Returns a report string.
    pub fn self_test() -> Result<String, String> {
        let bridge = BridgeState::spawn()?;
        bridge.spawn_reader(None);

        let before = bridge
            .call("bootstrap", json!({}))
            .map_err(|e| format!("bootstrap#1 failed: {e}"))?;
        let pid_a = bridge.inner.child.lock().unwrap().as_ref().unwrap().id();
        let ver = before
            .get("version")
            .and_then(|v| v.as_str())
            .unwrap_or("?")
            .to_string();

        #[cfg(target_os = "windows")]
        {
            let kill = Command::new("taskkill")
                .args(["/F", "/T", "/PID", &pid_a.to_string()])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status()
                .map_err(|e| format!("taskkill failed: {e}"))?;
            if !kill.success() {
                return Err(format!("failed to kill sidecar pid {pid_a}"));
            }
        }

        std::thread::sleep(Duration::from_millis(1800));

        let dead_seen = !bridge.inner.alive.load(Ordering::SeqCst);

        let _after = bridge
            .call("bootstrap", json!({}))
            .map_err(|e| format!("bootstrap#2 (after kill) failed: {e}"))?;
        let pid_b = bridge.inner.child.lock().unwrap().as_ref().unwrap().id();
        let alive_after = bridge.inner.alive.load(Ordering::SeqCst);

        drop(bridge);

        let report = format!(
            "SELFTEST OK: pid {pid_a} -> {pid_b} dead_seen={dead_seen} alive_after={alive_after} version={ver}"
        );
        if let Ok(out) = std::env::var("INSTAREPORT_SELFTEST_OUT") {
            let _ = std::fs::write(out, &report);
        }
        Ok(report)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    use std::sync::OnceLock;

    static FAKE_SCRIPT: OnceLock<PathBuf> = OnceLock::new();

    /// Write a fake sidecar script: reads JSON requests on stdin, echoes each
    /// one back as a JSON response on stdout, and dies normally on `shutdown`.
    fn fake_script() -> PathBuf {
        FAKE_SCRIPT
            .get_or_init(|| {
                let dir = std::env::temp_dir().join("opencode");
                std::fs::create_dir_all(&dir).unwrap();
                let path = dir.join("fake_sidecar.py");
                std::fs::write(
                    &path,
                    r#"import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        req = json.loads(line)
    except Exception:
        continue
    if req.get("method") == "shutdown":
        break
    resp = {"type": "response", "id": req.get("id"), "ok": True,
            "data": {"echo": req.get("method")}}
    sys.stdout.write(json.dumps(resp) + "\n")
    sys.stdout.flush()
"#,
                )
                .unwrap();
                path
            })
            .clone()
    }

    #[test]
    fn respawns_after_death() {
        let script = fake_script();

        unsafe {
            std::env::set_var("INSTAREPORT_SIDECAR_SCRIPT", &script);
            std::env::remove_var("INSTAREPORT_SIDECAR_EXE");
            std::env::remove_var("INSTAREPORT_SIDECAR_CMD");
        }

        let bridge = BridgeState::spawn().expect("spawn should succeed");
        bridge.spawn_reader(None);

        let first = bridge
            .call("ping", json!({}))
            .expect("first call should succeed");
        assert_eq!(first["echo"], "ping");

        // Simulate the sidecar dying mid-session (AV kill / crash).
        let pid = {
            let g = bridge.inner.child.lock().unwrap();
            g.as_ref().expect("child exists").id()
        };
        #[cfg(target_os = "windows")]
        {
            let kill = Command::new("taskkill")
                .args(["/F", "/PID", &pid.to_string()])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status()
                .expect("taskkill runs");
            assert!(kill.success(), "should kill the child");
        }

        // Give the reader thread time to notice EOF.
        std::thread::sleep(Duration::from_millis(1500));
        assert!(
            !bridge.inner.alive.load(Ordering::SeqCst),
            "sidecar should be marked dead"
        );

        // The next call must auto-respawn and succeed instead of erroring out.
        let second = bridge
            .call("ping", json!({}))
            .expect("call after respawn should succeed");
        assert_eq!(second["echo"], "ping");

        let new_pid = bridge.inner.child.lock().unwrap().as_ref().unwrap().id();
        assert_ne!(pid, new_pid, "should have respawned a new process");

        bridge.shutdown();
    }
}
