import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

export interface Wire {
  type: string;
  id?: number | null;
  name?: string | null;
  ok?: boolean | null;
  data?: unknown;
  error?: string | null;
}

export type EventHandler = (name: string, data: unknown) => void;

let inited = false;

/** Subscribe once to the Rust-forwarded sidecar event stream. */
export async function initEvents(handler: EventHandler): Promise<void> {
  if (inited) return;
  inited = true;
  await listen<Wire>("sidecar", (e) => {
    const w = e.payload;
    if (w.type === "event" && w.name && w.data !== undefined) {
      handler(w.name, w.data);
    }
  });
}

/** JSON-RPC call to the Python sidecar through the Rust shell. */
export async function call<T = unknown>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<T> {
  return await invoke<T>("sidecar_call", { method, params });
}
