"use client";

import { useEffect, useState } from "react";
import { Mail, Send, FileText, Zap, Clock, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

type EmailStats = { sent: number; delivered: number; opened: number; campaigns: number };

const TABS = [
  { id: "dashboard", label: "Dashboard", icon: Mail },
  { id: "campaigns", label: "Campanhas", icon: Send },
  { id: "templates", label: "Templates", icon: FileText },
  { id: "automations", label: "Automações", icon: Zap },
  { id: "history", label: "Histórico", icon: Clock },
];

export default function EmailPage() {
  const [tab, setTab] = useState("dashboard");
  const [stats, setStats] = useState<EmailStats | null>(null);
  const [campaigns, setCampaigns] = useState<{ id: number; name: string; status: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [dash, camps] = await Promise.all([
          apiFetch<EmailStats>("/api/email/dashboard"),
          apiFetch<{ id: number; name: string; status: string }[]>("/api/email/campaigns"),
        ]);
        setStats(dash);
        setCampaigns(camps);
      } catch {
        setApiError(true);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" /></div>;

  if (apiError) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Email Marketing</h1>
        <div className="rounded-xl border p-8 text-center text-muted-foreground">
          <Mail className="h-10 w-10 mx-auto mb-3 opacity-50" />
          <p>Módulo de email em configuração.</p>
          <p className="text-sm mt-2">Configure domínio Resend em Configurações quando disponível.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Email Marketing</h1>
        <p className="text-muted-foreground text-sm mt-1">Campanhas, templates e automações de email</p>
      </div>

      <div className="flex gap-2 flex-wrap">
        {TABS.map((t) => (
          <Button key={t.id} size="sm" variant={tab === t.id ? "default" : "outline"} onClick={() => setTab(t.id)}>
            <t.icon className="h-4 w-4 mr-1" />{t.label}
          </Button>
        ))}
      </div>

      {tab === "dashboard" && stats && (
        <div className="grid sm:grid-cols-4 gap-4">
          {[
            { label: "Enviados", value: stats.sent },
            { label: "Entregues", value: stats.delivered },
            { label: "Abertos", value: stats.opened },
            { label: "Campanhas", value: stats.campaigns },
          ].map((s) => (
            <div key={s.label} className="rounded-xl border p-5">
              <p className="text-sm text-muted-foreground">{s.label}</p>
              <p className="text-2xl font-bold mt-1">{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {tab === "campaigns" && (
        <div className="rounded-xl border divide-y">
          {campaigns.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">Nenhuma campanha de email</div>
          ) : campaigns.map((c) => (
            <div key={c.id} className="flex items-center justify-between p-4">
              <span className="font-medium">{c.name}</span>
              <Badge>{c.status}</Badge>
            </div>
          ))}
        </div>
      )}

      {tab !== "dashboard" && tab !== "campaigns" && (
        <div className="rounded-xl border p-8 text-center text-muted-foreground">
          Seção {tab} — acesse via API /api/email/{tab}
        </div>
      )}
    </div>
  );
}
