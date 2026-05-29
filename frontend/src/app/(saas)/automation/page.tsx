"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Zap,
  Plus,
  Play,
  Pause,
  Trash2,
  Edit3,
  MoreHorizontal,
  MessageCircle,
  Bell,
  CheckCircle,
  ClipboardList,
  Settings,
  ChevronDown,
  Loader2,
  Activity,
  ArrowRight,
  CircleDot,
  RefreshCw,
  AlertCircle,
  Shield,
  Timer,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";

// ─── Types ───────────────────────────────────────────────────────────────────

type Pipeline = {
  id: number;
  name: string;
  color: string;
  stages?: Stage[];
};

type Stage = {
  id: number;
  name: string;
  color: string;
  position: number;
  pipeline_id: number;
  automations_count: number;
};

type Automation = {
  id: number;
  stage_id: number;
  company_id: number;
  is_active: boolean;
  position: number;
  type: string;
  config: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
};

type AutomationLog = {
  id: number;
  automation_id: number;
  deal_id: number | null;
  lead_id: number | null;
  type: string;
  status: "success" | "failed" | "skipped";
  error_message: string | null;
  executed_at: string | null;
  payload: Record<string, unknown> | null;
};

// ─── Constants ───────────────────────────────────────────────────────────────

const AUTOMATION_TYPES = [
  {
    value: "send_whatsapp",
    label: "Enviar WhatsApp",
    description: "Envia uma mensagem automática via WhatsApp quando o deal entra nesta etapa",
    icon: MessageCircle,
    color: "text-emerald-500",
    bgColor: "bg-emerald-500/10",
  },
  {
    value: "notify_agent",
    label: "Notificar Operador",
    description: "Envia notificação push ou e-mail para o operador responsável",
    icon: Bell,
    color: "text-indigo-500",
    bgColor: "bg-indigo-500/10",
  },
  {
    value: "create_task",
    label: "Criar Tarefa",
    description: "Cria uma tarefa automática de follow-up para o operador",
    icon: ClipboardList,
    color: "text-amber-500",
    bgColor: "bg-amber-500/10",
  },
  {
    value: "update_deal",
    label: "Atualizar Negócio",
    description: "Atualiza campos do deal automaticamente (probabilidade, status, etc.)",
    icon: RefreshCw,
    color: "text-sky-500",
    bgColor: "bg-sky-500/10",
  },
];

// ─── Component ───────────────────────────────────────────────────────────────

export default function AutomationPage() {
  // State
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [selectedPipelineId, setSelectedPipelineId] = useState<number | null>(null);
  const [stages, setStages] = useState<Stage[]>([]);
  const [selectedStageId, setSelectedStageId] = useState<number | null>(null);
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [logs, setLogs] = useState<AutomationLog[]>([]);

  // Loading
  const [loadingPipelines, setLoadingPipelines] = useState(true);
  const [loadingAutomations, setLoadingAutomations] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Modals
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [selectedAutomation, setSelectedAutomation] = useState<Automation | null>(null);

  // Form
  const [formType, setFormType] = useState("");
  const [formConfig, setFormConfig] = useState<Record<string, string>>({});
  const [formActive, setFormActive] = useState(true);

  // ─── Data Loading ────────────────────────────────────────────────────────

  const loadPipelines = useCallback(async () => {
    try {
      const res = await fetch("/api/crm/pipelines");
      if (res.ok) {
        const data: Pipeline[] = await res.json();
        const active = data.filter((p) => !("is_archived" in p) || !(p as any).is_archived);
        setPipelines(active);
        if (active.length > 0 && !selectedPipelineId) {
          setSelectedPipelineId(active[0].id);
          setStages(active[0].stages || []);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingPipelines(false);
    }
  }, [selectedPipelineId]);

  const loadAutomations = useCallback(async (stageId: number) => {
    setLoadingAutomations(true);
    try {
      const res = await fetch(`/api/crm/stages/${stageId}/automations`);
      if (res.ok) {
        const data = await res.json();
        setAutomations(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingAutomations(false);
    }
  }, []);

  const loadLogs = useCallback(async () => {
    setLoadingLogs(true);
    try {
      const res = await fetch("/api/crm/automations/logs?limit=30");
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingLogs(false);
    }
  }, []);

  useEffect(() => {
    loadPipelines();
    loadLogs();
  }, [loadPipelines, loadLogs]);

  useEffect(() => {
    if (selectedPipelineId) {
      const pipeline = pipelines.find((p) => p.id === selectedPipelineId);
      setStages(pipeline?.stages || []);
      setSelectedStageId(null);
      setAutomations([]);
    }
  }, [selectedPipelineId, pipelines]);

  useEffect(() => {
    if (selectedStageId) {
      loadAutomations(selectedStageId);
    }
  }, [selectedStageId, loadAutomations]);

  // ─── CRUD ────────────────────────────────────────────────────────────────

  const handleCreate = async () => {
    if (!formType || !selectedStageId) {
      toast.error("Selecione um tipo de automação e uma etapa");
      return;
    }
    setActionLoading(true);
    try {
      const res = await fetch(`/api/crm/stages/${selectedStageId}/automations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: formType,
          config: formConfig,
          is_active: formActive,
        }),
      });
      if (res.ok) {
        toast.success("Automação criada com sucesso!");
        setCreateOpen(false);
        resetForm();
        await loadAutomations(selectedStageId);
      } else {
        const err = await res.json();
        toast.error(err.error || "Erro ao criar automação");
      }
    } catch {
      toast.error("Erro de conexão");
    } finally {
      setActionLoading(false);
    }
  };

  const handleUpdate = async () => {
    if (!selectedAutomation) return;
    setActionLoading(true);
    try {
      const res = await fetch(`/api/crm/automations/${selectedAutomation.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: formType,
          config: formConfig,
          is_active: formActive,
        }),
      });
      if (res.ok) {
        toast.success("Automação atualizada!");
        setEditOpen(false);
        resetForm();
        if (selectedStageId) await loadAutomations(selectedStageId);
      } else {
        const err = await res.json();
        toast.error(err.error || "Erro ao atualizar automação");
      }
    } catch {
      toast.error("Erro de conexão");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async (automationId: number) => {
    try {
      const res = await fetch(`/api/crm/automations/${automationId}`, { method: "DELETE" });
      if (res.ok) {
        toast.success("Automação removida");
        if (selectedStageId) await loadAutomations(selectedStageId);
      } else {
        const err = await res.json();
        toast.error(err.error || "Erro ao remover");
      }
    } catch {
      toast.error("Erro de conexão");
    }
  };

  const handleToggle = async (automation: Automation) => {
    try {
      const res = await fetch(`/api/crm/automations/${automation.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !automation.is_active }),
      });
      if (res.ok) {
        toast.success(automation.is_active ? "Automação pausada" : "Automação ativada");
        if (selectedStageId) await loadAutomations(selectedStageId);
      }
    } catch {
      toast.error("Erro ao alternar status");
    }
  };

  const resetForm = () => {
    setFormType("");
    setFormConfig({});
    setFormActive(true);
    setSelectedAutomation(null);
  };

  const openEdit = (automation: Automation) => {
    setSelectedAutomation(automation);
    setFormType(automation.type);
    setFormConfig(automation.config as Record<string, string>);
    setFormActive(automation.is_active);
    setEditOpen(true);
  };

  // ─── Helpers ──────────────────────────────────────────────────────────────

  const getTypeInfo = (type: string) => AUTOMATION_TYPES.find((t) => t.value === type);

  const selectedStage = stages.find((s) => s.id === selectedStageId);

  // ─── Loading ──────────────────────────────────────────────────────────────

  if (loadingPipelines) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Loader2 className="h-10 w-10 border-4 border-primary border-t-transparent rounded-full animate-spin text-primary" />
        <p className="text-sm text-muted-foreground font-medium animate-pulse">
          Carregando automações...
        </p>
      </div>
    );
  }

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Automações</h1>
          <p className="text-muted-foreground mt-1">
            Configure ações automáticas que executam quando um negócio entra em uma etapa do pipeline.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="px-3 py-1.5 text-xs font-semibold bg-muted/30 gap-1.5">
            <Zap className="h-3 w-3 text-primary" />
            {automations.filter((a) => a.is_active).length} ativas
          </Badge>
        </div>
      </div>

      {/* Pipeline + Stage Selector */}
      <div className="flex items-center gap-3">
        {/* Pipeline */}
        <div className="space-y-1">
          <Label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
            Pipeline
          </Label>
          <select
            value={selectedPipelineId || ""}
            onChange={(e) => setSelectedPipelineId(Number(e.target.value) || null)}
            className="h-9 rounded-lg border border-input bg-background px-3 py-1 text-sm font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-primary min-w-[200px]"
          >
            <option value="">Selecione um pipeline...</option>
            {pipelines.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <ArrowRight className="h-4 w-4 text-muted-foreground/40 mt-5" />

        {/* Stage */}
        <div className="space-y-1">
          <Label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
            Etapa do Funil
          </Label>
          <select
            value={selectedStageId || ""}
            onChange={(e) => setSelectedStageId(Number(e.target.value) || null)}
            className="h-9 rounded-lg border border-input bg-background px-3 py-1 text-sm font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-primary min-w-[200px]"
            disabled={!selectedPipelineId}
          >
            <option value="">Selecione uma etapa...</option>
            {stages.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} {s.automations_count > 0 ? `(${s.automations_count} automações)` : ""}
              </option>
            ))}
          </select>
        </div>

        {selectedStageId && (
          <Button
            size="sm"
            className="mt-5 gap-1.5 shadow-md shadow-primary/20"
            onClick={() => setCreateOpen(true)}
          >
            <Plus className="h-4 w-4" />
            Nova Automação
          </Button>
        )}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Automations List */}
        <div className="lg:col-span-8 space-y-4">
          {selectedStageId ? (
            <>
              {/* Stage header card */}
              <Card className="border-border/50 shadow-sm bg-gradient-to-r from-primary/5 to-transparent">
                <CardContent className="py-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className="h-10 w-10 rounded-xl flex items-center justify-center"
                      style={{ backgroundColor: `${selectedStage?.color}15` }}
                    >
                      <Zap className="h-5 w-5" style={{ color: selectedStage?.color }} />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-foreground">
                        Automações da etapa: {selectedStage?.name}
                      </h3>
                      <p className="text-[10px] text-muted-foreground font-semibold">
                        {automations.length} automação(ões) configurada(s)
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Automation Cards */}
              {loadingAutomations ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
              ) : automations.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 gap-3">
                  <div className="h-14 w-14 rounded-2xl bg-muted flex items-center justify-center">
                    <Zap className="h-7 w-7 text-muted-foreground/40" />
                  </div>
                  <p className="text-sm text-muted-foreground font-medium">
                    Nenhuma automação configurada nesta etapa.
                  </p>
                  <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5">
                    <Plus className="h-4 w-4" />
                    Criar Automação
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {automations.map((automation, index) => {
                    const typeInfo = getTypeInfo(automation.type);
                    const Icon = typeInfo?.icon || Zap;
                    return (
                      <Card
                        key={automation.id}
                        className={`border-border/50 shadow-sm transition-all duration-200 hover:shadow-md ${
                          !automation.is_active ? "opacity-60" : ""
                        }`}
                      >
                        <CardContent className="py-4">
                          <div className="flex items-center gap-4">
                            {/* Step number */}
                            <div className="flex flex-col items-center gap-1 shrink-0">
                              <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-xs font-bold text-muted-foreground">
                                {index + 1}
                              </div>
                              {index < automations.length - 1 && (
                                <div className="w-0.5 h-4 bg-border/60" />
                              )}
                            </div>

                            {/* Icon */}
                            <div
                              className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${
                                typeInfo?.bgColor || "bg-muted"
                              }`}
                            >
                              <Icon className={`h-5 w-5 ${typeInfo?.color || "text-muted-foreground"}`} />
                            </div>

                            {/* Content */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <h4 className="text-sm font-bold text-foreground">
                                  {typeInfo?.label || automation.type}
                                </h4>
                                <Badge
                                  variant={automation.is_active ? "success" : "secondary"}
                                  className="text-[9px] h-4 px-1.5"
                                >
                                  {automation.is_active ? "Ativa" : "Pausada"}
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground mt-0.5">
                                {typeInfo?.description || "Automação personalizada"}
                              </p>

                              {/* Config display */}
                              {Object.keys(automation.config || {}).length > 0 && (
                                <div className="mt-2 flex flex-wrap gap-1.5">
                                  {Object.entries(automation.config).map(([key, value]) => (
                                    <Badge
                                      key={key}
                                      variant="outline"
                                      className="text-[9px] font-mono"
                                    >
                                      {key}: {String(value).slice(0, 30)}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                            </div>

                            {/* Actions */}
                            <div className="flex items-center gap-1 shrink-0">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0"
                                onClick={() => handleToggle(automation)}
                                title={automation.is_active ? "Pausar" : "Ativar"}
                              >
                                {automation.is_active ? (
                                  <Pause className="h-3.5 w-3.5 text-amber-500" />
                                ) : (
                                  <Play className="h-3.5 w-3.5 text-emerald-500" />
                                )}
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0"
                                onClick={() => openEdit(automation)}
                              >
                                <Edit3 className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                                onClick={() => handleDelete(automation.id)}
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 gap-4">
              <div className="h-16 w-16 rounded-2xl bg-muted flex items-center justify-center">
                <Zap className="h-8 w-8 text-muted-foreground/30" />
              </div>
              <div className="text-center">
                <h3 className="font-bold text-foreground text-lg">
                  Selecione uma Etapa
                </h3>
                <p className="text-sm text-muted-foreground mt-1 max-w-md">
                  Escolha um pipeline e uma etapa do funil para configurar automações que
                  executam quando um negócio entra naquela etapa.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Automation Logs Panel */}
        <div className="lg:col-span-4">
          <Card className="border-border/50 shadow-sm sticky top-6">
            <CardHeader className="pb-3 border-b">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <Activity className="h-4 w-4 text-primary" />
                  Logs de Execução
                </CardTitle>
                <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={loadLogs}>
                  <RefreshCw className={`h-3 w-3 mr-1 ${loadingLogs ? "animate-spin" : ""}`} />
                  Atualizar
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-3">
              {loadingLogs ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                </div>
              ) : logs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <Timer className="h-8 w-8 text-muted-foreground/30" />
                  <p className="text-xs text-muted-foreground mt-2 font-medium">
                    Nenhum log de execução ainda.
                  </p>
                </div>
              ) : (
                <div className="space-y-2 max-h-[500px] overflow-y-auto">
                  {logs.map((log) => {
                    const typeInfo = getTypeInfo(log.type);
                    return (
                      <div
                        key={log.id}
                        className="p-2.5 rounded-lg bg-muted/30 border border-border/20 space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold text-foreground flex items-center gap-1">
                            {typeInfo?.label || log.type}
                          </span>
                          <Badge
                            variant={
                              log.status === "success"
                                ? "success"
                                : log.status === "failed"
                                  ? "destructive"
                                  : "secondary"
                            }
                            className="text-[8px] h-3.5 px-1"
                          >
                            {log.status === "success"
                              ? "✓ OK"
                              : log.status === "failed"
                                ? "✗ Falha"
                                : "⊘ Pulado"}
                          </Badge>
                        </div>
                        {log.error_message && (
                          <p className="text-[9px] text-destructive font-medium flex items-center gap-1">
                            <AlertCircle className="h-2.5 w-2.5" />
                            {log.error_message}
                          </p>
                        )}
                        <p className="text-[9px] text-muted-foreground">
                          {log.executed_at
                            ? new Date(log.executed_at).toLocaleString("pt-BR")
                            : "—"}
                          {log.deal_id && ` · Deal #${log.deal_id}`}
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Available Automation Types Card */}
          <Card className="border-border/50 shadow-sm mt-4">
            <CardHeader className="pb-3 border-b">
              <CardTitle className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Shield className="h-4 w-4 text-primary" />
                Tipos Disponíveis
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-3 space-y-2">
              {AUTOMATION_TYPES.map((type) => {
                const Icon = type.icon;
                return (
                  <div
                    key={type.value}
                    className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/30 transition-colors cursor-default"
                  >
                    <div className={`h-8 w-8 rounded-lg flex items-center justify-center ${type.bgColor}`}>
                      <Icon className={`h-4 w-4 ${type.color}`} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-foreground">{type.label}</p>
                      <p className="text-[9px] text-muted-foreground line-clamp-1">{type.description}</p>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ═══════ Create Automation Modal ═══════ */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold tracking-tight flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" />
              Nova Automação
            </DialogTitle>
            <DialogDescription>
              Configure uma automação que será executada quando um negócio entrar na etapa{" "}
              <strong>{selectedStage?.name}</strong>.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Type Selector */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase">Tipo de Automação *</Label>
              <div className="grid grid-cols-2 gap-2">
                {AUTOMATION_TYPES.map((type) => {
                  const Icon = type.icon;
                  const isSelected = formType === type.value;
                  return (
                    <button
                      key={type.value}
                      onClick={() => setFormType(type.value)}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        isSelected
                          ? "border-primary bg-primary/5 ring-1 ring-primary"
                          : "border-border/40 hover:border-primary/30 hover:bg-muted/30"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <div className={`h-7 w-7 rounded-lg flex items-center justify-center ${type.bgColor}`}>
                          <Icon className={`h-3.5 w-3.5 ${type.color}`} />
                        </div>
                        <span className="text-xs font-bold text-foreground">{type.label}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Config fields based on type */}
            {formType === "send_whatsapp" && (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase">Mensagem do WhatsApp</Label>
                  <textarea
                    value={formConfig.message || ""}
                    onChange={(e) => setFormConfig({ ...formConfig, message: e.target.value })}
                    placeholder="Olá {{lead_name}}, temos novidades sobre seu negócio..."
                    className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[80px] resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <p className="text-[10px] text-muted-foreground">
                  Variáveis: {"{{lead_name}}"}, {"{{deal_title}}"}, {"{{deal_value}}"}, {"{{stage_name}}"}
                </p>
              </div>
            )}

            {formType === "notify_agent" && (
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase">Mensagem da Notificação</Label>
                <Input
                  value={formConfig.notification_message || ""}
                  onChange={(e) =>
                    setFormConfig({ ...formConfig, notification_message: e.target.value })
                  }
                  placeholder="Novo negócio na etapa de qualificação!"
                />
              </div>
            )}

            {formType === "create_task" && (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase">Título da Tarefa</Label>
                  <Input
                    value={formConfig.task_title || ""}
                    onChange={(e) => setFormConfig({ ...formConfig, task_title: e.target.value })}
                    placeholder="Follow-up com lead"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase">Prazo (dias)</Label>
                  <Input
                    type="number"
                    value={formConfig.due_days || ""}
                    onChange={(e) => setFormConfig({ ...formConfig, due_days: e.target.value })}
                    placeholder="3"
                  />
                </div>
              </div>
            )}

            {formType === "update_deal" && (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase">Nova Probabilidade (%)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={formConfig.probability || ""}
                    onChange={(e) => setFormConfig({ ...formConfig, probability: e.target.value })}
                    placeholder="50"
                  />
                </div>
              </div>
            )}

            {/* Active toggle */}
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="active-check"
                checked={formActive}
                onChange={(e) => setFormActive(e.target.checked)}
                className="rounded border-input"
              />
              <Label htmlFor="active-check" className="text-xs font-semibold">
                Ativar imediatamente
              </Label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => { setCreateOpen(false); resetForm(); }}>
              Cancelar
            </Button>
            <Button onClick={handleCreate} disabled={actionLoading}>
              {actionLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Criar Automação
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ═══════ Edit Automation Modal ═══════ */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold tracking-tight flex items-center gap-2">
              <Edit3 className="h-5 w-5 text-primary" />
              Editar Automação
            </DialogTitle>
            <DialogDescription>
              Atualize a configuração da automação selecionada.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase">Tipo</Label>
              <Input value={getTypeInfo(formType)?.label || formType} disabled />
            </div>

            {formType === "send_whatsapp" && (
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase">Mensagem</Label>
                <textarea
                  value={formConfig.message || ""}
                  onChange={(e) => setFormConfig({ ...formConfig, message: e.target.value })}
                  className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[80px] resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            )}

            {formType === "notify_agent" && (
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase">Mensagem</Label>
                <Input
                  value={formConfig.notification_message || ""}
                  onChange={(e) =>
                    setFormConfig({ ...formConfig, notification_message: e.target.value })
                  }
                />
              </div>
            )}

            {formType === "create_task" && (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase">Título</Label>
                  <Input
                    value={formConfig.task_title || ""}
                    onChange={(e) => setFormConfig({ ...formConfig, task_title: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold uppercase">Prazo (dias)</Label>
                  <Input
                    type="number"
                    value={formConfig.due_days || ""}
                    onChange={(e) => setFormConfig({ ...formConfig, due_days: e.target.value })}
                  />
                </div>
              </div>
            )}

            {formType === "update_deal" && (
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase">Probabilidade (%)</Label>
                <Input
                  type="number"
                  value={formConfig.probability || ""}
                  onChange={(e) => setFormConfig({ ...formConfig, probability: e.target.value })}
                />
              </div>
            )}

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="edit-active-check"
                checked={formActive}
                onChange={(e) => setFormActive(e.target.checked)}
                className="rounded border-input"
              />
              <Label htmlFor="edit-active-check" className="text-xs font-semibold">
                Automação ativa
              </Label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => { setEditOpen(false); resetForm(); }}>
              Cancelar
            </Button>
            <Button onClick={handleUpdate} disabled={actionLoading}>
              {actionLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Salvar Alterações
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
