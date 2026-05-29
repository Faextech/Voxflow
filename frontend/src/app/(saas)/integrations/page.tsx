"use client";

import { useEffect, useState } from "react";
import { Plug, ExternalLink, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

type Provider = { slug: string; name: string; description: string; connected: boolean };
type Connection = { id: number; provider: string; status: string; email?: string };

const NATIVE = [
  { name: "Twilio Voice", slug: "twilio", desc: "Discador e webphone WebRTC", connected: true },
  { name: "WhatsApp Business", slug: "whatsapp", desc: "Evolution API / Meta Cloud", connected: false },
  { name: "Email (Resend)", slug: "email", desc: "Campanhas e transacionais", connected: false },
];

export default function IntegrationsPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [p, c] = await Promise.all([
          apiFetch<{ providers: Provider[] }>("/api/v1/integrations/providers"),
          apiFetch<{ connections: Connection[] }>("/api/v1/integrations/connections"),
        ]);
        setProviders(p.providers || []);
        setConnections(c.connections || []);
      } catch {
        setApiError(true);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const connect = async (slug: string) => {
    try {
      const data = await apiFetch<{ url: string }>(`/api/v1/integrations/oauth/${slug}/authorize`);
      window.location.href = data.url;
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "OAuth não configurado");
    }
  };

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" /></div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Integrações</h1>
        <p className="text-muted-foreground text-sm mt-1">Conecte canais de comunicação e ferramentas externas</p>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {NATIVE.map((n) => (
          <div key={n.slug} className="rounded-xl border bg-card p-5">
            <div className="flex items-center justify-between mb-3">
              <Plug className="h-5 w-5 text-primary" />
              <Badge variant={n.connected ? "success" : "secondary"}>
                {n.connected ? <><CheckCircle2 className="h-3 w-3 mr-1" />Ativo</> : "Pendente"}
              </Badge>
            </div>
            <h3 className="font-semibold">{n.name}</h3>
            <p className="text-sm text-muted-foreground mt-1">{n.desc}</p>
            {!n.connected && n.slug !== "twilio" && (
              <Button size="sm" variant="outline" className="mt-3" onClick={() => toast.info("Configure em Configurações → Twilio/Evolution")}>
                Configurar
              </Button>
            )}
          </div>
        ))}
      </div>

      {!apiError && providers.length > 0 && (
        <div className="rounded-xl border">
          <div className="p-4 border-b font-semibold">OAuth Providers</div>
          <div className="divide-y">
            {providers.map((p) => (
              <div key={p.slug} className="flex items-center justify-between p-4">
                <div>
                  <p className="font-medium">{p.name}</p>
                  <p className="text-sm text-muted-foreground">{p.description}</p>
                </div>
                <Button size="sm" variant={p.connected ? "outline" : "default"} onClick={() => connect(p.slug)}>
                  {p.connected ? "Reconectar" : "Conectar"}<ExternalLink className="h-3 w-3 ml-1" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {connections.length > 0 && (
        <div className="rounded-xl border divide-y">
          <div className="p-4 font-semibold">Conexões ativas</div>
          {connections.map((c) => (
            <div key={c.id} className="flex items-center justify-between p-4">
              <span>{c.provider} {c.email && `· ${c.email}`}</span>
              <Badge variant={c.status === "active" ? "success" : "destructive"}>{c.status}</Badge>
            </div>
          ))}
        </div>
      )}

      {apiError && (
        <div className="rounded-xl border p-6 text-center text-muted-foreground">
          <XCircle className="h-8 w-8 mx-auto mb-2 opacity-50" />
          API Enterprise v1 em configuração. Twilio Voice já funciona via Configurações.
        </div>
      )}
    </div>
  );
}
