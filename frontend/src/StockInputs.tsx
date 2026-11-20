import { useRef, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api, errMsg } from "./api";

export const BASE_UNITS = ["Pièce", "Kg", "Litre", "Paquet"];
const PACK_NAMES = ["Carton", "Boîte", "Paquet", "Sachet", "Sac", "Pack"];
const QUICK_COUNTS = ["6", "10", "12", "20", "24", "50", "100"];
const OTHER = "__other";

const toNum = (s: string) => Number(String(s).replace(",", ".")) || 0;
const nf = (n: number) => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 3 }).format(n);

/** Keep only digits and one decimal point (max 2 decimals). The form state stays a clean "20000". */
export const cleanMoney = (s: string) => {
  let t = s.replace(/,/g, ".").replace(/[^\d.]/g, "");
  const k = t.indexOf(".");
  if (k >= 0) t = t.slice(0, k + 1) + t.slice(k + 1).replace(/\./g, "").slice(0, 2);
  return t.replace(/^0+(?=\d)/, "");
};
/** "20000" -> "20 000" (narrow no-break space, same as the rest of the app). */
export const groupDigits = (raw: string) => {
  if (!raw) return "";
  const [int, dec] = raw.split(".");
  const g = int.replace(/\B(?=(\d{3})+(?!\d))/g, "\u202F");
  return dec !== undefined ? `${g}.${dec}` : g;
};

/** Price / amount input that shows 20 000 while typing; onChange receives the clean string "20000". */
export function MoneyField({ label, icon, value, onChange, required = true, placeholder = "0" }: any) {
  return (
    <label className="field">
      <span>{label}</span>
      <div className="input-wrap">
        {icon}
        <input
          required={required}
          inputMode="decimal"
          dir="ltr"
          placeholder={placeholder}
          value={groupDigits(value || "")}
          onChange={(e) => onChange(cleanMoney(e.target.value))}
        />
      </div>
    </label>
  );
}

function PackName({ fr, name, onChange }: { fr: boolean; name: string; onChange: (n: string) => void }) {
  const [custom, setCustom] = useState(false);
  const isCustom = custom || (name !== "" && !PACK_NAMES.includes(name));
  return (
    <>
      <label className="field">
        <span>{fr ? "Conditionnement" : "التعبئة"}</span>
        <div className="select-wrap">
          <select
            value={isCustom ? OTHER : name}
            onChange={(e) => {
              if (e.target.value === OTHER) {
                setCustom(true);
                onChange("");
              } else {
                setCustom(false);
                onChange(e.target.value);
              }
            }}
          >
            <option value="">—</option>
            {PACK_NAMES.map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
            <option value={OTHER}>{fr ? "Autre…" : "أخرى…"}</option>
          </select>
        </div>
      </label>
      {isCustom && (
        <label className="field">
          <span>{fr ? "Nom" : "الاسم"}</span>
          <div className="input-wrap">
            <input value={name} onChange={(e) => onChange(e.target.value)} />
          </div>
        </label>
      )}
    </>
  );
}

function CountPicker({ label, count, onCount }: { label: string; count: string; onCount: (v: string) => void }) {
  return (
    <div className="field">
      <span>{label}</span>
      <div className="input-wrap">
        <input inputMode="decimal" dir="ltr" placeholder="0" value={count} onChange={(e) => onCount(cleanMoney(e.target.value))} />
      </div>
      <div className="category-pills">
        {QUICK_COUNTS.map((c) => (
          <button type="button" key={c} className={count === c ? "active" : ""} onClick={() => onCount(c)}>
            {c}
          </button>
        ))}
      </div>
    </div>
  );
}

const noEnter = (e: any) => {
  if (e.key === "Enter") e.preventDefault(); // Enter here must not submit the whole product form
};

type Row = { id: number; name: string; count: string; inner: number };

/** New product: "1 Carton contient 20 Paquets", "1 Paquet contient 10 Pièces". Emits "Paquet=10, Carton=200". */
export function PackagingBuilder({ lang, baseUnit, onChange }: { lang: string; baseUnit: string; onChange: (units: string) => void }) {
  const fr = lang === "fr";
  const [rows, setRows] = useState<Row[]>([]);
  const seq = useRef(0);
  const base = baseUnit || (fr ? "unité" : "وحدة");
  const factors = (rs: Row[]) => {
    const f: number[] = [];
    rs.forEach((r, i) => {
      f[i] = toNum(r.count) * (r.inner >= 0 && r.inner < i ? f[r.inner] : 1);
    });
    return f;
  };
  const emit = (rs: Row[]) => {
    setRows(rs);
    const f = factors(rs);
    onChange(
      rs
        .map((r, i) => ({ name: r.name.trim(), factor: +f[i].toFixed(3) }))
        .filter((x) => x.name && x.factor > 0)
        .map((x) => `${x.name}=${x.factor}`)
        .join(", "),
    );
  };
  const patch = (i: number, p: Partial<Row>) => emit(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));
  const remove = (k: number) =>
    emit(rows.filter((_, i) => i !== k).map((r) => ({ ...r, inner: r.inner === k ? -1 : r.inner > k ? r.inner - 1 : r.inner })));
  const add = () => emit([...rows, { id: ++seq.current, name: "", count: "", inner: rows.length ? rows.length - 1 : -1 }]);
  const f = factors(rows);
  return (
    <div style={{ display: "grid", gap: 10 }} onKeyDown={noEnter}>
      <span className="muted">
        <b>{fr ? "Conditionnements (facultatif)" : "التعبئات (اختياري)"}</b>
        {" · "}
        {fr ? "Ex. : 1 Carton contient 20 Paquets, 1 Paquet contient 10 Pièces." : "مثال: الكرتون يحتوي 20 علبة، والعلبة 10 قطع."}
      </span>
      {rows.map((r, i) => (
        <div key={r.id} style={{ border: "1px solid var(--line)", borderRadius: 12, padding: 12, display: "grid", gap: 8 }}>
          <PackName fr={fr} name={r.name} onChange={(n) => patch(i, { name: n })} />
          <label className="field">
            <span>{fr ? "Il contient des…" : "يحتوي على…"}</span>
            <div className="select-wrap">
              <select value={r.inner} onChange={(e) => patch(i, { inner: Number(e.target.value) })}>
                <option value={-1}>{base}</option>
                {rows.slice(0, i).map((x, j) => (
                  <option key={x.id} value={j}>{x.name || `#${j + 1}`}</option>
                ))}
              </select>
            </div>
          </label>
          <CountPicker label={fr ? "Combien ?" : "كم العدد؟"} count={r.count} onCount={(c) => patch(i, { count: c })} />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <small className="muted">
              {f[i] > 0 ? <b>1 {r.name || "…"} = {nf(f[i])} {base}</b> : ""}
            </small>
            <button type="button" className="icon-only" aria-label="remove" onClick={() => remove(i)}>
              <Trash2 size={16} />
            </button>
          </div>
        </div>
      ))}
      <button type="button" className="btn small secondary" onClick={add}>
        <Plus size={15} />
        {fr ? "Ajouter un conditionnement (carton, sachet…)" : "إضافة تعبئة (كرتون، كيس…)"}
      </button>
    </div>
  );
}

/** Receive stock on an EXISTING product that lacks the packaging (e.g. Carton). Calls POST /products/{id}/units. */
export function AddPackagingForm({ lang, product, onAdded }: { lang: string; product: any; onAdded: (name: string) => void }) {
  const fr = lang === "fr";
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [count, setCount] = useState("");
  const [inner, setInner] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const units: any[] = product.units || [];
  const innerName = inner || product.base_unit;
  const innerUnit = units.find((u) => u.name === innerName);
  const factor = +(toNum(count) * (Number(innerUnit?.factor) || 1)).toFixed(3);
  const save = async () => {
    setBusy(true);
    setErr("");
    try {
      await api.post(`/products/${product.id}/units`, { name: name.trim(), factor: String(factor) });
      onAdded(name.trim());
      setOpen(false);
      setName("");
      setCount("");
      setInner("");
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  };
  if (!open)
    return (
      <button type="button" className="btn small secondary" onClick={() => setOpen(true)}>
        <Plus size={15} />
        {fr ? "Ajouter un conditionnement (carton, sachet…)" : "إضافة تعبئة (كرتون، كيس…)"}
      </button>
    );
  return (
    <div style={{ border: "1px solid var(--line)", borderRadius: 12, padding: 12, display: "grid", gap: 8 }} onKeyDown={noEnter}>
      <PackName fr={fr} name={name} onChange={setName} />
      <label className="field">
        <span>{fr ? "Il contient des…" : "يحتوي على…"}</span>
        <div className="select-wrap">
          <select value={innerName} onChange={(e) => setInner(e.target.value)}>
            {units.map((u) => (
              <option key={u.name} value={u.name}>{u.name}</option>
            ))}
          </select>
        </div>
      </label>
      <CountPicker label={fr ? "Combien ?" : "كم العدد؟"} count={count} onCount={setCount} />
      {factor > 0 && name.trim() && (
        <small className="muted">
          <b>1 {name.trim()} = {nf(factor)} {product.base_unit}</b>
        </small>
      )}
      {err && <p className="form-error">{err}</p>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="btn small secondary" onClick={() => setOpen(false)}>
          {fr ? "Annuler" : "إلغاء"}
        </button>
        <button type="button" className="btn small primary" disabled={busy || !name.trim() || !(factor > 0)} onClick={save}>
          {fr ? "Ajouter" : "إضافة"}
        </button>
      </div>
    </div>
  );
}
