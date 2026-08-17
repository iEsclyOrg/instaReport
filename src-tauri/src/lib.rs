mod sidecar;

use serde_json::Value;
use tauri::{Manager, State};

use sidecar::BridgeState;

type OptionalBridge = Option<BridgeState>;

#[tauri::command]
async fn sidecar_call(
    state: State<'_, OptionalBridge>,
    method: String,
    params: Value,
) -> Result<Value, String> {
    let bridge = state.inner().as_ref().ok_or_else(|| {
        "Browser automation is not available on this platform. The sidecar was not found.".to_string()
    })?;
    let bridge = bridge.clone();
    let params = params.clone();
    tauri::async_runtime::spawn_blocking(move || bridge.call(&method, params))
        .await
        .map_err(|e| format!("sidecar task failed: {e}"))?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let bridge = BridgeState::spawn().ok();

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(bridge)
        .setup(|app| {
            if let Some(bridge) = app.state::<OptionalBridge>().inner() {
                let handle = app.handle().clone();
                bridge.start_reader(handle);
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![sidecar_call])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let tauri::RunEvent::ExitRequested { .. } = event {
                if let Some(bridge) = app.state::<OptionalBridge>().inner() {
                    bridge.shutdown();
                }
            }
        });
}
