"use client";

import { useEffect, useState, useCallback } from "react";
import { Eye, Headphones, MessageSquare, Loader2, RefreshCw } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

type Agent = {
  id: number;
  name: string;
  status: string;
  last_active: string | null;
  active_call?: {
    conference_name: string;
    lead_name: string;
    phone_number: string;
    status: string;
  };
};

const statusColor: Record<string, string> = {
  available: "success",
  busy: "warning",
  on_call: "destructive",
  offline: "secondary",
  break: "outline",
};

export default function SupervisorPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalConfs, setTotalConfs] = useState(0);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<{ agents: Agent[]; total_active_conferences: number }>("/api/supervisor/realtime");
      setAgents(data.agents);
      setTotalConfs(data.total_active_conferences);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Acesso negado");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 5000);
    return () => clearInterval(iv);
  }, [load]);

  const listenLive = async (conferenceName: string) => {
    try {
      await apiFetch("/api/supervisor/listen-live", {
        method: "POST",
        body: JSON.stringify({ conference_name: conferenceName }),
      });
      toast.success("Modo escuta ativado — verifique seu webphone");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro");
    }
  };

  const whisper = async (conferenceName: string) => {
    try {
      await apiFetch("/api/supervisor/whisper", {
        method: "POST",
        body: JSON.stringify({ conference_name: conferenceName }),
      });
      toast.success("Whisper ativado — só o agente ouve você");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Supervisor em Tempo Real</h1>
          <p className="text-muted-foreground text-sm mt-1">{totalConfs} conferências ativas · atualiza a cada 5s</p>
        </div>
        <Button variant="outline" size="sm" onClick={load}><RefreshCw className="h-4 w-4 mr-1" />Atualizar</Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((a) => (
            <div key={a.id} className="rounded-xl border bg-card p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold">{a.name}</p>
                  <p className="text-xs text-muted-foreground">Agent #{a.id}</p>
                </div>
                <Badge variant={(statusColor[a.status] || "secondary") as "success"}>{a.status}</Badge>
              </div>

              {a.active_call ? (
                <div className="rounded-lg bg-muted/50 p-3 space-y-2">
                  <p className="text-sm font-medium">{a.active_call.lead_name}</p>
                  <p className="text-xs text-muted-foreground">{a.active_call.phone_number}</p>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => listenLive(a.active_call!.conference_name)}>
                      <Headphones className="h-3 w-3 mr-1" />Escutar
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => whisper(a.active_call!.conference_name)}>
                      <MessageSquare className="h-3 w-3 mr-1" />Whisper
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground flex items-center gap-1">
                  <Eye className="h-3 w-3" />Sem chamada ativa
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
