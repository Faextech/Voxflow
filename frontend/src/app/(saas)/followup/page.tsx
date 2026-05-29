"use client";

import { useEffect, useState, useCallback } from "react";
import { Repeat, Plus, Trash2, Check, SkipForward, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { formatDate, formatPhone } from "@/lib/utils";
import { toast } from "sonner";

type Sequence = {
  id: number;
  name: string;
  trigger_disposition: string;
  is_active: boolean;
  steps: { delay_minutes: number; action: string; template: string }[];
};

type Task = {
  id: number;
  lead_name: string | null;
  lead_phone: string | null;
  sequence_name: string | null;
  action: string;
  scheduled_at: string;
  status: string;
};

export default function FollowupPage() {
  const [sequences, setSequences] = useState<Sequence[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"tasks" | "sequences">("tasks");
  const [newName, setNewName] = useState("");
  const [newTrigger, setNewTrigger] = useState("no_answer");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [seqs, taskData] = await Promise.all([
        apiFetch<Sequence[]>("/api/followup/sequences"),
        apiFetch<{ tasks: Task[] }>("/api/followup/tasks?status=pending"),
      ]);
      setSequences(seqs);
      setTasks(taskData.tasks || []);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const createSequence = async () => {
    try {
      await apiFetch("/api/followup/sequences", {
        method: "POST",
        body: JSON.stringify({
          name: newName,
          trigger_disposition: newTrigger,
          steps: [{ delay_minutes: 60, action: "email", template: "Olá {{name}}, retornamos sua ligação." }],
        }),
      });
      toast.success("Sequência criada");
      setNewName("");
      load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro");
    }
  };

  const deleteSeq = async (id: number) => {
    await apiFetch(`/api/followup/sequences/${id}`, { method: "DELETE" });
    load();
  };

  const markSent = async (id: number) => {
    await apiFetch(`/api/followup/tasks/${id}/mark-sent`, { method: "POST" });
    load();
  };

  const skipTask = async (id: number) => {
    await apiFetch(`/api/followup/tasks/${id}/skip`, { method: "POST" });
    load();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Follow-up Automático</h1>
        <p className="text-muted-foreground text-sm mt-1">Sequências pós-chamada e tarefas pendentes</p>
      </div>

      <div className="flex gap-2">
        <Button variant={tab === "tasks" ? "default" : "outline"} size="sm" onClick={() => setTab("tasks")}>
          Tarefas pendentes ({tasks.length})
        </Button>
        <Button variant={tab === "sequences" ? "default" : "outline"} size="sm" onClick={() => setTab("sequences")}>
          Sequências ({sequences.length})
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : tab === "tasks" ? (
        <div className="rounded-xl border divide-y">
          {tasks.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">Nenhuma tarefa pendente</div>
          ) : tasks.map((t) => (
            <div key={t.id} className="flex items-center justify-between p-4">
              <div>
                <p className="font-medium">{t.lead_name || "Lead"} · {formatPhone(t.lead_phone || "")}</p>
                <p className="text-sm text-muted-foreground">{t.sequence_name} · {t.action} · {formatDate(t.scheduled_at)}</p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => markSent(t.id)}><Check className="h-4 w-4 mr-1" />Enviado</Button>
                <Button size="sm" variant="ghost" onClick={() => skipTask(t.id)}><SkipForward className="h-4 w-4" /></Button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-xl border p-4 grid md:grid-cols-3 gap-3">
            <div><Label>Nome</Label><Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Retorno 24h" /></div>
            <div>
              <Label>Disparo quando</Label>
              <select className="w-full h-10 rounded-md border px-3 text-sm mt-1" value={newTrigger} onChange={(e) => setNewTrigger(e.target.value)}>
                <option value="no_answer">Não atendeu</option>
                <option value="voicemail">Caixa postal</option>
                <option value="busy">Ocupado</option>
                <option value="completed">Atendeu</option>
              </select>
            </div>
            <div className="flex items-end">
              <Button onClick={createSequence} disabled={!newName}><Plus className="h-4 w-4 mr-1" />Criar</Button>
            </div>
          </div>
          <div className="rounded-xl border divide-y">
            {sequences.map((s) => (
              <div key={s.id} className="flex items-center justify-between p-4">
                <div>
                  <p className="font-medium flex items-center gap-2">
                    <Repeat className="h-4 w-4" />{s.name}
                    <Badge variant={s.is_active ? "success" : "secondary"}>{s.is_active ? "Ativa" : "Inativa"}</Badge>
                  </p>
                  <p className="text-sm text-muted-foreground">Trigger: {s.trigger_disposition} · {s.steps?.length || 0} passos</p>
                </div>
                <Button variant="ghost" size="icon" onClick={() => deleteSeq(s.id)}><Trash2 className="h-4 w-4 text-destructive" /></Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
