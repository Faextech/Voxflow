"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Plus,
  MoreHorizontal,
  GripVertical,
  User,
  Building,
  DollarSign,
  Phone,
  Calendar,
  ChevronDown,
  Trash2,
  Edit3,
  Archive,
  Trophy,
  XCircle,
  ArrowRight,
  Loader2,
  Kanban,
  Palette,
  Search,
  Filter,
  Clock,
  TrendingUp,
  Eye,
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
import { formatCurrency } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────────────────────────

type Pipeline = {
  id: number;
  name: string;
  color: string;
  icon: string | null;
  description: string | null;
  position: number;
  is_default: boolean;
  is_archived: boolean;
  deals_count: number;
  deals_open: number;
  stages_count: number;
  stages?: Stage[];
};

type Stage = {
  id: number;
  name: string;
  color: string;
  position: number;
  is_won: boolean;
  is_lost: boolean;
  is_meeting: boolean;
  default_probability: number;
  pipeline_id: number;
  deals?: Deal[];
};

type DealLead = {
  id: number;
  name: string;
  phone: string | null;
  company: string | null;
  email: string | null;
  status: string;
};

type Deal = {
  id: number;
  title: string;
  value: number | null;
  currency: string;
  probability: number;
  status: string;
  notes: string | null;
  pipeline_id: number;
  stage_id: number;
  lead_id: number;
  agent_id: number | null;
  lead: DealLead | null;
  stage_entered_at: string | null;
  last_activity_at: string | null;
  expected_close_date: string | null;
  created_at: string | null;
  has_recording: boolean;
};

type BoardColumn = Stage & {
  deals: Deal[];
};

// ─── Constants ───────────────────────────────────────────────────────────────

const STAGE_COLORS = [
  "#6366f1", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b",
  "#ef4444", "#ec4899", "#14b8a6", "#3b82f6", "#f97316",
];

// ─── Component ───────────────────────────────────────────────────────────────

export default function PipelinePage() {
  // Pipeline state
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [activePipelineId, setActivePipelineId] = useState<number | null>(null);
  const [board, setBoard] = useState<BoardColumn[]>([]);
  const [pipelineMeta, setPipelineMeta] = useState<Pipeline | null>(null);

  // Loading states
  const [loadingPipelines, setLoadingPipelines] = useState(true);
  const [loadingBoard, setLoadingBoard] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Search & filter
  const [searchTerm, setSearchTerm] = useState("");

  // Drag state
  const [draggedDeal, setDraggedDeal] = useState<Deal | null>(null);
  const [dragOverStageId, setDragOverStageId] = useState<number | null>(null);

  // Modals
  const [createPipelineOpen, setCreatePipelineOpen] = useState(false);
  const [createStageOpen, setCreateStageOpen] = useState(false);
  const [createDealOpen, setCreateDealOpen] = useState(false);
  const [dealDetailOpen, setDealDetailOpen] = useState(false);
  const [selectedDeal, setSelectedDeal] = useState<Deal | null>(null);
  const [targetStageId, setTargetStageId] = useState<number | null>(null);

  // Form state
  const [formPipeline, setFormPipeline] = useState({ name: "", color: "#6366f1", description: "" });
  const [formStage, setFormStage] = useState({ name: "", color: "#6366f1", default_probability: 0 });
  const [formDeal, setFormDeal] = useState({
    title: "",
    value: "",
    lead_id: "",
    notes: "",
    expected_close_date: "",
  });

  // ─── Data Loading ────────────────────────────────────────────────────────

  const loadPipelines = useCallback(async () => {
    try {
      const res = await fetch("/api/crm/pipelines");
      if (res.ok) {
        const data: Pipeline[] = await res.json();
        const active = data.filter((p) => !p.is_archived);
        setPipelines(active);
        // Auto-select first pipeline if none is active
        if (!activePipelineId && active.length > 0) {
          setActivePipelineId(active[0].id);
        }
      }
    } catch (e) {
      console.error("Failed to load pipelines", e);
    } finally {
      setLoadingPipelines(false);
    }
  }, [activePipelineId]);

  const loadBoard = useCallback(async (pipelineId: number) => {
    setLoadingBoard(true);
    try {
      const res = await fetch(`/api/crm/pipeline/${pipelineId}/deals`);
      if (res.ok) {
        const data = await res.json();
        setPipelineMeta(data.pipeline);
        setBoard(data.board || []);
      }
    } catch (e) {
      console.error("Failed to load board", e);
    } finally {
      setLoadingBoard(false);
    }
  }, []);

  useEffect(() => {
    loadPipelines();
  }, [loadPipelines]);

  useEffect(() => {
    if (activePipelineId) {
      loadBoard(activePipelineId);
    }
  }, [activePipelineId, loadBoard]);

  // ─── Pipeline CRUD ───────────────────────────────────────────────────────

  const handleCreatePipeline = async () => {
    if (!formPipeline.name.trim()) {
      toast.error("Nome do pipeline é obrigatório");
      return;
    }
    setActionLoading(true);
    try {
      const res = await fetch("/api/crm/pipelines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formPipeline),
      });
      if (res.ok) {
        toast.success("Pipeline criado com sucesso!");
        setCreatePipelineOpen(false);
        setFormPipeline({ name: "", color: "#6366f1", description: "" });
        await loadPipelines();
      } else {
        const err = await res.json();
        toast.error(err.error || "Erro ao criar pipeline");
      }
    } catch {
      toast.error("Erro de conexão");
    } finally {
      setActionLoading(false);
    }
  };

  const handleArchivePipeline = async (pipelineId: number) => {
    try {
      const res = await fetch(`/api/crm/pipelines/${pipelineId}/archive`, { method: "POST" });
      if (res.ok) {
        toast.success("Pipeline arquivado");
        await loadPipelines();
        if (activePipelineId === pipelineId) {
          setActivePipelineId(null);
          setBoard([]);
        }
      }
    } catch {
      toast.error("Erro ao arquivar pipeline");
    }
  };

  // ─── Stage CRUD ──────────────────────────────────────────────────────────

  const handleCreateStage = async () => {
    if (!formStage.name.trim() || !activePipelineId) {
      toast.error("Nome da etapa é obrigatório");
      return;
    }
    setActionLoading(true);
    try {
      const res = await fetch(`/api/crm/pipelines/${activePipelineId}/stages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formStage),
      });
      if (res.ok) {
        toast.success("Etapa criada!");
        setCreateStageOpen(false);
        setFormStage({ name: "", color: "#6366f1", default_probability: 0 });
        await loadBoard(activePipelineId);
      } else {
        const err = await res.json();
        toast.error(err.error || "Erro ao criar etapa");
      }
    } catch {
      toast.error("Erro de conexão");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteStage = async (stageId: number) => {
    try {
      const res = await fetch(`/api/crm/stages/${stageId}`, { method: "DELETE" });
      if (res.ok) {
        toast.success("Etapa removida");
        if (activePipelineId) await loadBoard(activePipelineId);
      } else {
        const err = await res.json();
        toast.error(err.error || "Erro ao remover etapa");
      }
    } catch {
      toast.error("Erro de conexão");
    }
  };

  // ─── Deal CRUD ───────────────────────────────────────────────────────────

  const handleCreateDeal = async () => {
    if (!formDeal.title.trim() || !formDeal.lead_id || !targetStageId || !activePipelineId) {
      toast.error("Preencha título, lead ID e selecione uma etapa");
      return;
    }
    setActionLoading(true);
    try {
      const res = await fetch("/api/crm/deals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: formDeal.title,
          value: formDeal.value ? parseFloat(formDeal.value) : null,
          lead_id: parseInt(formDeal.lead_id),
          pipeline_id: activePipelineId,
          stage_id: targetStageId,
          notes: formDeal.notes || null,
          expected_close_date: formDeal.expected_close_date || null,
        }),
      });
      if (res.ok) {
        toast.success("Negócio criado com sucesso!");
        setCreateDealOpen(false);
        setFormDeal({ title: "", value: "", lead_id: "", notes: "", expected_close_date: "" });
        setTargetStageId(null);
        await loadBoard(activePipelineId);
      } else {
        const err = await res.json();
        toast.error(err.error || "Erro ao criar negócio");
      }
    } catch {
      toast.error("Erro de conexão");
    } finally {
      setActionLoading(false);
    }
  };

  const handleMoveDeal = async (dealId: number, newStageId: number) => {
    try {
      const res = await fetch(`/api/crm/deals/${dealId}/stage`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage_id: newStageId }),
      });
      if (res.ok) {
        if (activePipelineId) await loadBoard(activePipelineId);
      } else {
        const err = await res.json();
        toast.error(err.error || "Erro ao mover negócio");
      }
    } catch {
      toast.error("Erro ao mover negócio");
    }
  };

  const handleUpdateDealStatus = async (dealId: number, status: "won" | "lost") => {
    try {
      const res = await fetch(`/api/crm/deals/${dealId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (res.ok) {
        toast.success(status === "won" ? "🏆 Negócio ganho!" : "❌ Negócio perdido");
        if (activePipelineId) await loadBoard(activePipelineId);
        setDealDetailOpen(false);
      }
    } catch {
      toast.error("Erro ao atualizar status");
    }
  };

  // ─── Drag & Drop ─────────────────────────────────────────────────────────

  const onDragStart = (e: React.DragEvent, deal: Deal) => {
    setDraggedDeal(deal);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(deal.id));
  };

  const onDragOver = (e: React.DragEvent, stageId: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverStageId(stageId);
  };

  const onDragLeave = () => {
    setDragOverStageId(null);
  };

  const onDrop = (e: React.DragEvent, stageId: number) => {
    e.preventDefault();
    setDragOverStageId(null);
    if (draggedDeal && draggedDeal.stage_id !== stageId) {
      handleMoveDeal(draggedDeal.id, stageId);
    }
    setDraggedDeal(null);
  };

  // ─── Computed ─────────────────────────────────────────────────────────────

  const filteredBoard = board.map((col) => ({
    ...col,
    deals: col.deals.filter((d) => {
      if (!searchTerm) return true;
      const term = searchTerm.toLowerCase();
      return (
        d.title.toLowerCase().includes(term) ||
        d.lead?.name.toLowerCase().includes(term) ||
        d.lead?.company?.toLowerCase().includes(term) ||
        d.lead?.email?.toLowerCase().includes(term)
      );
    }),
  }));

  const totalBoardValue = board.reduce(
    (sum, col) => sum + col.deals.reduce((s, d) => s + (d.value || 0), 0),
    0
  );

  const totalDeals = board.reduce((sum, col) => sum + col.deals.length, 0);

  // ─── Helpers ──────────────────────────────────────────────────────────────

  const timeAgo = (dateStr: string | null) => {
    if (!dateStr) return "";
    const diff = Date.now() - new Date(dateStr).getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days === 0) return "Hoje";
    if (days === 1) return "Ontem";
    return `${days}d atrás`;
  };

  // ─── Loading State ────────────────────────────────────────────────────────

  if (loadingPipelines) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Loader2 className="h-10 w-10 border-4 border-primary border-t-transparent rounded-full animate-spin text-primary" />
        <p className="text-sm text-muted-foreground font-medium animate-pulse">
          Carregando pipelines CRM...
        </p>
      </div>
    );
  }

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Pipeline CRM</h1>
          <p className="text-muted-foreground mt-1">
            Kanban visual de negócios e etapas comerciais com drag-and-drop.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Pipeline Selector */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" className="gap-2 font-semibold text-sm">
                <Kanban className="h-4 w-4 text-primary" />
                {pipelines.find((p) => p.id === activePipelineId)?.name || "Selecionar Pipeline"}
                <ChevronDown className="h-3.5 w-3.5 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              {pipelines.map((p) => (
                <DropdownMenuItem
                  key={p.id}
                  onClick={() => setActivePipelineId(p.id)}
                  className="gap-2"
                >
                  <div
                    className="h-2.5 w-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: p.color }}
                  />
                  <span className="font-medium">{p.name}</span>
                  <Badge variant="secondary" className="ml-auto text-[10px]">
                    {p.deals_open}
                  </Badge>
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => setCreatePipelineOpen(true)} className="gap-2 text-primary">
                <Plus className="h-4 w-4" />
                Novo Pipeline
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Button size="sm" onClick={() => setCreateDealOpen(true)} className="gap-1.5 shadow-md shadow-primary/20">
            <Plus className="h-4 w-4" />
            Novo Negócio
          </Button>
        </div>
      </div>

      {/* Pipeline Stats Bar */}
      {activePipelineId && (
        <div className="flex items-center gap-4 shrink-0">
          <div className="flex items-center gap-6 text-xs font-semibold text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <TrendingUp className="h-3.5 w-3.5 text-primary" />
              <span className="text-foreground">{totalDeals}</span> negócios
            </span>
            <span className="flex items-center gap-1.5">
              <DollarSign className="h-3.5 w-3.5 text-emerald-500" />
              <span className="text-foreground">{formatCurrency(totalBoardValue)}</span> no funil
            </span>
            <span className="flex items-center gap-1.5">
              <Kanban className="h-3.5 w-3.5 text-indigo-500" />
              <span className="text-foreground">{board.length}</span> etapas
            </span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Buscar negócios..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8 h-8 w-56 text-xs"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 h-8 text-xs"
              onClick={() => setCreateStageOpen(true)}
            >
              <Plus className="h-3.5 w-3.5" />
              Nova Etapa
            </Button>
          </div>
        </div>
      )}

      {/* Kanban Board */}
      {activePipelineId && (
        <div className="flex-1 overflow-x-auto overflow-y-hidden pb-4">
          {loadingBoard ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : board.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 gap-3">
              <Kanban className="h-12 w-12 text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground font-medium">
                Nenhuma etapa criada neste pipeline.
              </p>
              <Button size="sm" onClick={() => setCreateStageOpen(true)}>
                <Plus className="h-4 w-4 mr-1.5" />
                Criar Primeira Etapa
              </Button>
            </div>
          ) : (
            <div className="flex gap-4 h-full min-h-[400px]">
              {filteredBoard.map((column) => (
                <div
                  key={column.id}
                  className={`flex flex-col w-[300px] min-w-[300px] bg-muted/30 rounded-xl border transition-all duration-200 ${
                    dragOverStageId === column.id
                      ? "border-primary/50 bg-primary/5 shadow-lg shadow-primary/10"
                      : "border-border/40"
                  }`}
                  onDragOver={(e) => onDragOver(e, column.id)}
                  onDragLeave={onDragLeave}
                  onDrop={(e) => onDrop(e, column.id)}
                >
                  {/* Column Header */}
                  <div className="px-3.5 py-3 border-b border-border/30 shrink-0">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div
                          className="h-2.5 w-2.5 rounded-full shrink-0"
                          style={{ backgroundColor: column.color }}
                        />
                        <h3 className="text-xs font-bold text-foreground uppercase tracking-wider">
                          {column.name}
                        </h3>
                        <Badge variant="secondary" className="text-[10px] h-5 px-1.5">
                          {column.deals.length}
                        </Badge>
                        {column.is_won && (
                          <Trophy className="h-3 w-3 text-emerald-500" />
                        )}
                        {column.is_lost && (
                          <XCircle className="h-3 w-3 text-rose-500" />
                        )}
                      </div>

                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                            <MoreHorizontal className="h-3.5 w-3.5" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-40">
                          <DropdownMenuItem
                            onClick={() => {
                              setTargetStageId(column.id);
                              setCreateDealOpen(true);
                            }}
                          >
                            <Plus className="h-3.5 w-3.5 mr-2" />
                            Novo Negócio
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() => handleDeleteStage(column.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5 mr-2" />
                            Excluir Etapa
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>

                    {/* Stage value total */}
                    {column.deals.length > 0 && (
                      <p className="text-[10px] text-muted-foreground font-semibold mt-1.5">
                        {formatCurrency(column.deals.reduce((s, d) => s + (d.value || 0), 0))}
                      </p>
                    )}
                  </div>

                  {/* Column Body – Scrollable deal cards */}
                  <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {column.deals.map((deal) => (
                      <div
                        key={deal.id}
                        draggable
                        onDragStart={(e) => onDragStart(e, deal)}
                        onDragEnd={() => setDraggedDeal(null)}
                        onClick={() => {
                          setSelectedDeal(deal);
                          setDealDetailOpen(true);
                        }}
                        className={`group bg-card rounded-lg border border-border/40 p-3 cursor-grab active:cursor-grabbing shadow-sm hover:shadow-md transition-all duration-200 hover:border-primary/30 ${
                          draggedDeal?.id === deal.id ? "opacity-40 scale-95" : ""
                        }`}
                      >
                        {/* Deal Title */}
                        <div className="flex items-start justify-between gap-2">
                          <h4 className="text-xs font-bold text-foreground leading-snug line-clamp-2">
                            {deal.title}
                          </h4>
                          <GripVertical className="h-3.5 w-3.5 text-muted-foreground/40 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>

                        {/* Lead info */}
                        {deal.lead && (
                          <div className="mt-2 space-y-1">
                            <p className="text-[11px] text-muted-foreground font-medium flex items-center gap-1">
                              <User className="h-3 w-3 text-muted-foreground/60" />
                              {deal.lead.name}
                            </p>
                            {deal.lead.company && (
                              <p className="text-[10px] text-muted-foreground/80 flex items-center gap-1">
                                <Building className="h-2.5 w-2.5" />
                                {deal.lead.company}
                              </p>
                            )}
                          </div>
                        )}

                        {/* Deal metadata footer */}
                        <div className="flex items-center justify-between mt-3 pt-2 border-t border-border/20">
                          {deal.value ? (
                            <span className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5">
                              <DollarSign className="h-3 w-3" />
                              {formatCurrency(deal.value)}
                            </span>
                          ) : (
                            <span className="text-[10px] text-muted-foreground italic">Sem valor</span>
                          )}

                          <div className="flex items-center gap-1.5">
                            {deal.probability > 0 && (
                              <Badge
                                variant="secondary"
                                className="text-[9px] h-4 px-1"
                              >
                                {deal.probability}%
                              </Badge>
                            )}
                            {deal.last_activity_at && (
                              <span className="text-[9px] text-muted-foreground/60 flex items-center gap-0.5">
                                <Clock className="h-2.5 w-2.5" />
                                {timeAgo(deal.last_activity_at)}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}

                    {/* Empty state for column */}
                    {column.deals.length === 0 && (
                      <div className="flex flex-col items-center justify-center py-8 text-center">
                        <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center mb-2">
                          <Kanban className="h-4 w-4 text-muted-foreground/50" />
                        </div>
                        <p className="text-[10px] text-muted-foreground font-medium">
                          Nenhum negócio
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Add deal to column */}
                  <div className="p-2 border-t border-border/20 shrink-0">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full h-7 text-[11px] text-muted-foreground hover:text-primary gap-1"
                      onClick={() => {
                        setTargetStageId(column.id);
                        setCreateDealOpen(true);
                      }}
                    >
                      <Plus className="h-3 w-3" />
                      Adicionar
                    </Button>
                  </div>
                </div>
              ))}

              {/* Add Stage Column */}
              <div
                className="flex flex-col items-center justify-center w-[200px] min-w-[200px] rounded-xl border border-dashed border-border/40 cursor-pointer hover:border-primary/40 hover:bg-primary/5 transition-all duration-200"
                onClick={() => setCreateStageOpen(true)}
              >
                <Plus className="h-6 w-6 text-muted-foreground/40" />
                <p className="text-xs text-muted-foreground/60 font-semibold mt-1">Nova Etapa</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty State — No Pipelines */}
      {!activePipelineId && pipelines.length === 0 && (
        <div className="flex flex-col items-center justify-center h-64 gap-4">
          <Kanban className="h-16 w-16 text-muted-foreground/30" />
          <div className="text-center">
            <h3 className="font-bold text-foreground text-lg">Nenhum Pipeline Criado</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Crie seu primeiro pipeline para organizar negócios.
            </p>
          </div>
          <Button onClick={() => setCreatePipelineOpen(true)} className="gap-1.5">
            <Plus className="h-4 w-4" />
            Criar Pipeline
          </Button>
        </div>
      )}

      {/* ═════════ MODALS ═════════ */}

      {/* Create Pipeline Modal */}
      <Dialog open={createPipelineOpen} onOpenChange={setCreatePipelineOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold tracking-tight">Novo Pipeline</DialogTitle>
            <DialogDescription>
              Crie um funil de vendas para organizar seus negócios por etapas.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase">Nome *</Label>
              <Input
                value={formPipeline.name}
                onChange={(e) => setFormPipeline({ ...formPipeline, name: e.target.value })}
                placeholder="Ex: Vendas B2B"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase">Descrição</Label>
              <Input
                value={formPipeline.description}
                onChange={(e) => setFormPipeline({ ...formPipeline, description: e.target.value })}
                placeholder="Breve descrição do pipeline..."
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase flex items-center gap-1.5">
                <Palette className="h-3.5 w-3.5 text-primary" />
                Cor
              </Label>
              <div className="flex gap-2 flex-wrap">
                {STAGE_COLORS.map((c) => (
                  <button
                    key={c}
                    onClick={() => setFormPipeline({ ...formPipeline, color: c })}
                    className={`h-7 w-7 rounded-full border-2 transition-all ${
                      formPipeline.color === c ? "border-foreground scale-110" : "border-transparent"
                    }`}
                    style={{ backgroundColor: c }}
                  />
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreatePipelineOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleCreatePipeline} disabled={actionLoading}>
              {actionLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Criar Pipeline
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Stage Modal */}
      <Dialog open={createStageOpen} onOpenChange={setCreateStageOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold tracking-tight">Nova Etapa</DialogTitle>
            <DialogDescription>
              Adicione uma etapa ao pipeline para organizar o fluxo de vendas.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase">Nome da Etapa *</Label>
              <Input
                value={formStage.name}
                onChange={(e) => setFormStage({ ...formStage, name: e.target.value })}
                placeholder="Ex: Qualificação, Proposta, Negociação..."
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase">Probabilidade Padrão (%)</Label>
              <Input
                type="number"
                min={0}
                max={100}
                value={formStage.default_probability}
                onChange={(e) =>
                  setFormStage({ ...formStage, default_probability: parseInt(e.target.value) || 0 })
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase flex items-center gap-1.5">
                <Palette className="h-3.5 w-3.5 text-primary" />
                Cor da Etapa
              </Label>
              <div className="flex gap-2 flex-wrap">
                {STAGE_COLORS.map((c) => (
                  <button
                    key={c}
                    onClick={() => setFormStage({ ...formStage, color: c })}
                    className={`h-7 w-7 rounded-full border-2 transition-all ${
                      formStage.color === c ? "border-foreground scale-110" : "border-transparent"
                    }`}
                    style={{ backgroundColor: c }}
                  />
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateStageOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleCreateStage} disabled={actionLoading}>
              {actionLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Criar Etapa
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Deal Modal */}
      <Dialog open={createDealOpen} onOpenChange={setCreateDealOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold tracking-tight">Novo Negócio</DialogTitle>
            <DialogDescription>
              Registre um novo negócio no pipeline. Vincule a um lead existente.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase">Título do Negócio *</Label>
              <Input
                value={formDeal.title}
                onChange={(e) => setFormDeal({ ...formDeal, title: e.target.value })}
                placeholder="Ex: Implementação VoxFlow para Empresa XYZ"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase">Valor (R$)</Label>
                <Input
                  type="number"
                  value={formDeal.value}
                  onChange={(e) => setFormDeal({ ...formDeal, value: e.target.value })}
                  placeholder="5000.00"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase">ID do Lead *</Label>
                <Input
                  type="number"
                  value={formDeal.lead_id}
                  onChange={(e) => setFormDeal({ ...formDeal, lead_id: e.target.value })}
                  placeholder="Lead ID"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase">Etapa de Entrada</Label>
              <select
                value={targetStageId || ""}
                onChange={(e) => setTargetStageId(Number(e.target.value) || null)}
                className="h-9 w-full rounded-lg border border-input bg-background px-3 py-1 text-sm font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">Selecione uma etapa...</option>
                {board.map((col) => (
                  <option key={col.id} value={col.id}>
                    {col.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase">Previsão de Fechamento</Label>
              <Input
                type="date"
                value={formDeal.expected_close_date}
                onChange={(e) =>
                  setFormDeal({ ...formDeal, expected_close_date: e.target.value })
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase">Observações</Label>
              <textarea
                value={formDeal.notes}
                onChange={(e) => setFormDeal({ ...formDeal, notes: e.target.value })}
                placeholder="Contexto sobre o negócio..."
                className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[70px] resize-none focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDealOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleCreateDeal} disabled={actionLoading}>
              {actionLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Criar Negócio
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Deal Detail Drawer/Modal */}
      <Dialog open={dealDetailOpen} onOpenChange={setDealDetailOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold tracking-tight flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-primary" />
              {selectedDeal?.title}
            </DialogTitle>
            <DialogDescription>
              Detalhes do negócio e ações rápidas de pipeline.
            </DialogDescription>
          </DialogHeader>

          {selectedDeal && (
            <div className="space-y-5">
              {/* Lead Info */}
              {selectedDeal.lead && (
                <div className="p-3 bg-muted/40 rounded-xl border space-y-2">
                  <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                    Lead Vinculado
                  </p>
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">
                      {selectedDeal.lead.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-bold text-foreground">{selectedDeal.lead.name}</p>
                      {selectedDeal.lead.company && (
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <Building className="h-3 w-3" />
                          {selectedDeal.lead.company}
                        </p>
                      )}
                      {selectedDeal.lead.phone && (
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <Phone className="h-3 w-3" />
                          {selectedDeal.lead.phone}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Deal Metadata */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-muted/30 rounded-lg">
                  <p className="text-[10px] text-muted-foreground font-bold uppercase">Valor</p>
                  <p className="text-sm font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                    {selectedDeal.value ? formatCurrency(selectedDeal.value) : "—"}
                  </p>
                </div>
                <div className="p-3 bg-muted/30 rounded-lg">
                  <p className="text-[10px] text-muted-foreground font-bold uppercase">Probabilidade</p>
                  <p className="text-sm font-bold text-foreground mt-0.5">
                    {selectedDeal.probability}%
                  </p>
                </div>
                <div className="p-3 bg-muted/30 rounded-lg">
                  <p className="text-[10px] text-muted-foreground font-bold uppercase">Status</p>
                  <Badge variant={selectedDeal.status === "won" ? "success" : selectedDeal.status === "lost" ? "destructive" : "secondary"} className="mt-1">
                    {selectedDeal.status === "open" ? "Aberto" : selectedDeal.status === "won" ? "Ganho" : "Perdido"}
                  </Badge>
                </div>
                <div className="p-3 bg-muted/30 rounded-lg">
                  <p className="text-[10px] text-muted-foreground font-bold uppercase">Criado em</p>
                  <p className="text-xs font-semibold text-foreground mt-0.5">
                    {selectedDeal.created_at
                      ? new Date(selectedDeal.created_at).toLocaleDateString("pt-BR")
                      : "—"}
                  </p>
                </div>
              </div>

              {/* Move to stage */}
              <div className="space-y-2">
                <Label className="text-xs font-bold uppercase text-muted-foreground">
                  Mover para Etapa
                </Label>
                <div className="flex flex-wrap gap-1.5">
                  {board.map((col) => (
                    <Button
                      key={col.id}
                      variant={col.id === selectedDeal.stage_id ? "default" : "outline"}
                      size="sm"
                      className="text-[10px] h-7 gap-1"
                      onClick={() => {
                        if (col.id !== selectedDeal.stage_id) {
                          handleMoveDeal(selectedDeal.id, col.id);
                          setDealDetailOpen(false);
                        }
                      }}
                    >
                      <div
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: col.color }}
                      />
                      {col.name}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Notes */}
              {selectedDeal.notes && (
                <div className="space-y-1">
                  <p className="text-xs font-bold uppercase text-muted-foreground">Observações</p>
                  <p className="text-xs text-muted-foreground bg-muted/30 p-3 rounded-lg">
                    {selectedDeal.notes}
                  </p>
                </div>
              )}

              {/* Quick actions */}
              {selectedDeal.status === "open" && (
                <div className="flex gap-2 pt-2 border-t">
                  <Button
                    className="flex-1 gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
                    onClick={() => handleUpdateDealStatus(selectedDeal.id, "won")}
                  >
                    <Trophy className="h-4 w-4" />
                    Marcar como Ganho
                  </Button>
                  <Button
                    variant="outline"
                    className="flex-1 gap-1.5 text-rose-500 border-rose-500/20 hover:bg-rose-500/5"
                    onClick={() => handleUpdateDealStatus(selectedDeal.id, "lost")}
                  >
                    <XCircle className="h-4 w-4" />
                    Marcar como Perdido
                  </Button>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
