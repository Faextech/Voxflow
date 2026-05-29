"use client";

import { useEffect, useState } from "react";
import { Phone, Pause, Play, SkipForward, Square, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/providers/auth-provider";

type DialerStatus = {
  running: boolean;
  paused: boolean;
  campaign_id: number | null;
  campaign_name?: string;
  current_lead?: { id: number; name: string; phone: string };
  stats?: { dialed: number; answered: number; remaining: number };
};

export function AutoDialerBar() {
  const { user } = useAuth();
  const [status, setStatus] = useState<DialerStatus | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!user?.agent_id) return;
    const poll = async () => {
      try {
        const campaigns = await apiFetch<{ id: number; name: string; status: string }[]>("/api/campaigns");
        const active = campaigns.find((c) => c.status === "running" || c.status === "active");
        if (!active) { setStatus(null); return; }
        const st = await apiFetch<DialerStatus>(`/api/dialer/auto/status/${active.id}`);
        setStatus({ ...st, campaign_id: active.id, campaign_name: active.name });
      } catch { setStatus(null); }
    };
    poll();
    const iv = setInterval(poll, 3000);
    return () => clearInterval(iv);
  }, [user?.agent_id]);

  if (!status?.running && !status?.paused) return null;

  const action = async (endpoint: string) => {
    setLoading(true);
    try {
      await apiFetch(`/api/dialer/auto/${endpoint}`, {
        method: "POST",
        body: JSON.stringify({ campaign_id: status.campaign_id, agent_id: user?.agent_id }),
      });
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 bg-card border shadow-lg rounded-xl px-4 py-3 min-w-[400px]">
      <Phone className="h-4 w-4 text-primary animate-pulse" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{status.campaign_name}</p>
        {status.current_lead && (
          <p className="text-xs text-muted-foreground truncate">{status.current_lead.name} · {status.current_lead.phone}</p>
        )}
      </div>
      {status.stats && (
        <Badge variant="secondary" className="text-[10px]">{status.stats.dialed}/{status.stats.remaining + status.stats.dialed}</Badge>
      )}
      <div className="flex gap-1">
        {status.paused ? (
          <Button size="icon" variant="outline" className="h-8 w-8" onClick={() => action("resume")} disabled={loading}>
            <Play className="h-3 w-3" />
          </Button>
        ) : (
          <Button size="icon" variant="outline" className="h-8 w-8" onClick={() => action("pause")} disabled={loading}>
            <Pause className="h-3 w-3" />
          </Button>
        )}
        <Button size="icon" variant="outline" className="h-8 w-8" onClick={() => action("next")} disabled={loading}>
          <SkipForward className="h-3 w-3" />
        </Button>
        <Button size="icon" variant="destructive" className="h-8 w-8" onClick={() => action("stop")} disabled={loading}>
          <Square className="h-3 w-3" />
        </Button>
      </div>
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
    </div>
  );
}
