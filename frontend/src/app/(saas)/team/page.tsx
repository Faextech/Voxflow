"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Users,
  Plus,
  Search,
  Trash2,
  Shield,
  Mail,
  Calendar,
  X,
  Loader2,
  ShieldAlert,
  Edit,
  UserCheck,
  Crown,
  Key,
  ShieldCheck,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { formatDate } from "@/lib/utils";

type UserMember = {
  id: number;
  company_id: number;
  email: string;
  name: string;
  role: string; // admin, agent, supervisor, etc.
  created_at: string;
  updated_at: string;
};

const roleConfig: Record<string, { label: string; variant: "default" | "secondary" | "success" | "warning" | "destructive" | "outline" | "info"; icon: any }> = {
  admin: { label: "Administrador", variant: "default", icon: Crown },
  agent: { label: "Agente / Operador", variant: "secondary", icon: UserCheck },
  operator: { label: "Agente / Operador", variant: "secondary", icon: UserCheck },
  supervisor: { label: "Supervisor", variant: "info", icon: Shield },
};

export default function TeamPage() {
  const [members, setMembers] = useState<UserMember[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  // Modals & form state
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<UserMember | null>(null);

  // User form data
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: "",
    role: "agent",
  });

  // Load team members
  const loadMembers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/users");
      if (res.ok) {
        const data = await res.json();
        setMembers(data.users || data);
      } else {
        toast.error("Erro ao obter membros do time");
      }
    } catch (e) {
      console.error(e);
      toast.error("Erro na comunicação com o servidor");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMembers();
  }, [loadMembers]);

  // Create member
  const handleCreateMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.email || !formData.password) {
      toast.error("Preencha todos os campos obrigatórios");
      return;
    }
    setActionLoading(true);
    try {
      const res = await fetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      const data = await res.json();
      if (res.ok) {
        toast.success("Novo membro adicionado ao time com sucesso!");
        setCreateOpen(false);
        setFormData({ name: "", email: "", password: "", role: "agent" });
        loadMembers();
      } else {
        toast.error(data.error || "Falha ao adicionar membro");
      }
    } catch {
      toast.error("Erro ao enviar dados");
    } finally {
      setActionLoading(false);
    }
  };

  // Open Edit Role Dialog
  const handleOpenEdit = (member: UserMember) => {
    setSelectedMember(member);
    setFormData({
      name: member.name,
      email: member.email,
      password: "",
      role: member.role,
    });
    setEditOpen(true);
  };

  // Update Role
  const handleUpdateRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMember) return;
    setActionLoading(true);
    try {
      const res = await fetch(`/api/users/${selectedMember.id}/role`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: formData.role }),
      });

      const data = await res.json();
      if (res.ok) {
        toast.success("Privilégios do membro atualizados!");
        setEditOpen(false);
        loadMembers();
      } else {
        toast.error(data.error || "Falha ao atualizar privilégios");
      }
    } catch {
      toast.error("Erro na comunicação");
    } finally {
      setActionLoading(false);
    }
  };

  // Delete Member
  const handleDeleteMember = async (memberId: number) => {
    if (!confirm("Deseja mesmo remover permanentemente este membro do seu time? Ele perderá imediatamente todo o acesso ao VoxFlow.")) return;
    setActionLoading(true);
    try {
      const res = await fetch(`/api/users/${memberId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        toast.success("Membro removido do time com sucesso!");
        loadMembers();
      } else {
        const data = await res.json();
        toast.error(data.error || "Não foi possível excluir o membro");
      }
    } catch {
      toast.error("Erro na requisição");
    } finally {
      setActionLoading(false);
    }
  };

  // Filtered list
  const filteredMembers = members.filter((member) => {
    const term = search.toLowerCase();
    return (
      member.name.toLowerCase().includes(term) ||
      member.email.toLowerCase().includes(term) ||
      member.role.toLowerCase().includes(term)
    );
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-foreground flex items-center gap-2">
            <Users className="h-8 w-8 text-primary" />
            Time / Operadores
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Gerencie os usuários que possuem acesso ao painel do VoxFlow, defina funções (Administrador, Supervisor, Agente) e credenciais.
          </p>
        </div>
        <div>
          <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5 font-bold shadow-md shadow-primary/10">
            <Plus className="h-4 w-4" />
            Adicionar Membro
          </Button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="bg-card border border-border/50 rounded-2xl p-4 flex flex-wrap gap-4 items-center shadow-sm">
        <div className="relative flex-1 min-w-[280px]">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar por nome, e-mail ou cargo..."
            className="pl-10"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Button variant="outline" size="icon" onClick={loadMembers} title="Atualizar Lista" className="shrink-0 rounded-lg">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* Grid List */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((n) => (
            <Card key={n} className="animate-pulse bg-muted/10 border-border/50">
              <CardHeader className="h-20 bg-muted/20 border-b border-border/30" />
              <CardContent className="h-32 p-6 space-y-4">
                <div className="h-4 bg-muted/30 rounded w-1/2" />
                <div className="h-3 bg-muted/20 rounded w-3/4" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filteredMembers.length === 0 ? (
        <div className="text-center py-16 bg-card border rounded-2xl p-8 space-y-4 shadow-sm">
          <Users className="h-12 w-12 text-muted-foreground/60 mx-auto" />
          <div className="space-y-1">
            <h3 className="text-lg font-bold text-foreground">Nenhum membro encontrado</h3>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto">
              Adicione operadores e supervisores ao seu time para que eles possam utilizar o Webphone e atender as campanhas de voz.
            </p>
          </div>
          <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5 mt-2">
            <Plus className="h-4 w-4" />
            Adicionar Novo Operador
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredMembers.map((member) => {
            const role = member.role.toLowerCase();
            const config = roleConfig[role] || { label: member.role, variant: "outline" as const, icon: ShieldAlert };
            const RoleIcon = config.icon;

            return (
              <Card
                key={member.id}
                className="group hover:shadow-md transition-all duration-200 border-border/50 bg-card overflow-hidden flex flex-col justify-between"
              >
                <div>
                  {/* Top Bar with Badge */}
                  <div className="p-4 border-b bg-muted/10 group-hover:bg-muted/20 transition-colors flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-xs font-bold text-foreground">
                      <RoleIcon className="h-4 w-4 text-primary shrink-0" />
                      {config.label}
                    </span>
                    <Badge variant={config.variant} className="text-[9px] font-extrabold uppercase py-0.5 px-2">
                      {member.role}
                    </Badge>
                  </div>

                  {/* Body Info */}
                  <div className="p-5 space-y-3.5">
                    <div className="space-y-1">
                      <h3 className="text-base font-bold text-foreground leading-tight tracking-tight">
                        {member.name}
                      </h3>
                      <p className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
                        <Mail className="h-3.5 w-3.5" />
                        {member.email}
                      </p>
                    </div>

                    <div className="text-[10px] font-semibold text-muted-foreground flex items-center gap-1">
                      <Calendar className="h-3.5 w-3.5" />
                      Adicionado em: {formatDate(member.created_at)}
                    </div>
                  </div>
                </div>

                {/* Footer Controls */}
                <div className="px-5 py-3.5 bg-muted/10 border-t border-border/30 flex items-center justify-end gap-2 shrink-0">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 text-xs font-bold"
                    onClick={() => handleOpenEdit(member)}
                  >
                    Alterar Cargo
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-8 w-8 text-destructive hover:bg-destructive/10 p-0"
                    onClick={() => handleDeleteMember(member.id)}
                    disabled={actionLoading}
                    title="Excluir Operador"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Creation Modal */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setCreateOpen(false)} />
          <div className="relative bg-card rounded-2xl shadow-2xl border w-full max-w-md mx-4 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between p-6 border-b">
              <h2 className="text-lg font-black text-foreground tracking-tight">Novo Membro do Time</h2>
              <button onClick={() => setCreateOpen(false)} className="text-muted-foreground hover:text-foreground cursor-pointer">
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateMember} className="p-6 space-y-4">
              {/* Name */}
              <div className="space-y-1.5">
                <Label htmlFor="create-name">Nome Completo *</Label>
                <Input
                  id="create-name"
                  placeholder="Nome do Operador"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>

              {/* Email */}
              <div className="space-y-1.5">
                <Label htmlFor="create-email">E-mail *</Label>
                <Input
                  id="create-email"
                  type="email"
                  placeholder="email@empresa.com"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  required
                />
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <Label htmlFor="create-password">Senha de Acesso *</Label>
                <Input
                  id="create-password"
                  type="password"
                  placeholder="Mínimo 6 caracteres"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  required
                />
              </div>

              {/* Role Selection */}
              <div className="space-y-1.5">
                <Label htmlFor="create-role">Função no Sistema *</Label>
                <select
                  id="create-role"
                  className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                >
                  <option value="agent">Agente / Operador (Apenas Webphone)</option>
                  <option value="supervisor">Supervisor (Acompanha relatórios e campanhas)</option>
                  <option value="admin">Administrador (Acesso total)</option>
                </select>
              </div>

              <div className="flex gap-3 pt-4 border-t">
                <Button type="button" variant="outline" className="flex-1 font-bold" onClick={() => setCreateOpen(false)}>
                  Cancelar
                </Button>
                <Button type="submit" className="flex-1 font-bold shadow-md shadow-primary/10" loading={actionLoading}>
                  Adicionar Membro
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Role Modal */}
      {editOpen && selectedMember && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setEditOpen(false)} />
          <div className="relative bg-card rounded-2xl shadow-2xl border w-full max-w-md mx-4 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between p-6 border-b">
              <h2 className="text-lg font-black text-foreground tracking-tight">Alterar Cargo / Nível de Acesso</h2>
              <button onClick={() => setEditOpen(false)} className="text-muted-foreground hover:text-foreground cursor-pointer">
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleUpdateRole} className="p-6 space-y-4">
              <div className="space-y-1.5 p-3 rounded-xl bg-muted/40 border">
                <p className="text-xs font-semibold text-muted-foreground leading-none">Membro selecionado:</p>
                <h4 className="text-sm font-bold text-foreground mt-1.5">{selectedMember.name}</h4>
                <p className="text-xs text-muted-foreground font-mono mt-0.5">{selectedMember.email}</p>
              </div>

              {/* Role Selection */}
              <div className="space-y-1.5">
                <Label htmlFor="edit-role">Função / Privilégios</Label>
                <select
                  id="edit-role"
                  className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                >
                  <option value="agent">Agente / Operador (Apenas Webphone)</option>
                  <option value="supervisor">Supervisor (Acompanha relatórios e campanhas)</option>
                  <option value="admin">Administrador (Acesso total)</option>
                </select>
              </div>

              <div className="flex gap-3 pt-4 border-t">
                <Button type="button" variant="outline" className="flex-1 font-bold" onClick={() => setEditOpen(false)}>
                  Cancelar
                </Button>
                <Button type="submit" className="flex-1 font-bold" loading={actionLoading}>
                  Salvar Alterações
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
