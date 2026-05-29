"use client";

import { useState } from "react";
import { Upload, FileSpreadsheet, CheckCircle2, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

type Campaign = { id: number; name: string };
type Preview = {
  columns: string[];
  sample: Record<string, string | null>[];
  suggestions: Record<string, string | null>;
  lead_fields: string[];
};

const FIELD_LABELS: Record<string, string> = {
  name: "Nome", email: "Email", company_name: "Empresa", job_title: "Cargo",
  city: "Cidade", state: "Estado", notes: "Observações",
  numero_1: "Telefone 1", numero_2: "Telefone 2", numero_3: "Telefone 3",
};

export default function ImportPage() {
  const [step, setStep] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignId, setCampaignId] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ imported: number; skipped: number; errors: string[] } | null>(null);

  const loadCampaigns = async () => {
    if (campaigns.length) return;
    try {
      const data = await apiFetch<Campaign[]>("/api/campaigns");
      setCampaigns(data);
    } catch { /* ignore */ }
  };

  const handleFile = async (f: File) => {
    setFile(f);
    setLoading(true);
    await loadCampaigns();
    try {
      const fd = new FormData();
      fd.append("file", f);
      const res = await fetch("/api/leads/import/preview", { method: "POST", body: fd, credentials: "include" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      setPreview(data);
      const initial: Record<string, string> = {};
      for (const [col, field] of Object.entries(data.suggestions as Record<string, string | null>)) {
        if (field) initial[col] = field;
      }
      setMapping(initial);
      setStep(2);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao ler arquivo");
    } finally {
      setLoading(false);
    }
  };

  const doImport = async () => {
    if (!file || !campaignId) return;
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("campaign_id", campaignId);
      fd.append("column_mapping", JSON.stringify(mapping));
      const res = await fetch("/api/leads/import", { method: "POST", body: fd, credentials: "include" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      setResult(data);
      setStep(3);
      toast.success(`${data.imported} leads importados!`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro na importação");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Importar Leads</h1>
        <p className="text-muted-foreground text-sm mt-1">CSV ou XLSX com mapeamento de colunas</p>
      </div>

      <div className="flex gap-2">
        {[1, 2, 3].map((s) => (
          <div key={s} className={`flex-1 h-1 rounded-full ${step >= s ? "bg-primary" : "bg-muted"}`} />
        ))}
      </div>

      {step === 1 && (
        <div
          className="border-2 border-dashed rounded-xl p-12 text-center hover:border-primary/50 transition-colors cursor-pointer"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
          onClick={() => document.getElementById("import-file")?.click()}
        >
          <input id="import-file" type="file" accept=".csv,.xlsx,.xls" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
          {loading ? <Loader2 className="h-10 w-10 mx-auto animate-spin text-muted-foreground" /> : (
            <>
              <Upload className="h-10 w-10 mx-auto text-muted-foreground mb-4" />
              <p className="font-medium">Arraste CSV/XLSX ou clique para selecionar</p>
              <p className="text-sm text-muted-foreground mt-1">Aliases PT-BR: nome, telefone, empresa, cargo...</p>
            </>
          )}
        </div>
      )}

      {step === 2 && preview && (
        <div className="space-y-4">
          <div className="rounded-xl border p-4 space-y-3">
            <Label>Campanha destino</Label>
            <select className="w-full h-10 rounded-md border px-3 text-sm" value={campaignId}
              onChange={(e) => setCampaignId(e.target.value)}>
              <option value="">Selecione...</option>
              {campaigns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>

          <div className="rounded-xl border overflow-hidden">
            <div className="p-3 bg-muted/50 font-medium text-sm flex items-center gap-2">
              <FileSpreadsheet className="h-4 w-4" />Mapeamento de colunas
            </div>
            <div className="divide-y">
              {preview.columns.map((col) => (
                <div key={col} className="flex items-center gap-4 p-3">
                  <span className="text-sm font-mono flex-1">{col}</span>
                  <select className="h-9 rounded-md border px-2 text-sm w-48"
                    value={mapping[col] || ""} onChange={(e) => setMapping({ ...mapping, [col]: e.target.value })}>
                    <option value="">Ignorar</option>
                    {preview.lead_fields.map((f) => (
                      <option key={f} value={f}>{FIELD_LABELS[f] || f}</option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          </div>

          {preview.sample.length > 0 && (
            <div className="rounded-xl border overflow-x-auto">
              <table className="w-full text-xs">
                <thead><tr className="bg-muted/50">{preview.columns.map((c) => <th key={c} className="p-2 text-left">{c}</th>)}</tr></thead>
                <tbody>{preview.sample.slice(0, 3).map((row, i) => (
                  <tr key={i} className="border-t">{preview.columns.map((c) => <td key={c} className="p-2">{row[c] || "—"}</td>)}</tr>
                ))}</tbody>
              </table>
            </div>
          )}

          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setStep(1)}>Voltar</Button>
            <Button onClick={doImport} disabled={!campaignId || loading} loading={loading}>
              Importar {file?.name}
            </Button>
          </div>
        </div>
      )}

      {step === 3 && result && (
        <div className="rounded-xl border p-8 text-center space-y-4">
          <CheckCircle2 className="h-12 w-12 mx-auto text-green-500" />
          <h2 className="text-xl font-bold">{result.imported} leads importados</h2>
          {result.skipped > 0 && <p className="text-muted-foreground">{result.skipped} ignorados (duplicados/inválidos)</p>}
          <Button onClick={() => { setStep(1); setFile(null); setResult(null); }}>Nova importação</Button>
        </div>
      )}
    </div>
  );
}
