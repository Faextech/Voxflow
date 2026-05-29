"use client";

import { useEffect, useState, useCallback } from "react";
import { LifeBuoy, Plus, Send, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import { toast } from "sonner";

type Ticket = {
  id: number;
  title: string;
  status: string;
  priority: string;
  category: string;
  created_at: string;
  updated_at: string;
};

type Message = { id: number; body: string; author_name: string; created_at: string; is_staff: boolean };

const statusLabel: Record<string, string> = {
  open: "Aberto", in_progress: "Em andamento", resolved: "Resolvido", closed: "Fechado",
};

export default function SupportPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newBody, setNewBody] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<{ tickets: Ticket[] }>("/api/support/tickets");
      setTickets(data.tickets || []);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, []);

  const loadMessages = useCallback(async (id: number) => {
    const data = await apiFetch<{ messages: Message[] }>(`/api/support/tickets/${id}/messages`);
    setMessages(data.messages || []);
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (selected) loadMessages(selected); }, [selected, loadMessages]);

  const createTicket = async () => {
    try {
      await apiFetch("/api/support/tickets", {
        method: "POST",
        body: JSON.stringify({ title: newTitle, body: newBody, category: "geral", priority: "medium" }),
      });
      toast.success("Ticket criado");
      setShowNew(false);
      setNewTitle("");
      setNewBody("");
      load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro");
    }
  };

  const sendReply = async () => {
    if (!selected || !reply.trim()) return;
    try {
      await apiFetch(`/api/support/tickets/${selected}/messages`, {
        method: "POST",
        body: JSON.stringify({ body: reply }),
      });
      setReply("");
      loadMessages(selected);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Suporte</h1>
          <p className="text-muted-foreground text-sm mt-1">Central de tickets e atendimento</p>
        </div>
        <Button onClick={() => setShowNew(true)}><Plus className="h-4 w-4 mr-1" />Novo Ticket</Button>
      </div>

      {showNew && (
        <div className="rounded-xl border p-4 space-y-3">
          <Label>Título</Label>
          <Input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
          <Label>Descrição</Label>
          <textarea className="w-full min-h-[100px] rounded-md border p-2 text-sm" value={newBody} onChange={(e) => setNewBody(e.target.value)} />
          <div className="flex gap-2">
            <Button onClick={createTicket} disabled={!newTitle}>Criar</Button>
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancelar</Button>
          </div>
        </div>
      )}

      <div className="flex gap-4 min-h-[400px]">
        <div className="w-80 rounded-xl border overflow-y-auto">
          {loading ? (
            <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin" /></div>
          ) : tickets.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground"><LifeBuoy className="h-8 w-8 mx-auto mb-2 opacity-50" />Nenhum ticket</div>
          ) : tickets.map((t) => (
            <button key={t.id} onClick={() => setSelected(t.id)}
              className={`w-full text-left p-3 border-b hover:bg-muted/50 ${selected === t.id ? "bg-muted" : ""}`}>
              <p className="font-medium text-sm truncate">{t.title}</p>
              <div className="flex gap-2 mt-1">
                <Badge variant="secondary" className="text-[10px]">{statusLabel[t.status] || t.status}</Badge>
                <span className="text-[10px] text-muted-foreground">{formatDate(t.created_at)}</span>
              </div>
            </button>
          ))}
        </div>

        <div className="flex-1 rounded-xl border flex flex-col">
          {selected ? (
            <>
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.map((m) => (
                  <div key={m.id} className={`${m.is_staff ? "bg-primary/5 border-l-2 border-primary" : "bg-muted/50"} rounded-lg p-3`}>
                    <p className="text-xs font-medium mb-1">{m.author_name} · {formatDate(m.created_at)}</p>
                    <p className="text-sm">{m.body}</p>
                  </div>
                ))}
              </div>
              <div className="p-3 border-t flex gap-2">
                <Input placeholder="Responder..." value={reply} onChange={(e) => setReply(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendReply()} />
                <Button onClick={sendReply}><Send className="h-4 w-4" /></Button>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">Selecione um ticket</div>
          )}
        </div>
      </div>
    </div>
  );
}
