"use client";

import { useEffect, useState, useCallback } from "react";
import { Phone, Clock, Filter, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatDate, formatPhone } from "@/lib/utils";

type Call = {
  id: number;
  lead_name: string | null;
  campaign_name: string | null;
  phone_dialed: string;
  status: string;
  disposition: string | null;
  duration_seconds: number | null;
  call_sid: string | null;
  answered_by: string | null;
  created_at: string | null;
};

const statusVariant: Record<string, "default" | "secondary" | "success" | "warning" | "destructive" | "outline"> = {
  completed: "success",
  answered: "success",
  in_progress: "warning",
  ringing: "warning",
  failed: "destructive",
  busy: "outline",
  no_answer: "outline",
};

export default function CallsPage() {
  const [calls, setCalls] = useState<Call[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      const data = await apiFetch<Call[]>(`/api/calls?${params}`);
      setCalls(data);
    } catch {
      setCalls([]);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => { load(); }, [load]);

  const filtered = calls.filter((c) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (c.lead_name || "").toLowerCase().includes(q) ||
      (c.phone_dialed || "").includes(q) ||
      (c.campaign_name || "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Histórico de Chamadas</h1>
        <p className="text-muted-foreground text-sm mt-1">CDR completo de todas as ligações realizadas</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Input placeholder="Buscar lead, telefone..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">Todos os status</option>
          <option value="completed">Concluídas</option>
          <option value="answered">Atendidas</option>
          <option value="no_answer">Não atendeu</option>
          <option value="busy">Ocupado</option>
          <option value="failed">Falhou</option>
        </select>
        <Button variant="outline" onClick={load}><Filter className="h-4 w-4 mr-2" />Atualizar</Button>
      </div>

      <div className="rounded-xl border bg-card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-muted-foreground">Nenhuma chamada encontrada</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left p-3 font-medium">Lead</th>
                  <th className="text-left p-3 font-medium">Campanha</th>
                  <th className="text-left p-3 font-medium">Telefone</th>
                  <th className="text-left p-3 font-medium">Status</th>
                  <th className="text-left p-3 font-medium">AMD</th>
                  <th className="text-left p-3 font-medium">Duração</th>
                  <th className="text-left p-3 font-medium">Data</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr key={c.id} className="border-b hover:bg-muted/30 transition-colors">
                    <td className="p-3 font-medium">{c.lead_name || "—"}</td>
                    <td className="p-3 text-muted-foreground">{c.campaign_name || "—"}</td>
                    <td className="p-3"><span className="flex items-center gap-1"><Phone className="h-3 w-3" />{formatPhone(c.phone_dialed)}</span></td>
                    <td className="p-3"><Badge variant={statusVariant[c.status] || "secondary"}>{c.status}</Badge></td>
                    <td className="p-3 text-muted-foreground">{c.answered_by || c.disposition || "—"}</td>
                    <td className="p-3"><span className="flex items-center gap-1"><Clock className="h-3 w-3" />{c.duration_seconds ? `${c.duration_seconds}s` : "—"}</span></td>
                    <td className="p-3 text-muted-foreground">{formatDate(c.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
