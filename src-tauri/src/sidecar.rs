use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
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
    child: Mutex<Child>,
    stdin: Mutex<ChildStdin>,
    stdout: Mutex<BufReader<ChildStdout>>,
    next_id: Mutex<i64>,
    pending: Mutex<HashMap<i64, Sender<Result<Value, String>>>>,
}

#[derive(Clone)]
pub struct BridgeState {
    inner: Arc<BridgeInner>,
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
fn build_state(mut child: Child) -> Result<BridgeState, String> {
    let stdin = child.stdin.take().ok_or("sidecar stdin unavailable")?;
    let stdout = child.stdout.take().ok_or("sidecar stdout unavailable")?;
    let stderr = child.stderr.take().ok_or("sidecar stderr unavailable")?;

    let state = BridgeState {
        inner: Arc::new(BridgeInner {
            child: Mutex::new(child),
            stdin: Mutex::new(stdin),
            stdout: Mutex::new(BufReader::new(stdout)),
            next_id: Mutex::new(0),
            pending: Mutex::new(HashMap::new()),
        }),
    };

    // Drain stderr so the child never blocks on a full pipe.
    std::thread::spawn(move || {
        for line in BufReader::new(stderr).lines() {
            if let Ok(line) = line {
                eprintln!("[sidecar] {line}");
            }
        }
    });

    Ok(state)
}

impl BridgeState {
    pub fn spawn() -> Result<Self, String> {
        // Prefer a bundled sidecar binary (production installs).
        if let Some(exe) = resolve_bundled_exe() {
            match Command::new(&exe)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
            {
                Ok(child) => return build_state(child),
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
            return build_state(child);
        }
        Err(format!("failed to start Python sidecar ({last_err})"))
    }

    pub fn start_reader(&self, app: AppHandle) {
        let inner = self.inner.clone();
        std::thread::spawn(move || {
            loop {
                let mut line = String::new();
                let n = {
                    let mut stdout = match inner.stdout.lock() {
                        Ok(g) => g,
                        Err(_) => return,
                    };
                    match stdout.read_line(&mut line) {
                        Ok(0) => return, // EOF — sidecar exited
                        Ok(_) => line,
                        Err(_) => return,
                    }
                };
                let wire: Wire = match serde_json::from_str(n.trim_end()) {
                    Ok(w) => w,
                    Err(_) => continue,
                };
                if wire.kind == "event" {
                    let _ = app.emit("sidecar", wire);
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
        let id = {
            let mut n = self.inner.next_id.lock().unwrap();
            *n += 1;
            *n
        };
        let (tx, rx) = channel();
        self.inner.pending.lock().unwrap().insert(id, tx);
        let req = json!({ "id": id, "method": method, "params": params });
        {
            let mut stdin = self.inner.stdin.lock().unwrap();
            writeln!(stdin, "{req}").map_err(|e| format!("sidecar write failed: {e}"))?;
            stdin.flush().map_err(|e| format!("sidecar flush failed: {e}"))?;
        }
        rx.recv_timeout(Duration::from_secs(120))
            .map_err(|_| "sidecar call timed out".to_string())?
    }

    pub fn shutdown(&self) {
        let _ = self.call("shutdown", json!({}));
        if let Ok(mut child) = self.inner.child.lock() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}
