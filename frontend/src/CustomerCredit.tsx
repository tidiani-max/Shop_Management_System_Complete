import { useMemo, useState } from "react";
import { AlertTriangle, Banknote, Check, Plus, Trash2, Users, X } from "lucide-react";
import { api, errMsg, num } from "./api";
import { modalStore, receiptStore, useApp, useFetch } from "./ctx";

type Lang = "fr" | "ar";
const fmt = (v: number, lang: Lang) =>
  `${new Intl.NumberFormat(lang === "ar" ? "ar-MA" : "fr-FR", { maximumFractionDigits: 0 }).format(v)} FCFA`;
const money = (v: number, lang: Lang) => (lang === "ar" ? `\u2066${fmt(v, lang)}\u2069` : fmt(v, lang));
const METHODS = (fr: boolean): [string, string][] => [
  ["cash", fr ? "Espèces" : "نقداً"],
  ["orange", "Orange Money"],
  ["moov", "Moov Money"],
  ["wave", "Wave"],
];

/** Staff screen (workers + owner): customers who owe the shop, and advances the shop holds. Record-only. */
export function CustomerCreditPage({ t, lang, setModal }: any) {
  const fr = lang === "fr";
  const [tab, setTab] = useState<"credits" | "deposits">("credits");
  const { data: debts } = useFetch<any>("/finance/debts?direction=RECEIVABLE");
  const { data: accounts } = useFetch<any[]>("/finance/customer-accounts");
  const credits = debts?.items || [];
  const held = (accounts || []).filter((a) => num(a.deposit_balance) > 0);
  const totalHeld = held.reduce((s, a) => s + num(a.deposit_balance), 0);
  const open = (type: string) => {
    modalStore.data = null;
    setModal(type);
  };
  return (
    <>
      <div className="page-heading row">
        <div>
          <h1>{fr ? "Crédits & avances clients" : "ديون وسلف العملاء"}</h1>
          <p>
            {fr
              ? "Enregistrez ce que le client a pris à crédit, ou l’argent qu’il laisse à la boutique."
              : "سجّل ما أخذه العميل بالدين أو المبلغ الذي تركه لدى المتجر."}
          </p>
        </div>
        <div className="action-group">
          <button className="btn secondary" onClick={() => open("deposit")}>
            <Banknote size={18} />
            {fr ? "Avance client" : "سلفة عميل"}
          </button>
          <button className="btn primary" onClick={() => open("credit")}>
            <Plus size={18} />
            {fr ? "Crédit client" : "دين عميل"}
          </button>
        </div>
      </div>
      <div className="tabs">
        <button className={tab === "credits" ? "active" : ""} onClick={() => setTab("credits")}>
          {fr ? "Clients me doivent" : "العملاء مدينون لي"}
          <span>{money(num(debts?.total_receivable), lang)}</span>
        </button>
        <button className={tab === "deposits" ? "active" : ""} onClick={() => setTab("deposits")}>
          {fr ? "Avances détenues" : "السلف المحفوظة"}
          <span>{money(totalHeld, lang)}</span>
        </button>
      </div>
      <section className="card table-card">
        <div className="people-list">
          {tab === "credits" &&
            credits.map((r: any) => (
              <div className="person-row" key={r.id}>
                <div className="person-avatar">
                  {r.party_name.split(" ").map((x: string) => x[0]).join("").slice(0, 2)}
                </div>
                <div className="person-name">
                  <b>{r.party_name}</b>
                  <small>{r.phone || ""}</small>
                  {r.items?.length > 0 && <small>{r.items.join(" · ")}</small>}
                  <small>
                    {new Date(r.created_at).toLocaleDateString(lang === "ar" ? "ar-MA" : "fr-FR")}
                    {r.recorded_by ? ` · ${r.recorded_by}` : ""}
                  </small>
                </div>
                <div>
                  <small>{fr ? "Dette initiale" : "الدين الأصلي"}</small>
                  <b>{money(num(r.original_amount), lang)}</b>
                </div>
                <div>
                  <small>{t.remaining}</small>
                  <strong>{money(num(r.balance), lang)}</strong>
                </div>
                <button
                  className="btn small secondary"
                  onClick={() => {
                    modalStore.data = { debt: r };
                    setModal("payment");
                  }}
                >
                  {t.recordPayment}
                </button>
              </div>
            ))}
          {tab === "deposits" &&
            held.map((a: any) => (
              <div className="person-row" key={a.customer_id}>
                <div className="person-avatar">
                  {a.name.split(" ").map((x: string) => x[0]).join("").slice(0, 2)}
                </div>
                <div className="person-name">
                  <b>{a.name}</b>
                  <small>{a.phone || ""}</small>
                </div>
                <div>
                  <small>{fr ? "Doit à la boutique" : "مدين للمتجر"}</small>
                  <b>{money(num(a.owed), lang)}</b>
                </div>
                <div>
                  <small>{fr ? "Avance détenue" : "السلفة المحفوظة"}</small>
                  <strong>{money(num(a.deposit_balance), lang)}</strong>
                </div>
              </div>
            ))}
          {((tab === "credits" && credits.length === 0) || (tab === "deposits" && held.length === 0)) && (
            <p className="muted" style={{ padding: 18 }}>
              {fr ? "Rien à afficher pour le moment." : "لا شيء لعرضه حالياً."}
            </p>
          )}
        </div>
      </section>
    </>
  );
}

type CLine = { pid: string; unit: string; qty: string };

/** Modal for type "credit" (customer takes items on credit) and "deposit" (customer leaves money). */
export function CustomerCreditModal({ type, t, lang, close, notify, setModal }: any) {
  const { refresh } = useApp();
  const fr = lang === "fr";
  const isCredit = type === "credit";
  const [v, setV] = useState<Record<string, string>>({ method: "cash" });
  const [lines, setLines] = useState<CLine[]>([{ pid: "", unit: "", qty: "1" }]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const { data: custs } = useFetch<any[]>("/customers");
  const { data: prods } = useFetch<any[]>(isCredit ? "/products" : null);
  const set = (k: string) => (e: any) => setV((x) => ({ ...x, [k]: e.target.value }));
  const patchLine = (i: number, p: Partial<CLine>) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...p } : l)));

  const priced = useMemo(
    () =>
      lines.map((l) => {
        const p = (prods || []).find((x) => String(x.id) === l.pid);
        const u = p?.units.find((x: any) => x.name === (l.unit || p.base_unit));
        return { p, price: num(u?.price), total: num(u?.price) * num(String(l.qty).replace(",", ".")) };
      }),
    [lines, prods],
  );
  const total = priced.reduce((s, x) => s + x.total, 0);

  const submit = async (e: any) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const who = v.customer_id
        ? { customer_id: Number(v.customer_id) }
        : { customer_name: (v.person || "").trim(), customer_phone: (v.phone || "").trim() };
      if (isCredit) {
        const body: any = {
          ...who,
          lines: lines.filter((l) => l.pid).map((l) => ({ product_id: Number(l.pid), unit_name: l.unit || null, quantity: String(l.qty).replace(",", ".") })),
          paid_amount: v.paid || null,
          paid_method: v.method,
          note: v.note || null,
        };
        const res = await api.post("/finance/customer-credit", body);
        receiptStore.invoice = res.invoice;
        refresh();
        notify(fr ? "Crédit enregistré" : "تم تسجيل الدين");
        setModal("receipt");
        return;
      }
      await api.post("/finance/customer-deposits", { ...who, amount: v.amount, method: v.method, note: v.note || null });
      refresh();
      notify(fr ? "Avance enregistrée" : "تم تسجيل السلفة");
      close();
    } catch (x) {
      setErr(errMsg(x));
    } finally {
      setBusy(false);
    }
  };

  const field = (label: string, key: string, props: any = {}) => (
    <label className="field">
      <span>{label}</span>
      <div className="input-wrap">
        <input required value={v[key] || ""} onChange={set(key)} {...props} />
      </div>
    </label>
  );

  return (
    <div className="modal-layer">
      <div className="modal-backdrop" onClick={close} />
      <div className="modal">
        <div className="modal-head">
          <div>
            <span>
              <Users />
            </span>
            <h2>{isCredit ? (fr ? "Crédit client" : "دين عميل") : fr ? "Avance / dépôt client" : "سلفة / وديعة عميل"}</h2>
          </div>
          <button onClick={close}>
            <X />
          </button>
        </div>
        <form onSubmit={submit}>
          <label className="field">
            <span>{fr ? "Client" : "العميل"}</span>
            <div className="select-wrap">
              <select value={v.customer_id || ""} onChange={set("customer_id")}>
                <option value="">{fr ? "+ Nouveau client" : "+ عميل جديد"}</option>
                {(custs || []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                    {c.phone ? ` · ${c.phone}` : ""}
                  </option>
                ))}
              </select>
            </div>
          </label>
          {!v.customer_id && (
            <div className="form-grid">
              {field(fr ? "Nom" : "الاسم", "person")}
              {field(fr ? "Téléphone" : "الهاتف", "phone", { inputMode: "tel" })}
            </div>
          )}
          {isCredit ? (
            <>
              {lines.map((l, i) => {
                const p = priced[i].p;
                return (
                  <div key={i} className="form-grid" style={{ alignItems: "end" }}>
                    <label className="field">
                      <span>{fr ? "Article pris" : "المنتج"}</span>
                      <div className="select-wrap">
                        <select required={i === 0} value={l.pid} onChange={(e) => patchLine(i, { pid: e.target.value, unit: "" })}>
                          <option value="">—</option>
                          {(prods || []).map((x) => (
                            <option key={x.id} value={x.id} disabled={num(x.stock_qty) <= 0}>
                              {x.name_fr} ({num(x.stock_qty)} {x.base_unit})
                            </option>
                          ))}
                        </select>
                      </div>
                    </label>
                    <div style={{ display: "flex", gap: 6, alignItems: "end" }}>
                      <label className="field" style={{ flex: 1 }}>
                        <span>{fr ? "Qté" : "الكمية"}</span>
                        <div className="input-wrap">
                          <input required inputMode="decimal" value={l.qty} onChange={(e) => patchLine(i, { qty: e.target.value })} />
                        </div>
                      </label>
                      {p && (
                        <div className="select-wrap" style={{ flex: 1 }}>
                          <select value={l.unit || p.base_unit} onChange={(e) => patchLine(i, { unit: e.target.value })}>
                            {p.units.map((u: any) => (
                              <option key={u.name} value={u.name}>
                                {u.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                      {lines.length > 1 && (
                        <button type="button" className="icon-only" aria-label="remove" onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))}>
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
              <button type="button" className="btn small secondary" onClick={() => setLines((ls) => [...ls, { pid: "", unit: "", qty: "1" }])}>
                <Plus size={15} />
                {fr ? "Ajouter un article" : "إضافة منتج"}
              </button>
              <p className="muted">
                {fr ? "Total à crédit" : "إجمالي الدين"}: <b>{money(total, lang)}</b>
              </p>
              {field(fr ? "Acompte versé (optionnel)" : "دفعة مقدمة (اختياري)", "paid", { type: "number", step: "0.01", required: false })}
              {v.paid && (
                <label className="field">
                  <span>{t.payment}</span>
                  <div className="select-wrap">
                    <select value={v.method} onChange={set("method")}>
                      {METHODS(fr).map((m) => (
                        <option key={m[0]} value={m[0]}>
                          {m[1]}
                        </option>
                      ))}
                    </select>
                  </div>
                </label>
              )}
              <p className="muted">
                {fr
                  ? "Le stock baisse, le reçu est imprimable. Le prix du catalogue est utilisé ; seul le propriétaire peut le modifier."
                  : "ينقص المخزون ويمكن طباعة الإيصال. يُستخدم سعر الكتالوج، ولا يغيّره إلا المالك."}
              </p>
            </>
          ) : (
            <>
              {field(t.amount, "amount", { type: "number", step: "0.01", placeholder: "0" })}
              <label className="field">
                <span>{t.payment}</span>
                <div className="select-wrap">
                  <select value={v.method} onChange={set("method")}>
                    {METHODS(fr).map((m) => (
                      <option key={m[0]} value={m[0]}>
                        {m[1]}
                      </option>
                    ))}
                  </select>
                </div>
              </label>
              <p className="muted">
                {fr
                  ? "L’argent est encaissé mais n’est pas une vente : il reste au client et peut être utilisé pour payer ses crédits."
                  : "يدخل المبلغ إلى الصندوق لكنه ليس بيعاً: يبقى للعميل ويمكن استخدامه لسداد ديونه."}
              </p>
            </>
          )}
          {field(fr ? "Note (optionnel)" : "ملاحظة (اختياري)", "note", { required: false })}
          {err && (
            <p className="form-error">
              <AlertTriangle size={15} />
              {err}
            </p>
          )}
          <div className="modal-actions">
            <button type="button" className="btn secondary" onClick={close}>
              {t.back}
            </button>
            <button className="btn primary" disabled={busy}>
              {t.save}
              <Check size={17} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
