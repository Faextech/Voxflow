"use client";

import { useEffect, useState, useCallback } from "react";
import { Shield, Building2, Users, Phone, Loader2, Plus } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { formatCurrency, formatDate } from "@/lib/utils";
import { toast } from "sonner";
import { useAuth } from "@/providers/auth-provider";

type Company = {
  id: number;
  name: string;
  email: string;
  plan: string;
  status: string;
  balance: number;
  created_at: string;
};

type AdminStats = {
  total_companies: number;
  active_companies: number;
  total_users: number;
  twilio_balance?: string;
};

export default function AdminPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteCode, setInviteCode] = useState("");

  const load = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([
        apiFetch<AdminStats>("/api/admin/dashboard"),
        apiFetch<{ companies: Company[] }>("/api/admin/companies"),
      ]);
      setStats(s);
      setCompanies(c.companies || []);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Acesso negado");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (user?.role === "superadmin") load(); else setLoading(false); }, [user, load]);

  const createInvite = async () => {
    try {
      const data = await apiFetch<{ code: string }>("/api/admin/invite-codes", {
        method: "POST",
        body: JSON.stringify({}),
      });
      setInviteCode(data.code);
      toast.success("Código de convite criado");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro");
    }
  };

  if (user?.role !== "superadmin") {
    return (
      <div className="text-center py-16 text-muted-foreground">
        <Shield className="h-10 w-10 mx-auto mb-3 opacity-50" />
        Acesso restrito a superadministradores
      </div>
    );
  }

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" /></div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Admin Plataforma</h1>
        <p className="text-muted-foreground text-sm mt-1">Gestão de empresas, convites e Twilio master</p>
      </div>

      {stats && (
        <div className="grid sm:grid-cols-4 gap-4">
          {[
            { label: "Empresas", value: stats.total_companies, icon: Building2 },
            { label: "Ativas", value: stats.active_companies, icon: Building2 },
            { label: "Usuários", value: stats.total_users, icon: Users },
            { label: "Twilio Master", value: stats.twilio_balance || "—", icon: Phone },
          ].map((s) => (
            <div key={s.label} className="rounded-xl border p-5">
              <s.icon className="h-4 w-4 text-primary mb-2" />
              <p className="text-2xl font-bold">{s.value}</p>
              <p className="text-sm text-muted-foreground">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-3">
        <Button onClick={createInvite}><Plus className="h-4 w-4 mr-1" />Novo convite</Button>
        {inviteCode && (
          <div className="flex items-center gap-2 rounded-lg border px-3 py-2 bg-muted/50">
            <span className="font-mono font-bold">{inviteCode}</span>
            <Button size="sm" variant="ghost" onClick={() => { navigator.clipboard.writeText(inviteCode); toast.success("Copiado"); }}>Copiar</Button>
          </div>
        )}
      </div>

      <div className="rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="text-left p-3">Empresa</th>
              <th className="text-left p-3">Plano</th>
              <th className="text-left p-3">Status</th>
              <th className="text-left p-3">Saldo</th>
              <th className="text-left p-3">Criada</th>
            </tr>
          </thead>
          <tbody>
            {companies.map((c) => (
              <tr key={c.id} className="border-b hover:bg-muted/30">
                <td className="p-3">
                  <p className="font-medium">{c.name}</p>
                  <p className="text-xs text-muted-foreground">{c.email}</p>
                </td>
                <td className="p-3"><Badge variant="secondary">{c.plan || "standard"}</Badge></td>
                <td className="p-3"><Badge variant={c.status === "active" ? "success" : "destructive"}>{c.status}</Badge></td>
                <td className="p-3">{formatCurrency(c.balance)}</td>
                <td className="p-3 text-muted-foreground">{formatDate(c.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
