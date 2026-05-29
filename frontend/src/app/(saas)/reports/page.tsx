"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  Download,
  Calendar,
  Filter,
  PhoneCall,
  Loader2,
  TrendingUp,
  FileSpreadsheet,
  AlertCircle,
  HelpCircle,
  Clock,
  CheckCircle,
  Info,
  CheckCircle2,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

type DashboardStats = {
  total_leads: number;
  total_calls: number;
  total_duration_minutes: number;
  conversion_rate: number;
  pipeline_stats: { stage_id: number; stage_name: string; count: number }[];
};

type AMDStats = {
  total: number;
  human: number;
  machine: number;
  no_answer: number;
  busy: number;
  failed: number;
  human_ratio: number;
  machine_ratio: number;
};

type TimeSeriesData = {
  date: string;
  calls: number;
  answered: number;
};

export default function ReportsPage() {
  const [loading, setLoading] = useState(true);
  const [exportingType, setExportingType] = useState<string | null>(null);

  // States for stats
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [amd, setAmd] = useState<AMDStats | null>(null);
  const [timeSeries, setTimeSeries] = useState<TimeSeriesData[]>([]);

  // Selected date range / filters mock
  const [dateRange, setDateRange] = useState("30"); // 7, 30, 90

  useEffect(() => {
    async function loadReportsData() {
      setLoading(true);
      try {
        const [statsRes, amdRes, timeRes] = await Promise.all([
          fetch("/api/analytics/dashboard"),
          fetch("/api/analytics/amd"),
          fetch("/api/analytics/time-series"),
        ]);

        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setStats(statsData);
        }
        if (amdRes.ok) {
          const amdData = await amdRes.json();
          setAmd(amdData);
        }
        if (timeRes.ok) {
          const timeData = await timeRes.json();
          setTimeSeries(timeData.time_series || timeData);
        }
      } catch (e) {
        console.error("Erro ao obter dados analíticos", e);
        toast.error("Erro ao carregar dados do relatório");
      } finally {
        setLoading(false);
      }
    }
    loadReportsData();
  }, [dateRange]);

  // Export functions
  const handleExport = (type: "leads" | "calls" | "dnc") => {
    setExportingType(type);
    toast.info(`Iniciando exportação de ${type}...`);
    try {
      // The browser handles authorization automatically due to session HTTPOnly cookies
      window.open(`/api/analytics/export/${type}`);
      setTimeout(() => {
        toast.success(`Exportação de ${type} concluída com sucesso!`);
        setExportingType(null);
      }, 1500);
    } catch {
      toast.error(`Falha ao exportar ${type}`);
      setExportingType(null);
    }
  };

  // Funnel representation counts
  const funnelStages = [
    { label: "Leads Cadastrados", count: stats?.total_leads || 0, pct: 100, color: "bg-primary" },
    { label: "Tentativas de Contato", count: stats?.total_calls || 0, pct: Math.min(100, Math.round(((stats?.total_calls || 0) / (stats?.total_leads || 1)) * 100)), color: "bg-indigo-500" },
    { label: "Contatos Humanos (AMD)", count: amd?.human || 0, pct: Math.min(100, Math.round(((amd?.human || 0) / (stats?.total_leads || 1)) * 100)), color: "bg-emerald-500" },
    { label: "Negócios Conquistados", count: Math.round((stats?.total_leads || 0) * ((stats?.conversion_rate || 0) / 100)), pct: Math.min(100, Math.round(stats?.conversion_rate || 0)), color: "bg-amber-500" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-foreground flex items-center gap-2">
            <BarChart3 className="h-8 w-8 text-primary" />
            Relatórios & Central de Exportações
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Acompanhe o funil de conversão, auditoria de ligações em tempo real, detecção de caixa postal e exporte relatórios em CSV.
          </p>
        </div>
        
        {/* Date Range Selector */}
        <div className="flex items-center gap-2 bg-card border rounded-lg px-3 py-1.5 shadow-sm text-xs font-bold text-foreground">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="bg-transparent border-0 outline-none focus:ring-0 text-xs font-bold cursor-pointer"
          >
            <option value="7">Últimos 7 dias</option>
            <option value="30">Últimos 30 dias</option>
            <option value="90">Últimos 90 dias</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i} className="animate-pulse bg-muted/10">
                <CardHeader className="h-20" />
              </Card>
            ))}
          </div>
          <Card className="animate-pulse h-64 bg-muted/10" />
        </div>
      ) : (
        <div className="space-y-6">
          {/* Top Quick KPI Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="bg-card border-border/50">
              <CardHeader className="py-4 px-5 flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-[10px] font-black uppercase tracking-wider text-muted-foreground">
                  Base de Leads
                </CardTitle>
                <Badge className="bg-primary/15 text-primary text-[9px] font-extrabold uppercase hover:bg-primary/20">
                  Total
                </Badge>
              </CardHeader>
              <CardContent className="px-5 pb-4">
                <p className="text-2xl font-black text-foreground">{stats?.total_leads}</p>
                <p className="text-[10px] text-muted-foreground mt-1 font-semibold">
                  Leads disponíveis para operação
                </p>
              </CardContent>
            </Card>

            <Card className="bg-card border-border/50">
              <CardHeader className="py-4 px-5 flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-[10px] font-black uppercase tracking-wider text-muted-foreground">
                  Total de Ligações
                </CardTitle>
                <PhoneCall className="h-4 w-4 text-indigo-500" />
              </CardHeader>
              <CardContent className="px-5 pb-4">
                <p className="text-2xl font-black text-foreground">{stats?.total_calls}</p>
                <p className="text-[10px] text-muted-foreground mt-1 font-semibold">
                  Ligações disparadas
                </p>
              </CardContent>
            </Card>

            <Card className="bg-card border-border/50">
              <CardHeader className="py-4 px-5 flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-[10px] font-black uppercase tracking-wider text-muted-foreground">
                  Conversão Geral
                </CardTitle>
                <TrendingUp className="h-4 w-4 text-emerald-500" />
              </CardHeader>
              <CardContent className="px-5 pb-4">
                <p className="text-2xl font-black text-foreground">{stats?.conversion_rate}%</p>
                <p className="text-[10px] text-muted-foreground mt-1 font-semibold">
                  Contatos qualificados
                </p>
              </CardContent>
            </Card>

            <Card className="bg-card border-border/50">
              <CardHeader className="py-4 px-5 flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-[10px] font-black uppercase tracking-wider text-muted-foreground">
                  Tempo Falado Total
                </CardTitle>
                <Clock className="h-4 w-4 text-amber-500" />
              </CardHeader>
              <CardContent className="px-5 pb-4">
                <p className="text-2xl font-black text-foreground">
                  {stats?.total_duration_minutes ? Math.round(stats.total_duration_minutes) : 0} min
                </p>
                <p className="text-[10px] text-muted-foreground mt-1 font-semibold">
                  Minutos tarifados Twilio
                </p>
              </CardContent>
            </Card>
          </div>

          {/* conversion funnel and AMD breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            {/* Funnel chart (lg:col-span-7) */}
            <Card className="bg-card border-border/50 shadow-sm lg:col-span-7">
              <CardHeader>
                <CardTitle className="text-base font-black tracking-tight text-foreground flex items-center gap-1.5">
                  Funil de Atendimento & Conversão
                </CardTitle>
                <CardDescription>
                  Breakdown visual de atritos desde a entrada do lead até a conversão final.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                {funnelStages.map((stage, idx) => (
                  <div key={idx} className="space-y-1.5">
                    <div className="flex justify-between items-center text-xs font-bold">
                      <span className="text-muted-foreground">{stage.label}</span>
                      <span className="font-mono text-foreground font-black">
                        {stage.count} ({stage.pct}%)
                      </span>
                    </div>
                    {/* Visual Funnel Bar */}
                    <div className="w-full bg-muted h-6 rounded-lg overflow-hidden flex items-center px-3 border relative">
                      <div
                        className={`absolute left-0 top-0 bottom-0 ${stage.color} opacity-20 transition-all duration-300`}
                        style={{ width: `${stage.pct}%` }}
                      />
                      <div
                        className={`h-2 rounded-full ${stage.color} shadow-xs z-10 transition-all duration-300`}
                        style={{ width: `${stage.pct}%` }}
                      />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* AMD / Voicemail statistics (lg:col-span-5) */}
            {amd && (
              <Card className="bg-card border-border/50 shadow-sm lg:col-span-5 flex flex-col justify-between">
                <div>
                  <CardHeader>
                    <CardTitle className="text-base font-black tracking-tight text-foreground flex items-center gap-1.5">
                      Filtro AMD (Answering Machine Detection)
                    </CardTitle>
                    <CardDescription>
                      Estatísticas do filtro inteligente contra Caixa Postal Twilio.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* Ring Ratio breakdown */}
                    <div className="flex items-center gap-6">
                      <div className="relative h-28 w-28 shrink-0 flex items-center justify-center rounded-full border bg-muted/20 shadow-inner">
                        <div className="text-center">
                          <p className="text-2xl font-black text-foreground">
                            {amd.human_ratio}%
                          </p>
                          <p className="text-[8px] font-bold text-muted-foreground uppercase tracking-widest mt-0.5">
                            Contato Real
                          </p>
                        </div>
                      </div>
                      <div className="space-y-2 text-xs font-medium text-muted-foreground w-full">
                        <div className="flex justify-between items-center">
                          <span className="flex items-center gap-1.5">
                            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                            Atendimento Humano:
                          </span>
                          <span className="font-bold text-foreground">{amd.human}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="flex items-center gap-1.5">
                            <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                            Caixa Postal / Robô:
                          </span>
                          <span className="font-bold text-foreground">{amd.machine}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="flex items-center gap-1.5">
                            <span className="h-2.5 w-2.5 rounded-full bg-muted-foreground/45" />
                            Sem Resposta / Falhou:
                          </span>
                          <span className="font-bold text-foreground">{amd.no_answer + amd.busy + amd.failed}</span>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </div>

                <div className="p-5 border-t bg-muted/10 text-xs text-muted-foreground font-semibold flex gap-2 shrink-0 items-start">
                  <Info className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <span>
                    A detecção de máquina da Twilio desvia ligações improdutivas evitando desperdício de tempo e de créditos tarifários da sua operadora.
                  </span>
                </div>
              </Card>
            )}
          </div>

          {/* Time Series History chart */}
          {timeSeries.length > 0 && (
            <Card className="bg-card border-border/50 shadow-sm">
              <CardHeader>
                <CardTitle className="text-base font-black tracking-tight text-foreground flex items-center gap-1.5">
                  Volumetria de Ligações Recentes
                </CardTitle>
                <CardDescription>
                  Volume diário de chamadas disparadas e atendidas.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {/* Clean CSS/SVG Multi-bar representation */}
                <div className="h-48 flex items-end justify-between gap-2.5 pt-6 border-b border-l px-4">
                  {timeSeries.map((item, idx) => {
                    const maxCalls = Math.max(...timeSeries.map((t) => t.calls), 10);
                    const callHeight = (item.calls / maxCalls) * 100;
                    const ansHeight = (item.answered / maxCalls) * 100;

                    return (
                      <div key={idx} className="flex-1 flex flex-col items-center gap-1 group relative h-full justify-end">
                        {/* Tooltip on hover */}
                        <div className="absolute bottom-full mb-2 bg-foreground text-background text-[9px] font-bold py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity z-20 pointer-events-none text-center shadow">
                          {item.date} <br />
                          Disparos: {item.calls} <br />
                          Atendidas: {item.answered}
                        </div>

                        {/* Visual Bars overlay */}
                        <div className="w-full flex items-end gap-1 h-full">
                          <div
                            className="w-1/2 bg-primary rounded-t-sm transition-all duration-300 group-hover:brightness-110"
                            style={{ height: `${callHeight}%` }}
                          />
                          <div
                            className="w-1/2 bg-emerald-500 rounded-t-sm transition-all duration-300 group-hover:brightness-110"
                            style={{ height: `${ansHeight}%` }}
                          />
                        </div>
                        <span className="text-[9px] font-bold text-muted-foreground font-mono mt-1 shrink-0 select-none">
                          {item.date.slice(-5)}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="flex justify-center items-center gap-4 text-xs font-semibold pt-4">
                  <span className="flex items-center gap-1.5">
                    <span className="h-3 w-3 bg-primary rounded-xs" />
                    Ligações Disparadas
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-3 w-3 bg-emerald-500 rounded-xs" />
                    Ligações Atendidas
                  </span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Export Center Card */}
          <Card className="bg-card border-border/50 shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-black tracking-tight text-foreground flex items-center gap-1.5">
                <FileSpreadsheet className="h-5 w-5 text-primary" />
                Central de Exportação de Dados (Auditoria & CRM)
              </CardTitle>
              <CardDescription>
                Extraia a base de dados do VoxFlow em formato CSV para auditorias de conformidade legal, importações em CRMs de terceiros ou relatórios de faturamento.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                
                {/* Leads Export */}
                <div className="border rounded-2xl p-5 space-y-4 bg-muted/10 flex flex-col justify-between">
                  <div className="space-y-1.5">
                    <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                      Contatos CRM
                    </span>
                    <h4 className="font-bold text-sm text-foreground leading-none">Exportar Base de Leads</h4>
                    <p className="text-xs text-muted-foreground mt-1.5">
                      Baixe todos os Leads cadastrados no sistema com e-mails, notas de atendimento e qualificações associadas.
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="font-bold gap-1.5 w-full shadow-xs mt-3 shrink-0"
                    onClick={() => handleExport("leads")}
                    disabled={exportingType !== null}
                  >
                    {exportingType === "leads" ? (
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    ) : (
                      <Download className="h-4 w-4" />
                    )}
                    Exportar Leads (CSV)
                  </Button>
                </div>

                {/* Call Logs Export */}
                <div className="border rounded-2xl p-5 space-y-4 bg-muted/10 flex flex-col justify-between">
                  <div className="space-y-1.5">
                    <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                      Faturamento & Auditoria
                    </span>
                    <h4 className="font-bold text-sm text-foreground leading-none">Exportar Histórico de Chamadas</h4>
                    <p className="text-xs text-muted-foreground mt-1.5">
                      Baixe o Call Detail Record (CDR) contendo data/hora exata, duração em segundos, gravações e tarifas Twilio.
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="font-bold gap-1.5 w-full shadow-xs mt-3 shrink-0"
                    onClick={() => handleExport("calls")}
                    disabled={exportingType !== null}
                  >
                    {exportingType === "calls" ? (
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    ) : (
                      <Download className="h-4 w-4" />
                    )}
                    Exportar Chamadas (CSV)
                  </Button>
                </div>

                {/* DNC Export */}
                <div className="border rounded-2xl p-5 space-y-4 bg-muted/10 flex flex-col justify-between">
                  <div className="space-y-1.5">
                    <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                      Conformidade Legal (LGPD)
                    </span>
                    <h4 className="font-bold text-sm text-foreground leading-none">Exportar Blacklist / DNC</h4>
                    <p className="text-xs text-muted-foreground mt-1.5">
                      Baixe a lista de contatos do tipo Do-Not-Call (Não Perturbe) que solicitaram remoção das listas de discagem ativas.
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="font-bold gap-1.5 w-full shadow-xs mt-3 shrink-0"
                    onClick={() => handleExport("dnc")}
                    disabled={exportingType !== null}
                  >
                    {exportingType === "dnc" ? (
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    ) : (
                      <Download className="h-4 w-4" />
                    )}
                    Exportar Lista DNC (CSV)
                  </Button>
                </div>

              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
