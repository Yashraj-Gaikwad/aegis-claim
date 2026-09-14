"use client";

import { useMemo, useState } from "react";
import {
  Activity, AlertTriangle, BadgeCheck, CircleDollarSign, FileCheck2, Fingerprint,
  Github, HeartPulse, LoaderCircle, LockKeyhole, Play, RotateCcw, ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const stages = [
  ["Lemma Guard", ShieldCheck], ["GitHub Policy", Github], ["Stripe Ledger", CircleDollarSign],
  ["Arga Twin Verification", BadgeCheck], ["Slack Audit", FileCheck2],
] as const;

type Claim = {
  claim_id: string; patient_id: string; cpt_code: string; icd10_code: string;
  amount: number; clinical_notes: string; deidentify_phi: boolean; scenario?: string;
};
type Result = {
  status: string; stage?: string; error?: string; idempotency_key?: string;
  decision?: { approved?: boolean; policy_reference?: string; exact_evidence_quote?: string } | null;
  verification?: { expected_state?: string; observed_state?: string; verified?: boolean } | null;
  compensation?: { status?: string } | null;
};

const initialClaim: Claim = {
  claim_id: "CLM-1092", patient_id: "PAT-9841", cpt_code: "33361", icd10_code: "I35.0",
  amount: 14500, deidentify_phi: true,
  clinical_notes: "The 74-year-old patient has severe symptomatic aortic stenosis with NYHA Class III heart failure symptoms. Echocardiography documents a valve area of 0.7 cm2 and a mean aortic gradient of 46 mmHg. The multidisciplinary heart team signed off on TAVR.",
};

function Field({ label, value, onChange, type = "text" }: { label: string; value: string | number; onChange: (value: string) => void; type?: string }) {
  return <label className="space-y-2 text-xs font-semibold uppercase tracking-wider text-slate-400"><span>{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} className="w-full rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm font-medium normal-case tracking-normal text-slate-100 transition focus:border-emerald-500/70 focus:ring-2 focus:ring-emerald-500/10" /></label>;
}

export default function Home() {
  const [claim, setClaim] = useState<Claim>(initialClaim);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rollbackMode, setRollbackMode] = useState(false);

  const presentation = useMemo(() => {
    if (!result) return { label: "READY", color: "slate", active: 0 };
    if (rollbackMode || result.status === "compensated_rolled_back") return { label: "COMPENSATED (ROLLBACK)", color: "amber", active: 5 };
    if (result.status === "escalated") return { label: "HALTED (SAFETY INTERLOCK)", color: "rose", active: 1 };
    return { label: result.decision?.approved ? "APPROVED" : "DENIED", color: "emerald", active: 5 };
  }, [result, rollbackMode]);

  async function loadScenario(name: string) {
    setError(""); setResult(null); setRollbackMode(name === "rollback");
    try {
      const response = await fetch(`${API_URL}/api/v1/scenarios/${name}`);
      if (!response.ok) throw new Error("Scenario could not be loaded");
      setClaim(await response.json());
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Scenario could not be loaded"); }
  }

  async function adjudicate() {
    setLoading(true); setError(""); setResult(null);
    try {
      const response = await fetch(`${API_URL}/api/v1/adjudicate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(claim) });
      if (!response.ok) throw new Error(`API rejected the claim (${response.status})`);
      setResult(await response.json());
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Adjudication failed"); }
    finally { setLoading(false); }
  }

  const set = (key: keyof Claim, value: string | number | boolean) => setClaim((current) => ({ ...current, [key]: value }));
  const statusClasses = presentation.color === "rose" ? "border-rose-500/40 bg-rose-500/10 text-rose-300" : presentation.color === "amber" ? "border-amber-500/40 bg-amber-500/10 text-amber-300" : presentation.color === "emerald" ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300" : "border-slate-700 bg-slate-800 text-slate-300";

  return <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.08),_transparent_32rem)] px-4 py-8 lg:px-8">
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-2xl shadow-black/20 backdrop-blur">
        <div className="flex flex-col justify-between gap-6 xl:flex-row xl:items-center">
          <div className="flex items-center gap-4"><div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-3"><HeartPulse className="h-8 w-8 text-emerald-400" /></div><div><p className="mb-1 text-xs font-bold uppercase tracking-[0.24em] text-emerald-400">High-Assurance Operations</p><h1 className="text-3xl font-bold tracking-tight">AegisClaim Control Center</h1><p className="mt-1 text-sm text-slate-400">Zero-Silent-Failure Clinical-Financial State Engine</p></div></div>
          <div className="flex flex-wrap gap-2"><button onClick={() => loadScenario("nominal")} className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-300 hover:bg-emerald-500/20">Load Nominal</button><button onClick={() => loadScenario("placeholder")} className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-2 text-sm font-semibold text-rose-300 hover:bg-rose-500/20">Inject Adversarial Token (&apos;unknown&apos;)</button><button onClick={() => loadScenario("rollback")} className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm font-semibold text-amber-300 hover:bg-amber-500/20"><RotateCcw className="h-4 w-4" />Simulate Saga Rollback</button></div>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6"><div className="mb-6 flex items-center gap-3"><LockKeyhole className="h-5 w-5 text-emerald-400" /><div><h2 className="font-bold">Claim Input & Ingestion</h2><p className="text-xs text-slate-500">Validated before any external mutation</p></div></div>
          <div className="grid gap-4 sm:grid-cols-2"><Field label="Claim ID" value={claim.claim_id} onChange={(v) => set("claim_id", v)} /><Field label="Patient ID" value={claim.patient_id} onChange={(v) => set("patient_id", v)} /><Field label="CPT Code" value={claim.cpt_code} onChange={(v) => set("cpt_code", v)} /><Field label="ICD-10 Code" value={claim.icd10_code} onChange={(v) => set("icd10_code", v)} /><div className="sm:col-span-2"><Field label="Amount ($)" type="number" value={claim.amount} onChange={(v) => set("amount", Number(v))} /></div></div>
          <label className="mt-4 block space-y-2 text-xs font-semibold uppercase tracking-wider text-slate-400"><span>Clinical Narrative</span><textarea rows={8} value={claim.clinical_notes} onChange={(event) => set("clinical_notes", event.target.value)} className="w-full resize-none rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm font-medium normal-case leading-relaxed tracking-normal text-slate-100 focus:border-emerald-500/70 focus:ring-2 focus:ring-emerald-500/10" /></label>
          <button onClick={() => set("deidentify_phi", !claim.deidentify_phi)} className="my-5 flex w-full items-center justify-between rounded-xl border border-slate-800 bg-slate-950 p-4 text-left"><span><span className="block text-sm font-semibold">HIPAA Safe Harbor PHI Scrubbing</span><span className="text-xs text-slate-500">Redact direct identifiers before policy matching</span></span><span className={cn("relative h-6 w-11 rounded-full transition", claim.deidentify_phi ? "bg-emerald-500" : "bg-slate-700")}><span className={cn("absolute top-1 h-4 w-4 rounded-full bg-white transition", claim.deidentify_phi ? "left-6" : "left-1")} /></span></button>
          <button disabled={loading} onClick={adjudicate} className="flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-500 px-5 py-3.5 font-bold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60">{loading ? <LoaderCircle className="h-5 w-5 animate-spin" /> : <Play className="h-5 w-5 fill-current" />}{loading ? "Running deterministic controls..." : "Run Adjudication Engine"}</button>{error && <p className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300">{error}</p>}
        </section>

        <section className="space-y-6 rounded-2xl border border-slate-800 bg-slate-900/80 p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><Activity className="h-5 w-5 text-emerald-400" /><div><h2 className="font-bold">Live Pipeline & Verification</h2><p className="text-xs text-slate-500">Deterministic execution trace</p></div></div><span className={cn("rounded-full border px-3 py-1.5 text-xs font-bold tracking-wider", statusClasses)}>{presentation.label}</span></div>
          <div className="grid gap-2 md:grid-cols-5">{stages.map(([label, Icon], index) => <div key={label} className={cn("rounded-xl border p-3 transition", index < presentation.active ? statusClasses : "border-slate-800 bg-slate-950 text-slate-600")}><div className="mb-3 flex items-center justify-between"><Icon className="h-4 w-4" /><span className="font-mono text-xs">0{index + 1}</span></div><p className="text-xs font-semibold leading-tight">{label}</p></div>)}</div>
          {result ? <div className="space-y-4"><div className="grid gap-4 sm:grid-cols-2"><div className="rounded-xl border border-slate-800 bg-slate-950 p-4"><div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500"><Github className="h-4 w-4" />Policy Provenance</div><p className="font-mono text-sm text-emerald-300">{result.decision?.policy_reference || "Not reached"}</p></div><div className="rounded-xl border border-slate-800 bg-slate-950 p-4"><div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500"><Fingerprint className="h-4 w-4" />Idempotency Key</div><p className="truncate font-mono text-sm text-cyan-300" title={result.idempotency_key}>{result.idempotency_key || "No financial mutation"}</p></div></div>
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-4"><p className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">Verbatim Grounded Evidence</p><blockquote className="border-l-2 border-emerald-500 pl-4 text-sm italic leading-relaxed text-slate-300">{result.decision?.exact_evidence_quote || result.error || "No evidence released after safety halt."}</blockquote></div>
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-4"><p className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">State Reconciliation</p>{result.verification ? <div className="flex flex-wrap items-center gap-3 font-mono text-sm"><span className="rounded-lg bg-slate-800 px-3 py-2">{result.verification.expected_state}</span><span className="text-emerald-400">==</span><span className="rounded-lg bg-slate-800 px-3 py-2">{result.verification.observed_state}</span><BadgeCheck className="h-5 w-5 text-emerald-400" /></div> : <div className="flex items-center gap-2 text-sm text-rose-300"><AlertTriangle className="h-4 w-4" />Ledger mutation was blocked before reconciliation.</div>}</div>
          </div> : <div className="flex min-h-80 flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 bg-slate-950/60 text-center"><ShieldCheck className="mb-4 h-12 w-12 text-slate-700" /><p className="font-semibold text-slate-400">Awaiting adjudication</p><p className="mt-1 max-w-xs text-sm text-slate-600">Load a scenario or submit a claim to visualize the five-stage assurance pipeline.</p></div>}
        </section>
      </div>
    </div>
  </main>;
}
