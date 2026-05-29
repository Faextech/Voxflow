"use client";

import { useEffect, useState, useCallback } from "react";
import { LineChart, TrendingUp, Phone, Users, Target, Loader2, Download } from "lucide-react";
import { apiFetch, exportCsv } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

type DashboardData = {
  leads: { total: number; new_today: number };
  calls: { total: number; answered: number; today: number };
  campaigns: { active: number; total: number };
  conversion: { rate: number; deals_won: number };
};

type AmdData = {
  human: number;
  machine: number;
  unknown: number;
  total: number;
};

type FunnelStep = { label: string; count: number };

export default function AnalyticsPage() {
  const [period, setPeriod] = useState("30");
  const [data, setData] = useState<DashboardData | null>(null);
  const [amd, setAmd] = useState<AmdData | null>(null);
  const [funnel, setFunnel] = useState<FunnelStep[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dash, amdData, funnelData] = await Promise.all([
        apiFetch<DashboardData>(`/api/analytics/dashboard?period=${period}`),
        apiFetch<AmdData>(`/api/analytics/amd?period=${period}`).catch(() => null),
        apiFetch<{ steps: FunnelStep[] }>(`/api/analytics/funnel?period=${period}`).catch(() => ({ steps: [] })),
      ]);
      setData(dash);
      setAmd(amdData);
      setFunnel(funnelData.steps || []);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => { load(); }, [load]);

  const kpis = data ? [
    { label: "Total Leads", value: data.leads.total, icon: Users, sub: `+${data.leads.new_today} hoje` },
    { label: "Chamadas", value: data.calls.total, icon: Phone, sub: `${data.calls.answered} atendidas` },
    { label: "Campanhas Ativas", value: data.campaigns.active, icon: Target, sub: `${data.campaigns.total} total` },
    { label: "Conversão", value: `${data.conversion.rate}%`, icon: TrendingUp, sub: `${data.conversion.deals_won} ganhos` },
  ] : [];

  const amdTotal = amd?.total || 1;
  const amdPct = (v: number) => Math.round((v / amdTotal) * 100);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
          <p className="text-muted-foreground text-sm mt-1">KPIs comerciais, funil e qualidade AMD</p>
        </div>
        <div className="flex gap-2">
          {["7", "30", "90"].map((p) => (
            <Button key={p} size="sm" variant={period === p ? "default" : "outline"} onClick={() => setPeriod(p)}>
              {p}d
            </Button>
          ))}
          <Button size="sm" variant="outline" onClick={() => exportCsv(`/api/analytics/export/calls?period=${period}`)}>
            <Download className="h-4 w-4 mr-1" />Exportar
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : (
        <>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {kpis.map((k) => (
              <div key={k.label} className="rounded-xl border bg-card p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-muted-foreground">{k.label}</span>
                  <k.icon className="h-4 w-4 text-primary" />
                </div>
                <p className="text-2xl font-bold">{k.value}</p>
                <p className="text-xs text-muted-foreground mt-1">{k.sub}</p>
              </div>
            ))}
          </div>

          {funnel.length > 0 && (
            <div className="rounded-xl border bg-card p-6">
              <h2 className="font-semibold mb-4 flex items-center gap-2"><LineChart className="h-4 w-4" />Funil de Conversão</h2>
              <div className="space-y-3">
                {funnel.map((step, i) => {
                  const max = funnel[0]?.count || 1;
                  const pct = Math.round((step.count / max) * 100);
                  return (
                    <div key={step.label}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>{step.label}</span>
                        <span className="text-muted-foreground">{step.count} ({pct}%)</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${pct}%`, opacity: 1 - i * 0.12 }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {amd && (
            <div className="rounded-xl border bg-card p-6">
              <h2 className="font-semibold mb-4">Qualidade AMD (Answering Machine Detection)</h2>
              <div className="grid sm:grid-cols-3 gap-4">
                {[
                  { label: "Humano", value: amd.human, color: "bg-green-500" },
                  { label: "Caixa Postal", value: amd.machine, color: "bg-amber-500" },
                  { label: "Desconhecido", value: amd.unknown, color: "bg-gray-400" },
                ].map((item) => (
                  <div key={item.label} className="text-center p-4 rounded-lg bg-muted/50">
                    <div className={`h-2 ${item.color} rounded-full mb-3`} style={{ width: `${amdPct(item.value)}%`, margin: "0 auto" }} />
                    <p className="text-2xl font-bold">{item.value}</p>
                    <p className="text-sm text-muted-foreground">{item.label} · {amdPct(item.value)}%</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
