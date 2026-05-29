"use client";

import { useEffect, useState, useCallback } from "react";
import { Ban, Plus, Trash2, Search, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDate, formatPhone } from "@/lib/utils";
import { toast } from "sonner";

type DncEntry = { id: number; phone: string; reason: string; created_at: string };

export default function DncPage() {
  const [items, setItems] = useState<DncEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [phone, setPhone] = useState("");
  const [bulk, setBulk] = useState("");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<{ items: DncEntry[]; total: number }>("/api/dnc");
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const addPhone = async (phones: string[]) => {
    try {
      await apiFetch("/api/dnc", { method: "POST", body: JSON.stringify({ phones, reason: "manual" }) });
      toast.success(`${phones.length} número(s) adicionado(s)`);
      setPhone("");
      setBulk("");
      load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro");
    }
  };

  const remove = async (id: number) => {
    try {
      await apiFetch(`/api/dnc/${id}`, { method: "DELETE" });
      load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro");
    }
  };

  const filtered = items.filter((i) => !search || i.phone.includes(search));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">DNC — Do Not Call</h1>
        <p className="text-muted-foreground text-sm mt-1">Blacklist de números bloqueados para discagem</p>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="rounded-xl border p-4 space-y-3">
          <Label>Adicionar número</Label>
          <div className="flex gap-2">
            <Input placeholder="+5511999999999" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <Button onClick={() => phone && addPhone([phone])}><Plus className="h-4 w-4" /></Button>
          </div>
        </div>
        <div className="rounded-xl border p-4 space-y-3">
          <Label>Importar em lote (um por linha)</Label>
          <textarea className="w-full min-h-[80px] rounded-md border p-2 text-sm" value={bulk}
            onChange={(e) => setBulk(e.target.value)} placeholder="+5511...\n+5521..." />
          <Button variant="outline" size="sm" onClick={() => {
            const phones = bulk.split("\n").map((p) => p.trim()).filter(Boolean);
            if (phones.length) addPhone(phones);
          }}>Importar lote</Button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input className="pl-9" placeholder="Buscar número..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <span className="text-sm text-muted-foreground">{total} números bloqueados</span>
        <Button variant="outline" size="sm" onClick={() => window.open("/api/analytics/export/dnc", "_blank")}>Exportar CSV</Button>
      </div>

      <div className="rounded-xl border bg-card">
        {loading ? (
          <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" /></div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-muted-foreground"><Ban className="h-8 w-8 mx-auto mb-2 opacity-50" />Lista vazia</div>
        ) : (
          <div className="divide-y">
            {filtered.map((e) => (
              <div key={e.id} className="flex items-center justify-between p-3 hover:bg-muted/30">
                <div>
                  <p className="font-mono font-medium">{formatPhone(e.phone)}</p>
                  <p className="text-xs text-muted-foreground">{e.reason} · {formatDate(e.created_at)}</p>
                </div>
                <Button variant="ghost" size="icon" onClick={() => remove(e.id)}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
