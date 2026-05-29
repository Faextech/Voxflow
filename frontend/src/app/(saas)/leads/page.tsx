"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Plus,
  Search,
  Filter,
  Phone,
  Mail,
  Building2,
  Tag,
  Clock,
  Trash2,
  X,
  FileText,
  Bookmark,
  Calendar,
  MessageCircle,
  HelpCircle,
  PhoneCall,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { formatDate, formatPhone } from "@/lib/utils";
import { toast } from "sonner";
import { Label } from "@/components/ui/label";

type Lead = {
  id: number;
  company_id: number;
  campaign_id: number;
  name: string;
  email: string | null;
  company_name: string | null;
  job_title: string | null;
  city: string | null;
  state: string | null;
  numero_1: string;
  numero_2: string | null;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

type Campaign = {
  id: number;
  name: string;
};

type TimelineEvent = {
  type: string;
  title: string;
  body: string | null;
  icon: string;
  color: string;
  created_at: string | null;
};

const statusConfig: Record<string, { label: string; variant: "default" | "secondary" | "success" | "warning" | "destructive" | "outline" | "info" }> = {
  new: { label: "Novo", variant: "secondary" },
  novo: { label: "Novo", variant: "secondary" },
  dialing: { label: "Discando", variant: "warning" },
  contacted: { label: "Contatado", variant: "info" },
  completed: { label: "Sucesso", variant: "success" },
  invalid: { label: "Inválido", variant: "destructive" },
  no_answer: { label: "Não atendeu", variant: "outline" },
  busy: { label: "Ocupado", variant: "outline" },
  voicemail: { label: "Caixa Postal", variant: "outline" },
};

export default function LeadsPage() {
  // Lists
  const [leads, setLeads] = useState<Lead[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);

  // Pagination & Filtering
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [search, setSearch] = useState("");
  const [selectedStatus, setSelectedStatus] = useState<string>("");
  const [selectedCampaign, setSelectedCampaign] = useState<string>("");

  // Modals & Drawers
  const [createOpen, setCreateOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [leadTimeline, setLeadTimeline] = useState<TimelineEvent[]>([]);

  // Loaders
  const [loadingList, setLoadingList] = useState(true);
  const [loadingTimeline, setLoadingTimeline] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Load Campaign list (for dropdown filtering and creation modal)
  useEffect(() => {
    async function loadCampaigns() {
      try {
        const res = await fetch("/api/campaigns");
        if (res.ok) {
          const data = await res.json();
          setCampaigns(data);
        }
      } catch (e) {
        console.error("Erro ao obter campanhas", e);
      }
    }
    loadCampaigns();
  }, []);

  // Main Lead load function
  const loadLeads = useCallback(async () => {
    setLoadingList(true);
    try {
      let url = `/api/leads?page=${currentPage}&per_page=15`;
      if (search) url += `&search=${encodeURIComponent(search)}`;
      if (selectedStatus) url += `&status=${encodeURIComponent(selectedStatus)}`;
      if (selectedCampaign) url += `&campaign_id=${encodeURIComponent(selectedCampaign)}`;

      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setLeads(data.leads ?? []);
        setTotal(data.total ?? 0);
        setPages(data.pages ?? 1);
      }
    } catch (e) {
      console.error("Erro ao obter leads", e);
      toast.error("Erro ao carregar lista de leads");
    } finally {
      setLoadingList(false);
    }
  }, [currentPage, search, selectedStatus, selectedCampaign]);

  // Sync leads list
  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  // Load a single lead's visual history timeline
  const loadLeadTimeline = async (leadId: number) => {
    setLoadingTimeline(true);
    try {
      const res = await fetch(`/api/leads/${leadId}/activity`);
      if (res.ok) {
        const data = await res.json();
        setLeadTimeline(data.events ?? []);
      }
    } catch {
      setLeadTimeline([]);
    } finally {
      setLoadingTimeline(false);
    }
  };

  const handleOpenDetails = (lead: Lead) => {
    setSelectedLead(lead);
    setDetailsOpen(true);
    loadLeadTimeline(lead.id);
  };

  const handleDeleteLead = async (leadId: number) => {
    if (!confirm("Deseja mesmo excluir permanentemente este Lead do VoxFlow?")) return;
    setActionLoading(true);
    try {
      const res = await fetch(`/api/leads/${leadId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        toast.success("Lead removido com sucesso!");
        setDetailsOpen(false);
        setSelectedLead(null);
        loadLeads();
      } else {
        toast.error("Não foi possível excluir o lead");
      }
    } catch {
      toast.error("Erro ao excluir o lead");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreateLead = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const payload = {
      campaign_id: Number(formData.get("campaign_id")),
      name: formData.get("name") as string,
      numero_1: formData.get("numero_1") as string,
      email: formData.get("email") as string || null,
      company_name: formData.get("company_name") as string || null,
      job_title: formData.get("job_title") as string || null,
      notes: formData.get("notes") as string || null,
      status: "new",
    };

    if (!payload.campaign_id) {
      toast.error("Selecione uma campanha");
      return;
    }
    if (!payload.name) {
      toast.error("Nome é obrigatório");
      return;
    }
    if (!payload.numero_1) {
      toast.error("Telefone é obrigatório");
      return;
    }

    setActionLoading(true);
    try {
      const res = await fetch("/api/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const result = await res.json();
      if (res.ok) {
        toast.success("Lead adicionado ao sistema!");
        setCreateOpen(false);
        loadLeads();
      } else {
        toast.error(result.error || "Erro ao adicionar lead");
      }
    } catch {
      toast.error("Erro na requisição de criação");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Leads</h1>
          <p className="text-muted-foreground mt-1">
            Gestão inteligente de contatos da empresa e campanhas ativas.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="px-3 py-1.5 text-xs font-semibold bg-muted/30">
            {total} lead{total !== 1 ? "s" : ""} cadastrados
          </Badge>
          <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5">
            <Plus className="h-4 w-4" />
            Adicionar Lead
          </Button>
        </div>
      </div>

      {/* Filters Toolbar */}
      <div className="bg-card border border-border/50 rounded-xl p-4 flex flex-wrap gap-4 items-center">
        {/* Search */}
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar por nome, telefone ou empresa..."
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* Campaign Filter */}
        <div className="flex items-center gap-2">
          <Filter className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <select
            value={selectedCampaign}
            onChange={(e) => {
              setSelectedCampaign(e.target.value);
              setCurrentPage(1);
            }}
            className="h-9 rounded-lg border border-input bg-background px-3 py-1 text-xs font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">Todas as Campanhas</option>
            {campaigns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        {/* Status Filter */}
        <select
          value={selectedStatus}
          onChange={(e) => {
            setSelectedStatus(e.target.value);
            setCurrentPage(1);
          }}
          className="h-9 rounded-lg border border-input bg-background px-3 py-1 text-xs font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">Todos os Status</option>
          <option value="new">Novo (Jinja / API new)</option>
          <option value="dialing">Em Discagem</option>
          <option value="contacted">Contatado</option>
          <option value="completed">Concluído</option>
          <option value="invalid">Número Inválido</option>
          <option value="voicemail">Caixa Postal</option>
          <option value="no_answer">Sem Resposta</option>
          <option value="busy">Ocupado</option>
        </select>
      </div>

      {/* Datatable */}
      <div className="bg-card border border-border/50 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/30 text-muted-foreground text-xs font-bold uppercase tracking-wider">
                <th className="px-6 py-3.5 text-left">Contato</th>
                <th className="px-6 py-3.5 text-left">Empresa / Cargo</th>
                <th className="px-6 py-3.5 text-left">Telefones</th>
                <th className="px-6 py-3.5 text-left">Campanha</th>
                <th className="px-6 py-3.5 text-left">Status</th>
                <th className="px-6 py-3.5 text-left">Cadastrado em</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {loadingList ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto text-primary" />
                    <span className="text-xs font-medium mt-2 block">Obtendo base de leads...</span>
                  </td>
                </tr>
              ) : leads.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                    Nenhum lead encontrado com os filtros ativos.
                  </td>
                </tr>
              ) : (
                leads.map((lead) => {
                  const status = lead.status.toLowerCase();
                  const st = statusConfig[status] || { label: lead.status, variant: "outline" };
                  const campaign = campaigns.find((c) => c.id === lead.campaign_id);

                  return (
                    <tr
                      key={lead.id}
                      onClick={() => handleOpenDetails(lead)}
                      className="hover:bg-muted/20 cursor-pointer transition-colors duration-150"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="h-9 w-9 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">
                            {lead.name.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p className="font-semibold text-foreground text-sm leading-none">
                              {lead.name}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {lead.email || "Sem email"}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        {lead.company_name ? (
                          <div>
                            <p className="text-sm font-medium text-foreground leading-none">
                              {lead.company_name}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {lead.job_title || "Cargo não informado"}
                            </p>
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="space-y-0.5 font-mono text-xs">
                          <p className="text-foreground">{formatPhone(lead.numero_1)}</p>
                          {lead.numero_2 && (
                            <p className="text-muted-foreground">{formatPhone(lead.numero_2)}</p>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant="outline" className="text-xs font-semibold bg-muted/10">
                          {campaign?.name || `Campanha #${lead.campaign_id}`}
                        </Badge>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={st.variant as "default"}>{st.label}</Badge>
                      </td>
                      <td className="px-6 py-4 text-xs text-muted-foreground">
                        {formatDate(lead.created_at)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination bar */}
        {!loadingList && pages > 1 && (
          <div className="px-6 py-4 bg-muted/20 border-t flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-medium">
              Página {currentPage} de {pages} (total de {total} leads)
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((c) => c - 1)}
              >
                Anterior
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage >= pages}
                onClick={() => setCurrentPage((c) => c + 1)}
              >
                Próxima
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Creation Modal */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setCreateOpen(false)} />
          <div className="relative bg-card rounded-2xl shadow-2xl border w-full max-w-lg mx-4 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between p-6 border-b">
              <h2 className="text-lg font-bold">Adicionar Novo Lead</h2>
              <button
                onClick={() => setCreateOpen(false)}
                className="text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateLead} className="p-6 space-y-4 max-h-[80vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-4">
                {/* Campaign Selection */}
                <div className="col-span-2 space-y-1.5">
                  <Label htmlFor="create-campaign">Campanha *</Label>
                  <select
                    id="create-campaign"
                    name="campaign_id"
                    required
                    className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="">Selecione uma campanha...</option>
                    {campaigns.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Name */}
                <div className="col-span-2 space-y-1.5">
                  <Label htmlFor="create-name">Nome Completo *</Label>
                  <Input id="create-name" name="name" placeholder="João da Silva" required />
                </div>

                {/* Phone */}
                <div className="space-y-1.5">
                  <Label htmlFor="create-phone">Telefone Principal *</Label>
                  <Input id="create-phone" name="numero_1" placeholder="11999999999" required />
                </div>

                {/* Email */}
                <div className="space-y-1.5">
                  <Label htmlFor="create-email">E-mail</Label>
                  <Input id="create-email" name="email" type="email" placeholder="joao@empresa.com" />
                </div>

                {/* Company name */}
                <div className="space-y-1.5">
                  <Label htmlFor="create-company">Empresa</Label>
                  <Input id="create-company" name="company_name" placeholder="Empresa S/A" />
                </div>

                {/* Job Title */}
                <div className="space-y-1.5">
                  <Label htmlFor="create-job">Cargo</Label>
                  <Input id="create-job" name="job_title" placeholder="Diretor" />
                </div>

                {/* Notes */}
                <div className="col-span-2 space-y-1.5">
                  <Label htmlFor="create-notes">Observações</Label>
                  <textarea
                    id="create-notes"
                    name="notes"
                    placeholder="Informações relevantes sobre este contato..."
                    className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[80px] resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  className="flex-1 font-semibold"
                  onClick={() => setCreateOpen(false)}
                >
                  Cancelar
                </Button>
                <Button type="submit" className="flex-1 font-semibold" loading={actionLoading}>
                  Adicionar Lead
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Details Side-Drawer */}
      {detailsOpen && selectedLead && (
        <>
          <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-xs" onClick={() => setDetailsOpen(false)} />
          <div className="fixed right-0 top-0 h-full w-full max-w-lg z-50 bg-card border-l border-border/80 shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-right duration-300">
            {/* Drawer Header */}
            <div className="sticky top-0 bg-card border-b px-6 py-4 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-base shadow-sm">
                  {selectedLead.name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <h2 className="font-bold text-foreground text-base tracking-tight leading-none">
                    {selectedLead.name}
                  </h2>
                  <p className="text-xs text-muted-foreground mt-1.5">
                    Lead ID: #{selectedLead.id}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setDetailsOpen(false)}
                className="text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Drawer Body Container */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Quick Actions */}
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="flex-1 text-destructive border-destructive/20 hover:bg-destructive/5 hover:text-destructive cursor-pointer font-semibold"
                  onClick={() => handleDeleteLead(selectedLead.id)}
                  loading={actionLoading}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Excluir Lead
                </Button>
              </div>

              {/* Status and Campaign Info */}
              <div className="grid grid-cols-2 gap-4 bg-muted/40 p-4 rounded-xl border">
                <div>
                  <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-1">
                    Status Atual
                  </p>
                  <Badge
                    variant={
                      (statusConfig[selectedLead.status.toLowerCase()]?.variant as "default") ||
                      "outline"
                    }
                  >
                    {statusConfig[selectedLead.status.toLowerCase()]?.label || selectedLead.status}
                  </Badge>
                </div>
                <div>
                  <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-1">
                    Campanha Vinculada
                  </p>
                  <span className="text-xs font-semibold text-foreground block truncate">
                    {campaigns.find((c) => c.id === selectedLead.campaign_id)?.name ||
                      `Campanha #${selectedLead.campaign_id}`}
                  </span>
                </div>
              </div>

              {/* Contact Data Details */}
              <div className="space-y-4">
                <h3 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
                  Informações de Contato
                </h3>
                <div className="space-y-3">
                  {/* Phone 1 */}
                  <div className="flex items-center gap-3 text-sm text-foreground">
                    <div className="h-7 w-7 rounded-lg bg-muted flex items-center justify-center text-muted-foreground">
                      <Phone className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground leading-none">Telefone Principal</p>
                      <p className="font-mono font-medium mt-1">
                        {formatPhone(selectedLead.numero_1)}
                      </p>
                    </div>
                  </div>

                  {/* Phone 2 */}
                  {selectedLead.numero_2 && (
                    <div className="flex items-center gap-3 text-sm text-foreground">
                      <div className="h-7 w-7 rounded-lg bg-muted flex items-center justify-center text-muted-foreground">
                        <Phone className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground leading-none">Telefone Secundário</p>
                        <p className="font-mono font-medium mt-1">
                          {formatPhone(selectedLead.numero_2)}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Email */}
                  {selectedLead.email && (
                    <div className="flex items-center gap-3 text-sm text-foreground">
                      <div className="h-7 w-7 rounded-lg bg-muted flex items-center justify-center text-muted-foreground">
                        <Mail className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground leading-none">E-mail corporativo</p>
                        <a
                          href={`mailto:${selectedLead.email}`}
                          className="font-medium text-primary hover:underline mt-1 block"
                        >
                          {selectedLead.email}
                        </a>
                      </div>
                    </div>
                  )}

                  {/* Company Name */}
                  {selectedLead.company_name && (
                    <div className="flex items-center gap-3 text-sm text-foreground">
                      <div className="h-7 w-7 rounded-lg bg-muted flex items-center justify-center text-muted-foreground">
                        <Building2 className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground leading-none">Empresa / Organização</p>
                        <p className="font-medium mt-1">
                          {selectedLead.company_name}
                          {selectedLead.job_title && (
                            <span className="text-muted-foreground font-normal">
                              {" "}
                              · {selectedLead.job_title}
                            </span>
                          )}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Notes */}
              {selectedLead.notes && (
                <div className="space-y-2">
                  <h3 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
                    Observações / Notas
                  </h3>
                  <div className="bg-muted p-4 rounded-xl border text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                    {selectedLead.notes}
                  </div>
                </div>
              )}

              {/* Unified Event Activity Timeline (Twilio calls & note creation) */}
              <div className="space-y-4">
                <h3 className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <PhoneCall className="h-4 w-4" />
                  Timeline de Atividade
                </h3>
                {loadingTimeline ? (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground py-2 justify-center">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    <span>Processando histórico...</span>
                  </div>
                ) : leadTimeline.length === 0 ? (
                  <p className="text-xs text-muted-foreground py-4 text-center">
                    Nenhuma atividade registrada para este lead.
                  </p>
                ) : (
                  <div className="relative pl-6 border-l border-border space-y-5">
                    {leadTimeline.map((event, index) => (
                      <div key={index} className="relative">
                        {/* Timeline Node Point */}
                        <div
                          className="absolute -left-[31px] top-0.5 h-4 w-4 rounded-full border bg-card flex items-center justify-center shadow-xs"
                          style={{ borderColor: event.color }}
                        >
                          <div
                            className="h-1.5 w-1.5 rounded-full"
                            style={{ backgroundColor: event.color }}
                          />
                        </div>

                        {/* Event details */}
                        <div>
                          <div className="flex justify-between items-baseline gap-2">
                            <h4 className="text-sm font-semibold text-foreground">
                              {event.title}
                            </h4>
                            {event.created_at && (
                              <span className="text-[10px] text-muted-foreground font-mono">
                                {formatDate(event.created_at)}
                              </span>
                            )}
                          </div>
                          {event.body && (
                            <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                              {event.body}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
