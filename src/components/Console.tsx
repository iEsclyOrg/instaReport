import { useEffect, useRef, useState } from "react";
import { useApp } from "../store";

export default function Console() {
  const lines = useApp((s) => s.console);
  const clearConsole = useApp((s) => s.clearConsole);
  const bodyRef = useRef<HTMLDivElement>(null);
  const [flash, setFlash] = useState<"err" | "warn" | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [follow, setFollow] = useState(true);

  const last = lines.length ? lines[lines.length - 1] : null;

  useEffect(() => {
    if (follow && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [lines.length, follow]);

  useEffect(() => {
    if (last && (last.tag === "err" || last.tag === "warn")) {
      setFlash(last.tag);
      const t = window.setTimeout(() => setFlash(null), 700);
      return () => window.clearTimeout(t);
    }
  }, [last]);

  function handleScroll() {
    const el = bodyRef.current;
    if (!el) return;
    setFollow(el.scrollHeight - el.scrollTop - el.clientHeight < 28);
  }

  function jumpToBottom() {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    setFollow(true);
  }

  async function copyText(text: string, id: number | null = null) {
    try {
      await navigator.clipboard.writeText(text);
      if (id !== null) {
        setCopiedId(id);
        window.setTimeout(() => setCopiedId(null), 1200);
      }
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className="console">
      <div className="console-strip">
        <span className={`console-title ${flash ? `flash-${flash}` : ""}`}>Console</span>
        <div className="spacer" />
        <button className="btn btn-ghost sm" onClick={() => void copyText(lines.map((l) => l.msg).join("\n"))}>
          Copy All
        </button>
        <button className="btn btn-ghost sm" onClick={clearConsole}>
          Clear
        </button>
      </div>
      <div className="console-wrap">
        <div className="console-body" ref={bodyRef} onScroll={handleScroll}>
          {lines.map((l) => (
            <div key={l.id} className={`console-line c-tag-${l.tag}`}>
              {l.msg}
              <button
                className="line-copy"
                onClick={() => void copyText(l.msg, l.id)}
                title="Copy this line"
              >
                {copiedId === l.id ? "✓ copied" : "copy"}
              </button>
            </div>
          ))}
        </div>
        {!follow && (
          <button className="console-jump" onClick={jumpToBottom} title="Jump to newest output">
            ↓ newest
          </button>
        )}
      </div>
    </div>
  );
}
