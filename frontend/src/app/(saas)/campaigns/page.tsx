"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Megaphone,
  Plus,
  Search,
  Play,
  Pause,
  Trash2,
  Settings,
  RefreshCw,
  X,
  ChevronRight,
  Info,
  Clock,
  Smartphone,
  Edit3,
  AlertCircle,
  Calendar,
  PhoneCall,
  Loader2,
  Users,
  CheckCircle2,
  TrendingUp,
  FileText,
  Sliders,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { formatDate } from "@/lib/utils";

type Campaign = {
  id: number;
  company_id: number;
  name: string;
  description: string | null;
  status: string; // active, paused, draft, completed
  dial_mode: "manual" | "auto" | "predictive";
  retry_limit: number;
  mobile_only: boolean;
  created_at: string;
  updated_at: string;
  default_pipeline_id: number | null;
  default_stage_id: number | null;
  call_script: string | null;
  caller_id_pool: string | null;
  predictive_ratio: number;
  ring_timeout_seconds: number;
  allowed_hours_start: number;
  allowed_hours_end: number;
  allowed_timezone: string;
  allowed_weekdays: string;
};

type CampaignProgress = {
  total_leads: number;
  new_leads: number;
  dialing_leads: number;
  contacted_leads: number;
  invalid_leads: number;
  processed_leads: number;
  total_calls: number;
  answered_calls: number;
  failed_calls: number;
  duration_total: number;
};

type Pipeline = {
  id: number;
  name: string;
  stages: { id: number; name: string }[];
};

const dialModeConfig = {
  manual: { label: "Manual", variant: "secondary" as const },
  auto: { label: "Automático (Power)", variant: "info" as const },
  predictive: { label: "Preditivo (AI)", variant: "success" as const },
};

const statusConfig = {
  draft: { label: "Rascunho", variant: "outline" as const },
  active: { label: "Ativa", variant: "success" as const },
  paused: { label: "Pausada", variant: "warning" as const },
  completed: { label: "Finalizada", variant: "info" as const },
};

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [search, setSearch] = useState("");
  
  // Loaders & Loading state
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [progressLoading, setProgressLoading] = useState(false);

  // Modals & Panels State
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);

  // Selected Campaign Details
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);
  const [campaignProgressData, setCampaignProgressData] = useState<CampaignProgress | null>(null);

  // Form Fields (For create and edit)
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    dial_mode: "manual" as "manual" | "auto" | "predictive",
    retry_limit: 3,
    mobile_only: false,
    default_pipeline_id: "",
    default_stage_id: "",
    call_script: "",
    caller_id_pool: "",
    predictive_ratio: 1.5,
    ring_timeout_seconds: 50,
    allowed_hours_start: 8,
    allowed_hours_end: 20,
  });

  // Fetch campaigns
  const loadCampaigns = useCallback(async () => {
    setLoading(true);
    try {
      let url = "/api/campaigns";
      if (search) {
        url += `?search=${encodeURIComponent(search)}`;
      }
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setCampaigns(data);
      } else {
        toast.error("Erro ao carregar campanhas");
      }
    } catch (e) {
      console.error(e);
      toast.error("Erro na comunicação com o servidor");
    } finally {
      setLoading(false);
    }
  }, [search]);

  // Fetch pipelines for mapping defaults
  const loadPipelines = async () => {
    try {
      const res = await fetch("/api/pipelines");
      if (res.ok) {
        const data = await res.json();
        setPipelines(data);
      }
    } catch (e) {
      console.error("Erro ao obter pipelines", e);
    }
  };

  useEffect(() => {
    loadCampaigns();
    loadPipelines();
  }, [loadCampaigns]);

  // Load campaign progress/stats
  const loadCampaignProgress = async (campaignId: number) => {
    setProgressLoading(true);
    try {
      const res = await fetch(`/api/campaign/${campaignId}/progress`);
      if (res.ok) {
        const data = await res.json();
        setCampaignProgressData(data);
      } else {
        setCampaignProgressData(null);
      }
    } catch {
      setCampaignProgressData(null);
    } finally {
      setProgressLoading(false);
    }
  };

  const handleOpenDetails = (campaign: Campaign) => {
    setSelectedCampaign(campaign);
    setDetailsOpen(true);
    loadCampaignProgress(campaign.id);
  };

  // Create Campaign
  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name) {
      toast.error("Nome da campanha é obrigatório");
      return;
    }
    setActionLoading(true);
    try {
      const payload = {
        name: formData.name,
        description: formData.description || null,
        dial_mode: formData.dial_mode,
        retry_limit: Number(formData.retry_limit),
        mobile_only: formData.mobile_only,
        default_pipeline_id: formData.default_pipeline_id ? Number(formData.default_pipeline_id) : null,
        default_stage_id: formData.default_stage_id ? Number(formData.default_stage_id) : null,
        call_script: formData.call_script || null,
        caller_id_pool: formData.caller_id_pool || null,
        predictive_ratio: Number(formData.predictive_ratio),
        ring_timeout_seconds: Number(formData.ring_timeout_seconds),
        allowed_hours_start: Number(formData.allowed_hours_start),
        allowed_hours_end: Number(formData.allowed_hours_end),
      };

      const res = await fetch("/api/campaign", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (res.ok) {
        toast.success("Campanha criada com sucesso!");
        setCreateOpen(false);
        // Reset form
        setFormData({
          name: "",
          description: "",
          dial_mode: "manual",
          retry_limit: 3,
          mobile_only: false,
          default_pipeline_id: "",
          default_stage_id: "",
          call_script: "",
          caller_id_pool: "",
          predictive_ratio: 1.5,
          ring_timeout_seconds: 50,
          allowed_hours_start: 8,
          allowed_hours_end: 20,
        });
        loadCampaigns();
      } else {
        toast.error(data.error || "Falha ao criar campanha");
      }
    } catch {
      toast.error("Erro ao enviar requisição");
    } finally {
      setActionLoading(false);
    }
  };

  // Open Edit Dialog
  const handleOpenEdit = (campaign: Campaign) => {
    setSelectedCampaign(campaign);
    setFormData({
      name: campaign.name,
      description: campaign.description || "",
      dial_mode: campaign.dial_mode,
      retry_limit: campaign.retry_limit,
      mobile_only: campaign.mobile_only,
      default_pipeline_id: campaign.default_pipeline_id?.toString() || "",
      default_stage_id: campaign.default_stage_id?.toString() || "",
      call_script: campaign.call_script || "",
      caller_id_pool: campaign.caller_id_pool || "",
      predictive_ratio: campaign.predictive_ratio,
      ring_timeout_seconds: campaign.ring_timeout_seconds,
      allowed_hours_start: campaign.allowed_hours_start,
      allowed_hours_end: campaign.allowed_hours_end,
    });
    setEditOpen(true);
  };

  // Update Campaign Details
  const handleUpdateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCampaign) return;
    setActionLoading(true);
    try {
      const payload = {
        name: formData.name,
        description: formData.description || null,
        dial_mode: formData.dial_mode,
        retry_limit: Number(formData.retry_limit),
        mobile_only: formData.mobile_only,
        default_pipeline_id: formData.default_pipeline_id ? Number(formData.default_pipeline_id) : null,
        default_stage_id: formData.default_stage_id ? Number(formData.default_stage_id) : null,
        call_script: formData.call_script || null,
        caller_id_pool: formData.caller_id_pool || null,
        predictive_ratio: Number(formData.predictive_ratio),
        ring_timeout_seconds: Number(formData.ring_timeout_seconds),
        allowed_hours_start: Number(formData.allowed_hours_start),
        allowed_hours_end: Number(formData.allowed_hours_end),
      };

      const res = await fetch(`/api/campaign/${selectedCampaign.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (res.ok) {
        toast.success("Campanha atualizada com sucesso!");
        setEditOpen(false);
        loadCampaigns();
        if (detailsOpen && selectedCampaign.id === data.campaign?.id) {
          setSelectedCampaign(data.campaign);
        }
      } else {
        toast.error(data.error || "Falha ao editar campanha");
      }
    } catch {
      toast.error("Erro na conexão");
    } finally {
      setActionLoading(false);
    }
  };

  // Toggle Campaign State (Start / Pause)
  const handleToggleCampaignState = async (campaign: Campaign, action: "start" | "pause") => {
    setActionLoading(true);
    try {
      const res = await fetch(`/api/campaign/${campaign.id}/${action}`, {
        method: "POST",
      });
      const data = await res.json();
      if (res.ok) {
        toast.success(action === "start" ? "Campanha ativada com sucesso!" : "Campanha pausada com sucesso!");
        loadCampaigns();
        // Refresh detail info if open
        if (detailsOpen && selectedCampaign?.id === campaign.id) {
          const updatedCampaign = { ...campaign, status: action === "start" ? "active" : "paused" };
          setSelectedCampaign(updatedCampaign);
          loadCampaignProgress(campaign.id);
        }
      } else {
        toast.error(data.error || `Erro ao ${action === "start" ? "iniciar" : "pausar"} campanha.`);
      }
    } catch {
      toast.error("Erro ao alterar estado da campanha");
    } finally {
      setActionLoading(false);
    }
  };

  // Delete Campaign
  const handleDeleteCampaign = async (campaignId: number) => {
    if (!confirm("Deseja mesmo remover esta campanha permanentemente do VoxFlow? Todos os leads associados serão desvinculados.")) return;
    setActionLoading(true);
    try {
      const res = await fetch(`/api/campaign/${campaignId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        toast.success("Campanha excluída com sucesso!");
        setDetailsOpen(false);
        setSelectedCampaign(null);
        loadCampaigns();
      } else {
        const data = await res.json();
        toast.error(data.error || "Não foi possível excluir a campanha");
      }
    } catch {
      toast.error("Erro ao excluir campanha");
    } finally {
      setActionLoading(false);
    }
  };

  // Reset Dialing Leads
  const handleResetLeads = async (campaignId: number) => {
    if (!confirm("Isso redefinirá o status de todos os leads dessa campanha de volta para 'Novo' para que possam ser discados novamente. Continuar?")) return;
    setActionLoading(true);
    try {
      const res = await fetch(`/api/campaign/${campaignId}/reset-leads`, {
        method: "POST",
      });
      const data = await res.json();
      if (res.ok) {
        toast.success("Status dos leads redefinidos com sucesso!");
        loadCampaignProgress(campaignId);
      } else {
        toast.error(data.error || "Falha ao redefinir leads");
      }
    } catch {
      toast.error("Erro na requisição");
    } finally {
      setActionLoading(false);
    }
  };

  // Clear Campaign Leads
  const handleClearLeads = async (campaignId: number) => {
    if (!confirm("CUIDADO: Isso removerá permanentemente TODOS os leads associados a esta campanha! Esta operação é irreversível. Tem certeza?")) return;
    setActionLoading(true);
    try {
      const res = await fetch(`/api/campaign/${campaignId}/clear-leads`, {
        method: "DELETE",
      });
      if (res.ok) {
        toast.success("Leads excluídos da campanha com sucesso!");
        loadCampaignProgress(campaignId);
      } else {
        const data = await res.json();
        toast.error(data.error || "Falha ao limpar leads");
      }
    } catch {
      toast.error("Erro na requisição");
    } finally {
      setActionLoading(false);
    }
  };

  // Selected pipeline's stages list
  const selectedPipelineId = formData.default_pipeline_id;
  const activePipeline = pipelines.find((p) => p.id.toString() === selectedPipelineId);
  const stages = activePipeline ? activePipeline.stages : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-foreground flex items-center gap-2">
            <Megaphone className="h-8 w-8 text-primary" />
            Campanhas de Voz
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Configure e gerencie campanhas ativas de discagem (Manual, Automática e Preditiva com Inteligência Artificial).
          </p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5 font-bold shadow-md shadow-primary/10">
            <Plus className="h-4 w-4" />
            Nova Campanha
          </Button>
        </div>
      </div>

      {/* Filter and Search toolbar */}
      <div className="bg-card border border-border/50 rounded-2xl p-4 flex flex-wrap gap-4 items-center shadow-sm">
        <div className="relative flex-1 min-w-[280px]">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar campanhas por nome ou descrição..."
            className="pl-10"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Button variant="outline" size="icon" onClick={loadCampaigns} title="Atualizar Lista" className="shrink-0 rounded-lg">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* Campaigns Grid / List */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((n) => (
            <Card key={n} className="animate-pulse bg-muted/10 border-border/50">
              <CardHeader className="h-28 bg-muted/20 border-b border-border/30" />
              <CardContent className="h-40 p-6 space-y-4">
                <div className="h-4 bg-muted/30 rounded w-2/3" />
                <div className="h-3 bg-muted/20 rounded w-full" />
                <div className="h-3 bg-muted/20 rounded w-4/5" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : campaigns.length === 0 ? (
        <div className="text-center py-16 bg-card border rounded-2xl p-8 space-y-4 shadow-sm">
          <Megaphone className="h-12 w-12 text-muted-foreground/60 mx-auto" />
          <div className="space-y-1">
            <h3 className="text-lg font-bold text-foreground">Nenhuma campanha cadastrada</h3>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto">
              Crie uma campanha de voz e importe leads para começar a fazer chamadas ativas ou configurar discagens automatizadas.
            </p>
          </div>
          <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5 mt-2">
            <Plus className="h-4 w-4" />
            Criar Minha Primeira Campanha
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {campaigns.map((campaign) => {
            const statusConfigItem = statusConfig[campaign.status as keyof typeof statusConfig] || { label: campaign.status, variant: "outline" as const };
            const modeConfigItem = dialModeConfig[campaign.dial_mode] || { label: campaign.dial_mode, variant: "outline" as const };
            
            return (
              <Card
                key={campaign.id}
                className="group hover:shadow-lg transition-all duration-200 border-border/50 bg-card overflow-hidden cursor-pointer hover:border-primary/20 flex flex-col justify-between"
                onClick={() => handleOpenDetails(campaign)}
              >
                <div>
                  <div className="p-5 border-b bg-muted/10 group-hover:bg-muted/20 transition-colors flex items-center justify-between">
                    <div className="space-y-1">
                      <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                        Modo de Discagem
                      </span>
                      <div className="flex items-center gap-1.5">
                        <Badge variant={modeConfigItem.variant} className="text-[10px] font-bold uppercase py-0.5">
                          {modeConfigItem.label}
                        </Badge>
                      </div>
                    </div>
                    <Badge variant={statusConfigItem.variant} className="font-semibold text-xs py-0.5 px-2.5">
                      {statusConfigItem.label}
                    </Badge>
                  </div>

                  <div className="p-6 space-y-4">
                    <div className="space-y-1.5">
                      <h3 className="text-lg font-black text-foreground group-hover:text-primary transition-colors tracking-tight leading-snug">
                        {campaign.name}
                      </h3>
                      <p className="text-xs text-muted-foreground line-clamp-2 min-h-[32px] leading-relaxed">
                        {campaign.description || "Nenhuma descrição fornecida."}
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4 pt-2 border-t border-border/40 text-xs">
                      <div className="space-y-1">
                        <span className="text-[10px] text-muted-foreground font-semibold block uppercase">
                          Tentativas
                        </span>
                        <p className="font-bold text-foreground">
                          {campaign.retry_limit} por Lead
                        </p>
                      </div>
                      <div className="space-y-1">
                        <span className="text-[10px] text-muted-foreground font-semibold block uppercase">
                          Mobile Only
                        </span>
                        <p className="font-bold text-foreground">
                          {campaign.mobile_only ? "Sim" : "Não (Todos)"}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="px-6 py-4 bg-muted/10 border-t border-border/30 flex items-center justify-between text-xs text-muted-foreground font-medium shrink-0">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5" />
                    {formatDate(campaign.created_at)}
                  </span>
                  <span className="text-primary group-hover:translate-x-1 transition-transform flex items-center gap-0.5 font-bold">
                    Gerenciar
                    <ChevronRight className="h-3.5 w-3.5" />
                  </span>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Details Side-Drawer */}
      {detailsOpen && selectedCampaign && (
        <>
          <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-xs" onClick={() => setDetailsOpen(false)} />
          <div className="fixed right-0 top-0 h-full w-full max-w-xl z-50 bg-card border-l border-border/80 shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-right duration-300">
            {/* Header */}
            <div className="sticky top-0 bg-card border-b px-6 py-5 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center font-bold text-lg shadow-sm">
                  <Megaphone className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="font-black text-foreground text-base tracking-tight leading-none">
                    {selectedCampaign.name}
                  </h2>
                  <p className="text-xs text-muted-foreground mt-1.5 font-medium">
                    ID Campanha: #{selectedCampaign.id}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setDetailsOpen(false)}
                className="text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Content Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Campaign State Controls */}
              <div className="flex flex-wrap gap-2.5 bg-muted/40 p-4 border rounded-2xl">
                {selectedCampaign.status === "paused" || selectedCampaign.status === "draft" ? (
                  <Button
                    size="sm"
                    className="flex-1 gap-1.5 font-bold"
                    onClick={() => handleToggleCampaignState(selectedCampaign, "start")}
                    disabled={actionLoading}
                  >
                    <Play className="h-4 w-4 fill-white" />
                    Iniciar Campanha
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="secondary"
                    className="flex-1 gap-1.5 font-bold bg-amber-500 hover:bg-amber-600 text-white border-0"
                    onClick={() => handleToggleCampaignState(selectedCampaign, "pause")}
                    disabled={actionLoading}
                  >
                    <Pause className="h-4 w-4 fill-white" />
                    Pausar Campanha
                  </Button>
                )}
                
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1.5 font-bold"
                  onClick={() => handleOpenEdit(selectedCampaign)}
                >
                  <Edit3 className="h-4 w-4" />
                  Editar
                </Button>

                <Button
                  size="sm"
                  variant="destructive"
                  className="gap-1.5 font-bold"
                  onClick={() => handleDeleteCampaign(selectedCampaign.id)}
                  disabled={actionLoading}
                >
                  <Trash2 className="h-4 w-4" />
                  Excluir
                </Button>
              </div>

              {/* Progress and Stats Cards */}
              <div className="space-y-4">
                <h3 className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <TrendingUp className="h-4 w-4 text-primary" />
                  Performance & Estatísticas Reais
                </h3>

                {progressLoading ? (
                  <div className="py-12 text-center text-muted-foreground border rounded-2xl bg-muted/10">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto text-primary" />
                    <p className="text-xs font-semibold mt-2">Processando relatório de discagem...</p>
                  </div>
                ) : campaignProgressData ? (
                  <div className="space-y-6">
                    {/* Progress Bar */}
                    <div className="bg-card border rounded-2xl p-5 space-y-3">
                      <div className="flex justify-between items-center text-xs font-bold text-muted-foreground">
                        <span className="uppercase tracking-wider">Progresso de Leads</span>
                        <span className="text-foreground text-sm font-black">
                          {campaignProgressData.total_leads > 0
                            ? Math.round(
                                ((campaignProgressData.total_leads - campaignProgressData.new_leads) /
                                  campaignProgressData.total_leads) *
                                  100
                              )
                            : 0}
                          % concluído
                        </span>
                      </div>
                      <div className="w-full bg-muted h-3 rounded-full overflow-hidden">
                        <div
                          className="bg-primary h-full transition-all duration-300 rounded-full"
                          style={{
                            width: `${
                              campaignProgressData.total_leads > 0
                                ? ((campaignProgressData.total_leads - campaignProgressData.new_leads) /
                                    campaignProgressData.total_leads) *
                                  100
                                : 0
                            }%`,
                          }}
                        />
                      </div>
                      <div className="flex justify-between items-center text-xs text-muted-foreground pt-1.5 font-semibold">
                        <span>Contatados: {campaignProgressData.contacted_leads}</span>
                        <span>Novos/Fila: {campaignProgressData.new_leads} / {campaignProgressData.total_leads}</span>
                      </div>
                    </div>

                    {/* KPI Stats Grid */}
                    <div className="grid grid-cols-2 gap-4">
                      <Card className="bg-card border-border/50">
                        <CardHeader className="py-3 px-4 flex flex-row items-center justify-between space-y-0">
                          <CardTitle className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                            Chamadas Realizadas
                          </CardTitle>
                          <PhoneCall className="h-4 w-4 text-primary" />
                        </CardHeader>
                        <CardContent className="py-2 px-4">
                          <p className="text-2xl font-black text-foreground">
                            {campaignProgressData.total_calls}
                          </p>
                          <span className="text-[10px] text-muted-foreground font-semibold mt-1 block">
                            Atendidas: {campaignProgressData.answered_calls} · Falhas: {campaignProgressData.failed_calls}
                          </span>
                        </CardContent>
                      </Card>

                      <Card className="bg-card border-border/50">
                        <CardHeader className="py-3 px-4 flex flex-row items-center justify-between space-y-0">
                          <CardTitle className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                            Tempo Total de Conversa
                          </CardTitle>
                          <Clock className="h-4 w-4 text-emerald-500" />
                        </CardHeader>
                        <CardContent className="py-2 px-4">
                          <p className="text-2xl font-black text-foreground">
                            {Math.round(campaignProgressData.duration_total / 60)} min
                          </p>
                          <span className="text-[10px] text-muted-foreground font-semibold mt-1 block">
                            {campaignProgressData.duration_total} segundos falados
                          </span>
                        </CardContent>
                      </Card>
                    </div>

                    {/* Data Actions Maintenance */}
                    <div className="space-y-2">
                      <h4 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
                        Ações da Base de Leads
                      </h4>
                      <div className="grid grid-cols-2 gap-3">
                        <Button
                          variant="outline"
                          size="sm"
                          className="font-bold border-warning/20 hover:bg-warning/5 hover:text-warning"
                          onClick={() => handleResetLeads(selectedCampaign.id)}
                          disabled={actionLoading}
                        >
                          <RefreshCw className="h-3.5 w-3.5 mr-2" />
                          Rediscar Leads (Reset)
                        </Button>
                        
                        <Button
                          variant="outline"
                          size="sm"
                          className="font-bold text-destructive border-destructive/20 hover:bg-destructive/5 hover:text-destructive"
                          onClick={() => handleClearLeads(selectedCampaign.id)}
                          disabled={actionLoading}
                        >
                          <Trash2 className="h-3.5 w-3.5 mr-2" />
                          Limpar Leads (Clear)
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground py-6 text-center border rounded-2xl bg-muted/5">
                    Não foi possível calcular estatísticas em tempo real no momento.
                  </p>
                )}
              </div>

              {/* Campaign settings Details */}
              <div className="space-y-4">
                <h3 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
                  Parâmetros de Operação
                </h3>
                <div className="border rounded-2xl divide-y text-sm">
                  <div className="p-4 flex justify-between">
                    <span className="text-muted-foreground font-medium">Modo de Discagem</span>
                    <Badge variant={dialModeConfig[selectedCampaign.dial_mode]?.variant}>
                      {dialModeConfig[selectedCampaign.dial_mode]?.label || selectedCampaign.dial_mode}
                    </Badge>
                  </div>
                  {selectedCampaign.dial_mode === "predictive" && (
                    <div className="p-4 flex justify-between">
                      <span className="text-muted-foreground font-medium">Ratio Preditivo (AI)</span>
                      <span className="font-bold text-foreground">{selectedCampaign.predictive_ratio}x</span>
                    </div>
                  )}
                  <div className="p-4 flex justify-between">
                    <span className="text-muted-foreground font-medium">Janela Horária Autorizada</span>
                    <span className="font-bold text-foreground">
                      {selectedCampaign.allowed_hours_start}:00 às {selectedCampaign.allowed_hours_end}:00
                    </span>
                  </div>
                  <div className="p-4 flex justify-between">
                    <span className="text-muted-foreground font-medium">Timeout de Toque</span>
                    <span className="font-bold text-foreground">{selectedCampaign.ring_timeout_seconds} segundos</span>
                  </div>
                  <div className="p-4 flex justify-between">
                    <span className="text-muted-foreground font-medium">Limite de Tentativas</span>
                    <span className="font-bold text-foreground">{selectedCampaign.retry_limit} chamadas</span>
                  </div>
                  {selectedCampaign.caller_id_pool && (
                    <div className="p-4 flex flex-col gap-1.5">
                      <span className="text-muted-foreground font-medium">Caller ID Pool (BINA)</span>
                      <code className="text-xs font-mono bg-muted p-2 rounded-lg break-all">
                        {selectedCampaign.caller_id_pool}
                      </code>
                    </div>
                  )}
                </div>
              </div>

              {/* Call Script Details */}
              {selectedCampaign.call_script && (
                <div className="space-y-2">
                  <h3 className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <FileText className="h-4 w-4 text-primary" />
                    Script de Atendimento da Campanha
                  </h3>
                  <div className="bg-muted p-4 rounded-2xl border text-sm text-foreground leading-relaxed whitespace-pre-wrap font-sans">
                    {selectedCampaign.call_script}
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Creation Modal */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setCreateOpen(false)} />
          <div className="relative bg-card rounded-2xl shadow-2xl border w-full max-w-2xl mx-4 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between p-6 border-b">
              <h2 className="text-lg font-black text-foreground tracking-tight">Nova Campanha de Voz</h2>
              <button onClick={() => setCreateOpen(false)} className="text-muted-foreground hover:text-foreground cursor-pointer">
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateCampaign} className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-4">
                {/* Name */}
                <div className="col-span-2 space-y-1.5">
                  <Label htmlFor="create-name">Nome da Campanha *</Label>
                  <Input
                    id="create-name"
                    placeholder="Ex: Black Friday Ativos, Renovação de Contrato"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>

                {/* Description */}
                <div className="col-span-2 space-y-1.5">
                  <Label htmlFor="create-description">Descrição Comercial</Label>
                  <textarea
                    id="create-description"
                    placeholder="Descreva o propósito da campanha..."
                    className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[70px] resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  />
                </div>

                {/* Dial Mode */}
                <div className="space-y-1.5">
                  <Label htmlFor="create-mode">Modo de Discagem *</Label>
                  <select
                    id="create-mode"
                    className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                    value={formData.dial_mode}
                    onChange={(e) => setFormData({ ...formData, dial_mode: e.target.value as any })}
                  >
                    <option value="manual">Manual (Operador inicia)</option>
                    <option value="auto">Automático / Power (Fila automática)</option>
                    <option value="predictive">Preditivo AI (Baseado em agentes livres)</option>
                  </select>
                </div>

                {/* Predictive ratio */}
                <div className="space-y-1.5">
                  <Label htmlFor="create-ratio">Ratio Preditivo (Apenas Preditivo)</Label>
                  <Input
                    id="create-ratio"
                    type="number"
                    step="0.1"
                    min="1.0"
                    max="3.0"
                    disabled={formData.dial_mode !== "predictive"}
                    value={formData.predictive_ratio}
                    onChange={(e) => setFormData({ ...formData, predictive_ratio: Number(e.target.value) })}
                  />
                </div>

                {/* Retry limit */}
                <div className="space-y-1.5">
                  <Label htmlFor="create-retry">Limite de Tentativas por Lead</Label>
                  <Input
                    id="create-retry"
                    type="number"
                    min="1"
                    max="10"
                    value={formData.retry_limit}
                    onChange={(e) => setFormData({ ...formData, retry_limit: Number(e.target.value) })}
                  />
                </div>

                {/* Ring Timeout */}
                <div className="space-y-1.5">
                  <Label htmlFor="create-timeout">Ring Timeout (Segundos)</Label>
                  <Input
                    id="create-timeout"
                    type="number"
                    min="20"
                    max="90"
                    value={formData.ring_timeout_seconds}
                    onChange={(e) => setFormData({ ...formData, ring_timeout_seconds: Number(e.target.value) })}
                  />
                </div>

                {/* Allowed Hours Start */}
                <div className="space-y-1.5">
                  <Label htmlFor="create-hstart">Início Janela Horária (h)</Label>
                  <Input
                    id="create-hstart"
                    type="number"
                    min="0"
                    max="23"
                    value={formData.allowed_hours_start}
                    onChange={(e) => setFormData({ ...formData, allowed_hours_start: Number(e.target.value) })}
                  />
                </div>

                {/* Allowed Hours End */}
                <div className="space-y-1.5">
                  <Label htmlFor="create-hend">Fim Janela Horária (h)</Label>
                  <Input
                    id="create-hend"
                    type="number"
                    min="0"
                    max="23"
                    value={formData.allowed_hours_end}
                    onChange={(e) => setFormData({ ...formData, allowed_hours_end: Number(e.target.value) })}
                  />
                </div>

                {/* Mobile only & defaults */}
                <div className="col-span-2 py-2 flex items-center gap-3">
                  <input
                    id="create-mobile"
                    type="checkbox"
                    className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                    checked={formData.mobile_only}
                    onChange={(e) => setFormData({ ...formData, mobile_only: e.target.checked })}
                  />
                  <Label htmlFor="create-mobile" className="cursor-pointer font-semibold">
                    Ligar apenas para celulares (Filtra telefones fixos)
                  </Label>
                </div>

                {/* Default CRM Pipeline mapping */}
                <div className="space-y-1.5">
                  <Label htmlFor="create-pipeline">Pipeline Padrão CRM</Label>
                  <select
                    id="create-pipeline"
                    className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                    value={formData.default_pipeline_id}
                    onChange={(e) => setFormData({ ...formData, default_pipeline_id: e.target.value, default_stage_id: "" })}
                  >
                    <option value="">Selecione um pipeline...</option>
                    {pipelines.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Default CRM Stage mapping */}
                <div className="space-y-1.5">
                  <Label htmlFor="create-stage">Estágio Padrão CRM</Label>
                  <select
                    id="create-stage"
                    disabled={!formData.default_pipeline_id}
                    className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                    value={formData.default_stage_id}
                    onChange={(e) => setFormData({ ...formData, default_stage_id: e.target.value })}
                  >
                    <option value="">Selecione um estágio...</option>
                    {stages.map((st) => (
                      <option key={st.id} value={st.id}>
                        {st.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Caller ID Pool */}
                <div className="col-span-2 space-y-1.5">
                  <Label htmlFor="create-bina">Caller ID Pool (BINA Twilio, separados por vírgula)</Label>
                  <Input
                    id="create-bina"
                    placeholder="+5511999999999, +5521988888888"
                    value={formData.caller_id_pool}
                    onChange={(e) => setFormData({ ...formData, caller_id_pool: e.target.value })}
                  />
                </div>

                {/* Call Script */}
                <div className="col-span-2 space-y-1.5">
                  <Label htmlFor="create-script">Script Recomendado para o Operador</Label>
                  <textarea
                    id="create-script"
                    placeholder="Olá [NOME], me chamo [OPERADOR] e gostaria de falar sobre..."
                    className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[90px] resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                    value={formData.call_script}
                    onChange={(e) => setFormData({ ...formData, call_script: e.target.value })}
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-4">
                <Button type="button" variant="outline" className="flex-1 font-semibold" onClick={() => setCreateOpen(false)}>
                  Cancelar
                </Button>
                <Button type="submit" className="flex-1 font-semibold" loading={actionLoading}>
                  Criar Campanha
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editOpen && selectedCampaign && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setEditOpen(false)} />
          <div className="relative bg-card rounded-2xl shadow-2xl border w-full max-w-2xl mx-4 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between p-6 border-b">
              <h2 className="text-lg font-black text-foreground tracking-tight">Editar Campanha</h2>
              <button onClick={() => setEditOpen(false)} className="text-muted-foreground hover:text-foreground cursor-pointer">
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleUpdateCampaign} className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-4">
                {/* Name */}
                <div className="col-span-2 space-y-1.5">
                  <Label htmlFor="edit-name">Nome da Campanha *</Label>
                  <Input
                    id="edit-name"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>

                {/* Description */}
                <div className="col-span-2 space-y-1.5">
                  <Label htmlFor="edit-description">Descrição Comercial</Label>
                  <textarea
                    id="edit-description"
                    className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[70px] resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  />
                </div>

                {/* Dial Mode */}
                <div className="space-y-1.5">
                  <Label htmlFor="edit-mode">Modo de Discagem *</Label>
                  <select
                    id="edit-mode"
                    className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                    value={formData.dial_mode}
                    onChange={(e) => setFormData({ ...formData, dial_mode: e.target.value as any })}
                  >
                    <option value="manual">Manual (Operador inicia)</option>
                    <option value="auto">Automático / Power (Fila automática)</option>
                    <option value="predictive">Preditivo AI (Baseado em agentes livres)</option>
                  </select>
                </div>

                {/* Predictive ratio */}
                <div className="space-y-1.5">
                  <Label htmlFor="edit-ratio">Ratio Preditivo (Apenas Preditivo)</Label>
                  <Input
                    id="edit-ratio"
                    type="number"
                    step="0.1"
                    min="1.0"
                    max="3.0"
                    disabled={formData.dial_mode !== "predictive"}
                    value={formData.predictive_ratio}
                    onChange={(e) => setFormData({ ...formData, predictive_ratio: Number(e.target.value) })}
                  />
                </div>

                {/* Retry limit */}
                <div className="space-y-1.5">
                  <Label htmlFor="edit-retry">Limite de Tentativas por Lead</Label>
                  <Input
                    id="edit-retry"
                    type="number"
                    min="1"
                    max="10"
                    value={formData.retry_limit}
                    onChange={(e) => setFormData({ ...formData, retry_limit: Number(e.target.value) })}
                  />
                </div>

                {/* Ring Timeout */}
                <div className="space-y-1.5">
                  <Label htmlFor="edit-timeout">Ring Timeout (Segundos)</Label>
                  <Input
                    id="edit-timeout"
                    type="number"
                    min="20"
                    max="90"
                    value={formData.ring_timeout_seconds}
                    onChange={(e) => setFormData({ ...formData, ring_timeout_seconds: Number(e.target.value) })}
                  />
                </div>

                {/* Allowed Hours Start */}
                <div className="space-y-1.5">
                  <Label htmlFor="edit-hstart">Início Janela Horária (h)</Label>
                  <Input
                    id="edit-hstart"
                    type="number"
                    min="0"
                    max="23"
                    value={formData.allowed_hours_start}
                    onChange={(e) => setFormData({ ...formData, allowed_hours_start: Number(e.target.value) })}
                  />
                </div>

                {/* Allowed Hours End */}
                <div className="space-y-1.5">
                  <Label htmlFor="edit-hend">Fim Janela Horária (h)</Label>
                  <Input
                    id="edit-hend"
                    type="number"
                    min="0"
                    max="23"
                    value={formData.allowed_hours_end}
                    onChange={(e) => setFormData({ ...formData, allowed_hours_end: Number(e.target.value) })}
                  />
                </div>

                {/* Mobile only & defaults */}
                <div className="col-span-2 py-2 flex items-center gap-3">
                  <input
                    id="edit-mobile"
                    type="checkbox"
                    className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                    checked={formData.mobile_only}
                    onChange={(e) => setFormData({ ...formData, mobile_only: e.target.checked })}
                  />
                  <Label htmlFor="edit-mobile" className="cursor-pointer font-semibold">
                    Ligar apenas para celulares (Filtra telefones fixos)
                  </Label>
                </div>

                {/* Default CRM Pipeline mapping */}
                <div className="space-y-1.5">
                  <Label htmlFor="edit-pipeline">Pipeline Padrão CRM</Label>
                  <select
                    id="edit-pipeline"
                    className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                    value={formData.default_pipeline_id}
                    onChange={(e) => setFormData({ ...formData, default_pipeline_id: e.target.value, default_stage_id: "" })}
                  >
                    <option value="">Selecione um pipeline...</option>
                    {pipelines.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Default CRM Stage mapping */}
                <div className="space-y-1.5">
                  <Label htmlFor="edit-stage">Estágio Padrão CRM</Label>
                  <select
                    id="edit-stage"
                    disabled={!formData.default_pipeline_id}
                    className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                    value={formData.default_stage_id}
                    onChange={(e) => setFormData({ ...formData, default_stage_id: e.target.value })}
                  >
                    <option value="">Selecione um estágio...</option>
                    {stages.map((st) => (
                      <option key={st.id} value={st.id}>
                        {st.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Caller ID Pool */}
                <div className="col-span-2 space-y-1.5">
                  <Label htmlFor="edit-bina">Caller ID Pool (BINA Twilio, separados por vírgula)</Label>
                  <Input
                    id="edit-bina"
                    placeholder="+5511999999999, +5521988888888"
                    value={formData.caller_id_pool}
                    onChange={(e) => setFormData({ ...formData, caller_id_pool: e.target.value })}
                  />
                </div>

                {/* Call Script */}
                <div className="col-span-2 space-y-1.5">
                  <Label htmlFor="edit-script">Script Recomendado para o Operador</Label>
                  <textarea
                    id="edit-script"
                    className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[90px] resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                    value={formData.call_script}
                    onChange={(e) => setFormData({ ...formData, call_script: e.target.value })}
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-4">
                <Button type="button" variant="outline" className="flex-1 font-semibold" onClick={() => setEditOpen(false)}>
                  Cancelar
                </Button>
                <Button type="submit" className="flex-1 font-semibold" loading={actionLoading}>
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
