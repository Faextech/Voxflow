"use client";

import { useEffect, useState, useCallback } from "react";
import { MessageSquare, Send, Loader2, Search } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { formatRelativeTime } from "@/lib/utils";
import { toast } from "sonner";

type Conversation = {
  id: string;
  contact_name: string;
  contact_phone: string;
  last_message: string;
  last_message_at: string;
  unread_count: number;
  status: string;
};

type Message = {
  id: string;
  body: string;
  direction: "inbound" | "outbound";
  created_at: string;
};

export default function InboxPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [reply, setReply] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(false);

  const loadConversations = useCallback(async () => {
    try {
      const data = await apiFetch<{ conversations: Conversation[] }>("/api/v1/whatsapp/conversations");
      setConversations(data.conversations || []);
      setApiError(false);
    } catch {
      setApiError(true);
      setConversations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMessages = useCallback(async (id: string) => {
    try {
      const data = await apiFetch<{ messages: Message[] }>(`/api/v1/whatsapp/conversations/${id}/messages`);
      setMessages(data.messages || []);
    } catch {
      setMessages([]);
    }
  }, []);

  useEffect(() => { loadConversations(); }, [loadConversations]);
  useEffect(() => { if (selected) loadMessages(selected); }, [selected, loadMessages]);

  const sendMessage = async () => {
    if (!selected || !reply.trim()) return;
    try {
      await apiFetch(`/api/v1/whatsapp/conversations/${selected}/messages`, {
        method: "POST",
        body: JSON.stringify({ body: reply }),
      });
      setReply("");
      loadMessages(selected);
      toast.success("Mensagem enviada");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao enviar");
    }
  };

  const filtered = conversations.filter((c) =>
    !search || c.contact_name?.toLowerCase().includes(search.toLowerCase()) || c.contact_phone?.includes(search)
  );

  if (apiError) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">WhatsApp Inbox</h1>
        <div className="rounded-xl border p-8 text-center text-muted-foreground">
          <MessageSquare className="h-10 w-10 mx-auto mb-3 opacity-50" />
          <p>WhatsApp Inbox requer integração Evolution API configurada.</p>
          <p className="text-sm mt-2">Configure em <a href="/integrations" className="text-primary underline">Integrações</a>.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      <h1 className="text-2xl font-bold mb-4">WhatsApp Inbox</h1>
      <div className="flex flex-1 rounded-xl border overflow-hidden min-h-0">
        <div className="w-80 border-r flex flex-col">
          <div className="p-3 border-b">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input className="pl-8 h-9" placeholder="Buscar..." value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin" /></div>
            ) : filtered.map((c) => (
              <button key={c.id} onClick={() => setSelected(c.id)}
                className={`w-full text-left p-3 border-b hover:bg-muted/50 ${selected === c.id ? "bg-muted" : ""}`}>
                <div className="flex justify-between">
                  <span className="font-medium text-sm truncate">{c.contact_name || c.contact_phone}</span>
                  {c.unread_count > 0 && <Badge variant="destructive" className="text-xs">{c.unread_count}</Badge>}
                </div>
                <p className="text-xs text-muted-foreground truncate mt-1">{c.last_message}</p>
                <p className="text-[10px] text-muted-foreground mt-1">{formatRelativeTime(c.last_message_at)}</p>
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 flex flex-col">
          {selected ? (
            <>
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.map((m) => (
                  <div key={m.id} className={`flex ${m.direction === "outbound" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[70%] rounded-lg px-3 py-2 text-sm ${m.direction === "outbound" ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
                      {m.body}
                      <p className="text-[10px] opacity-70 mt-1">{formatRelativeTime(m.created_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="p-3 border-t flex gap-2">
                <Input placeholder="Digite sua mensagem..." value={reply} onChange={(e) => setReply(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendMessage()} />
                <Button onClick={sendMessage}><Send className="h-4 w-4" /></Button>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              Selecione uma conversa
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
