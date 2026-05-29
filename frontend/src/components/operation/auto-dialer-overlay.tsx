"use client";

import { useEffect, useState } from "react";
import { Phone, Pause, Play, SkipForward, Square, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useSocket } from "@/providers/socket-provider";

type DialerStatus = {
  running: boolean;
  paused: boolean;
  campaign_id: number;
  campaign_name?: string;
  current_lead?: { id: number; name: string; phone: string };
  stats?: { dialed: number; answered: number; remaining: number };
};

export function AutoDialerOverlay() {
  const [status, setStatus] = useState<DialerStatus | null>(null);
  const [visible, setVisible] = useState(false);
  const { socket } = useSocket();

  const loadStatus = async (campaignId?: number) => {
    if (!campaignId) return;
    try {
      const data = await apiFetch<DialerStatus>(`/api/dialer/auto/status/${campaignId}`);
      setStatus(data);
      setVisible(data.running);
    } catch {
      setVisible(false);
    }
  };

  useEffect(() => {
    if (!socket) return;
    const handler = (data: DialerStatus & { type?: string }) => {
      if (data.running !== undefined) {
        setStatus(data);
        setVisible(data.running);
      }
    };
    socket.on("dialer_status", handler);
    return () => { socket.off("dialer_status", handler); };
  }, [socket]);

  const action = async (endpoint: string) => {
    try {
      await apiFetch(`/api/dialer/auto/${endpoint}`, { method: "POST", body: JSON.stringify({ campaign_id: status?.campaign_id }) });
    } catch { /* ignore */ }
  };

  if (!visible || !status) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 rounded-xl border bg-card shadow-2xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Phone className="h-4 w-4 text-primary animate-pulse" />
          <span className="font-semibold text-sm">Auto-Dialer</span>
        </div>
        <Badge variant={status.paused ? "warning" : "success"}>{status.paused ? "Pausado" : "Ativo"}</Badge>
      </div>

      {status.current_lead && (
        <div className="rounded-lg bg-muted/50 p-2 text-sm">
          <p className="font-medium">{status.current_lead.name}</p>
          <p className="text-muted-foreground">{status.current_lead.phone}</p>
        </div>
      )}

      {status.stats && (
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div><p className="font-bold">{status.stats.dialed}</p><p className="text-muted-foreground">Discados</p></div>
          <div><p className="font-bold">{status.stats.answered}</p><p className="text-muted-foreground">Atendidos</p></div>
          <div><p className="font-bold">{status.stats.remaining}</p><p className="text-muted-foreground">Restantes</p></div>
        </div>
      )}

      <div className="flex gap-2">
        <Button size="sm" variant="outline" onClick={() => action(status.paused ? "resume" : "pause")}>
          {status.paused ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
        </Button>
        <Button size="sm" variant="outline" onClick={() => action("next")}><SkipForward className="h-3 w-3" /></Button>
        <Button size="sm" variant="outline" onClick={() => action("skip_phone")}>Pular tel</Button>
        <Button size="sm" variant="destructive" onClick={() => { action("stop"); setVisible(false); }}>
          <Square className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}
