"use client";

import { useEffect, useState, useCallback } from "react";
import { PhoneForwarded, Trash2, Loader2, Calendar } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate, formatPhone } from "@/lib/utils";
import { toast } from "sonner";

type Callback = {
  id: number;
  lead_id: number;
  lead_name?: string;
  lead_phone?: string;
  campaign_id: number;
  priority: number;
  status: string;
  notes: string | null;
  scheduled_for: string;
};

export default function CallbacksPage() {
  const [items, setItems] = useState<Callback[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("pending");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<{ callbacks: Callback[] }>(`/api/callbacks?status=${filter}`);
      setItems(data.callbacks || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const cancel = async (id: number) => {
    try {
      await apiFetch(`/api/callbacks/${id}`, { method: "DELETE" });
      toast.success("Retorno cancelado");
      load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao cancelar");
    }
  };

  const priorityLabel = (p: number) => (p >= 3 ? "Alta" : p >= 2 ? "Média" : "Normal");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Fila de Retornos</h1>
        <p className="text-muted-foreground text-sm mt-1">Callbacks agendados por operadores</p>
      </div>

      <div className="flex gap-2">
        {["pending", "completed", "canceled", "all"].map((s) => (
          <Button key={s} variant={filter === s ? "default" : "outline"} size="sm" onClick={() => setFilter(s)}>
            {s === "pending" ? "Pendentes" : s === "completed" ? "Concluídos" : s === "canceled" ? "Cancelados" : "Todos"}
          </Button>
        ))}
      </div>

      <div className="rounded-xl border bg-card">
        {loading ? (
          <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" /></div>
        ) : items.length === 0 ? (
          <div className="text-center py-16 text-muted-foreground">Nenhum retorno na fila</div>
        ) : (
          <div className="divide-y">
            {items.map((cb) => (
              <div key={cb.id} className="flex items-center justify-between p-4 hover:bg-muted/30">
                <div className="flex items-start gap-3">
                  <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
                    <PhoneForwarded className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="font-medium">{cb.lead_name || `Lead #${cb.lead_id}`}</p>
                    <p className="text-sm text-muted-foreground">{formatPhone(cb.lead_phone || "")}</p>
                    {cb.notes && <p className="text-xs text-muted-foreground mt-1">{cb.notes}</p>}
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right text-sm">
                    <Badge variant={cb.priority >= 3 ? "destructive" : "secondary"}>{priorityLabel(cb.priority)}</Badge>
                    <p className="text-muted-foreground mt-1 flex items-center gap-1 justify-end">
                      <Calendar className="h-3 w-3" />{formatDate(cb.scheduled_for)}
                    </p>
                  </div>
                  {cb.status === "pending" && (
                    <Button variant="ghost" size="icon" onClick={() => cancel(cb.id)}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
