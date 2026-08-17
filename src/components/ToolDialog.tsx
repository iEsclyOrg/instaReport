import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { useApp, type ToolField, type ToolResult, type ToolSchema } from "../store";

function initialValues(fields: ToolField[] | undefined): Record<string, unknown> {
  const v: Record<string, unknown> = {};
  for (const f of fields ?? []) {
    v[f.key] = f.type === "bool" ? Boolean(f.default) : (f.default ?? "");
  }
  return v;
}

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: ToolField;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  if (field.type === "bool") {
    return (
      <label className="tool-field">
        <span className="tool-label">{field.label}</span>
        <input
          type="checkbox"
          className="switch"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
        />
      </label>
    );
  }
  if (field.type === "select") {
    return (
      <label className="tool-field">
        <span className="tool-label">{field.label}</span>
        <select
          className="field"
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        >
          {(field.options ?? []).map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      </label>
    );
  }
  if (field.type === "number") {
    return (
      <label className="tool-field">
        <span className="tool-label">{field.label}</span>
        <input
          type="number"
          className="field"
          min={field.min}
          max={field.max}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        />
      </label>
    );
  }
  if (field.type === "textarea") {
    return (
      <label className="tool-field wide">
        <span className="tool-label">{field.label}</span>
        <textarea
          className={`field textarea${field.mono ? " mono" : ""}`}
          rows={4}
          placeholder={field.placeholder}
          value={String(value ?? "")}
          spellCheck={false}
          onChange={(e) => onChange(e.target.value)}
        />
      </label>
    );
  }
  return (
    <label className="tool-field">
      <span className="tool-label">{field.label}</span>
      <input
        className="field"
        type={field.type === "password" ? "password" : "text"}
        placeholder={field.placeholder}
        value={String(value ?? "")}
        spellCheck={false}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

function ResultView({ result }: { result: ToolResult | null }) {
  if (!result) return null;
  return (
    <div className="tool-result">
      {result.rows ? (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                {(result.columns ?? []).map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => (
                    <td key={j}>{String(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {result.url ? (
        <p className="tool-msg">
          {result.message} <a href={result.url} target="_blank" rel="noreferrer">open ↗</a>
        </p>
      ) : result.message ? (
        <p className="tool-msg">{result.message}</p>
      ) : null}
    </div>
  );
}

function ActionDialog({ schema }: { schema: ToolSchema }) {
  const runTool = useApp((s) => s.runTool);
  const close = useApp((s) => s.closeToolDialog);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ToolResult | null>(null);

  async function go() {
    setBusy(true);
    setResult(null);
    try {
      setResult(await runTool(schema.key, {}));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h3>{schema.title}</h3>
      <p className="hint">{schema.desc}</p>
      {schema.available === false ? (
        <p className="tool-msg warn">Not available in this build.</p>
      ) : (
        <>
          <ResultView result={result} />
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={close}>
              Close
            </button>
            <button
              className={`btn ${schema.danger ? "btn-danger" : "btn-primary"}`}
              onClick={() => void go()}
              disabled={busy}
            >
              {busy ? "Working…" : schema.button ?? "Run"}
            </button>
          </div>
        </>
      )}
    </>
  );
}

function FormDialog({ schema }: { schema: ToolSchema }) {
  const runTool = useApp((s) => s.runTool);
  const close = useApp((s) => s.closeToolDialog);
  const fields = schema.fields ?? [];
  const [values, setValues] = useState<Record<string, unknown>>(() => initialValues(fields));
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ToolResult | null>(null);

  function submit() {
    const missing = fields.find(
      (f) => f.required && !String(values[f.key] ?? "").trim(),
    );
    if (missing) {
      setResult({ message: `${missing.label} is required` });
      return;
    }
    setBusy(true);
    setResult(null);
    void runTool(schema.key, values)
      .then(setResult)
      .finally(() => setBusy(false));
  }

  return (
    <>
      <h3>{schema.title}</h3>
      <p className="hint">{schema.desc}</p>
      <div className="tool-form">
        {fields.map((f) => (
          <FieldInput
            key={f.key}
            field={f}
            value={values[f.key]}
            onChange={(v) => setValues((p) => ({ ...p, [f.key]: v }))}
          />
        ))}
      </div>
      <ResultView result={result} />
      <div className="modal-actions">
        <button className="btn btn-ghost" onClick={close}>
          Cancel
        </button>
        <button className="btn btn-primary" onClick={submit} disabled={busy}>
          {busy ? "Working…" : schema.button ?? "Run"}
        </button>
      </div>
    </>
  );
}

function TableDialog({ schema }: { schema: ToolSchema }) {
  const runTool = useApp((s) => s.runTool);
  const close = useApp((s) => s.closeToolDialog);
  const columns = useMemo(() => (schema.columns ?? []).filter((c) => !c.hidden), [schema]);
  const inputs = schema.inputs ?? [];
  const [inputVals, setInputVals] = useState<Record<string, unknown>>(() => initialValues(inputs));
  const [result, setResult] = useState<ToolResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    try {
      setResult(await runTool(schema.key, {}));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function act(param: string, extra: Record<string, unknown> = {}) {
    setBusy(true);
    try {
      setResult(await runTool(schema.key, { action: param, ...inputVals, ...extra }));
    } finally {
      setBusy(false);
    }
  }

  const rows = result?.rows ?? [];

  return (
    <>
      <h3>{schema.title}</h3>
      <p className="hint">{schema.desc}</p>
      {(inputs.length > 0 || (schema.actions ?? []).length > 0) && (
        <div className="toolbar">
          {inputs.map((f) => (
            <FieldInput
              key={f.key}
              field={f}
              value={inputVals[f.key]}
              onChange={(v) => setInputVals((p) => ({ ...p, [f.key]: v }))}
            />
          ))}
          {(schema.actions ?? []).map((a) => (
            <button
              key={a.param}
              className={`btn ${a.danger ? "btn-danger" : "btn-primary"}`}
              style={{ padding: "6px 14px" }}
              onClick={() => void act(a.param)}
              disabled={busy}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
      <div className="table-wrap tool-table">
        <table className="data">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key}>{c.label}</th>
              ))}
              {(schema.row_actions ?? []).length > 0 && <th />}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={columns.length + 1} className="empty">No rows</td>
              </tr>
            )}
            {rows.map((row, i) => {
              return (
                <tr key={i}>
                  {columns.map((c) => (
                    <td key={c.key}>
                      {String(row[(schema.columns ?? []).indexOf(c)])}
                    </td>
                  ))}
                  {(schema.row_actions ?? []).length > 0 && (
                    <td className="row-actions">
                      {(schema.row_actions ?? []).map((a) => (
                        <button
                          key={a.param}
                          className={`btn ${a.danger ? "btn-danger" : "btn-ghost"}`}
                          style={{ padding: "3px 9px", fontSize: 10 }}
                          onClick={() => void act(a.param, { row })}
                          disabled={busy}
                        >
                          {a.label}
                        </button>
                      ))}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="modal-actions">
        <button className="btn btn-ghost" onClick={close}>
          Close
        </button>
      </div>
    </>
  );
}

export default function ToolDialog() {
  const dialog = useApp((s) => s.toolDialog);
  if (!dialog) return null;
  const { schema } = dialog;
  return (
    <div className="overlay" onClick={() => void 0}>
      <motion.div
        className={schema.kind === "table" ? "modal wide" : "modal"}
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.16, ease: "easeOut" }}
        onClick={(e) => e.stopPropagation()}
      >
        {schema.kind === "action" ? (
          <ActionDialog schema={schema} />
        ) : schema.kind === "table" ? (
          <TableDialog schema={schema} />
        ) : (
          <FormDialog schema={schema} />
        )}
      </motion.div>
    </div>
  );
}
