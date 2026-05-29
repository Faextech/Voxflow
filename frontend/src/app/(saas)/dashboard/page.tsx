"use client";

import { useEffect, useState } from "react";
import {
  TrendingUp,
  Phone,
  PhoneCall,
  DollarSign,
  AlertTriangle,
  Award,
  Clock,
  ArrowUpRight,
  ShieldAlert,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { formatCurrency } from "@/lib/utils";

type DashboardData = {
  deals: {
    total: number;
    won: number;
    lost: number;
    open: number;
    conversion_rate: number;
    avg_days_to_close: number;
    avg_ticket: number;
    total_revenue: number;
    total_lost_value: number;
  };
  leads: {
    total: number;
  };
  calls: {
    total: number;
    answered: number;
    no_answer: number;
    busy: number;
    voicemail: number;
    contact_rate: number;
    avg_duration_seconds: number;
  };
};

type Alert = {
  type: string;
  severity: "critical" | "warning";
  title: string;
  message: string;
  campaign_name: string | null;
  value: number;
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [dashRes, alertsRes] = await Promise.all([
          fetch("/api/analytics/dashboard?period=month"),
          fetch("/api/analytics/alerts"),
        ]);

        if (dashRes.ok) {
          const dashData = await dashRes.json();
          setData(dashData);
        }
        if (alertsRes.ok) {
          const alertsData = await alertsRes.json();
          setAlerts(alertsData.alerts ?? []);
        }
      } catch (e) {
        console.error("Erro ao carregar dados do dashboard", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="h-10 w-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-muted-foreground font-medium animate-pulse">
          Carregando indicadores do VoxFlow...
        </p>
      </div>
    );
  }

  const deals = data?.deals;
  const calls = data?.calls;
  const leads = data?.leads;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Visão geral em tempo real de chamadas, leads e desempenho comercial.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="px-3 py-1.5 text-xs font-semibold bg-muted/30">
            Período: Últimos 30 dias
          </Badge>
          <Button size="sm" asChild>
            <Link href="/operation">
              <Zap className="h-4 w-4 mr-2" />
              Abrir Discador
            </Link>
          </Button>
        </div>
      </div>

      {/* Critical Alerts / Warnings Banner */}
      {alerts.length > 0 && (
        <div className="space-y-3">
          {alerts.map((alert, index) => (
            <div
              key={index}
              className={`p-4 rounded-xl border flex items-start gap-3 shadow-sm transition-all hover:translate-x-1 duration-200 ${
                alert.severity === "critical"
                  ? "bg-destructive/5 border-destructive/20 text-destructive"
                  : "bg-amber-500/5 border-amber-500/20 text-amber-600 dark:text-amber-500"
              }`}
            >
              {alert.severity === "critical" ? (
                <ShieldAlert className="h-5 w-5 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
              )}
              <div className="flex-1">
                <h4 className="font-semibold text-sm">{alert.title}</h4>
                <p className="text-xs opacity-90 mt-1">{alert.message}</p>
              </div>
              {alert.type === "low_balance" && (
                <Button size="sm" variant="outline" className="shrink-0 text-xs border-current" asChild>
                  <Link href="/settings">Recarregar</Link>
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* High-Fidelity Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Total Leads */}
        <Card className="border-border/50 shadow-sm relative overflow-hidden group hover:shadow-md transition-all duration-300">
          <div className="absolute top-0 right-0 h-24 w-24 bg-primary/5 rounded-full -mr-8 -mt-8 transition-transform group-hover:scale-110" />
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
              Total de Leads
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-foreground tracking-tight">
              {leads?.total ?? 0}
            </div>
            <p className="text-[10px] text-muted-foreground mt-1.5 flex items-center gap-1 font-medium">
              <span className="text-emerald-500 flex items-center font-bold">
                +12%
                <ArrowUpRight className="h-3 w-3" />
              </span>
              em relação ao mês anterior
            </p>
          </CardContent>
        </Card>

        {/* Outbound Calls */}
        <Card className="border-border/50 shadow-sm relative overflow-hidden group hover:shadow-md transition-all duration-300">
          <div className="absolute top-0 right-0 h-24 w-24 bg-sky-500/5 rounded-full -mr-8 -mt-8 transition-transform group-hover:scale-110" />
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
              Chamadas Realizadas
            </CardTitle>
            <Phone className="h-4 w-4 text-sky-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-foreground tracking-tight">
              {calls?.total ?? 0}
            </div>
            <p className="text-[10px] text-muted-foreground mt-1.5 flex items-center gap-1 font-medium">
              Taxa de atendimento: <span className="font-bold text-sky-500">{calls?.contact_rate ?? 0}%</span>
            </p>
          </CardContent>
        </Card>

        {/* Won Value / Revenue */}
        <Card className="border-border/50 shadow-sm relative overflow-hidden group hover:shadow-md transition-all duration-300">
          <div className="absolute top-0 right-0 h-24 w-24 bg-emerald-500/5 rounded-full -mr-8 -mt-8 transition-transform group-hover:scale-110" />
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
              Receita Conquistada
            </CardTitle>
            <DollarSign className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-foreground tracking-tight">
              {formatCurrency(deals?.total_revenue ?? 0)}
            </div>
            <p className="text-[10px] text-muted-foreground mt-1.5 flex items-center gap-1 font-medium">
              Ticket Médio: <span className="font-bold text-emerald-600 dark:text-emerald-400">{formatCurrency(deals?.avg_ticket ?? 0)}</span>
            </p>
          </CardContent>
        </Card>

        {/* Conversion Rate */}
        <Card className="border-border/50 shadow-sm relative overflow-hidden group hover:shadow-md transition-all duration-300">
          <div className="absolute top-0 right-0 h-24 w-24 bg-indigo-500/5 rounded-full -mr-8 -mt-8 transition-transform group-hover:scale-110" />
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
              Conversão de Vendas
            </CardTitle>
            <Award className="h-4 w-4 text-indigo-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-foreground tracking-tight">
              {deals?.conversion_rate ?? 0}%
            </div>
            <p className="text-[10px] text-muted-foreground mt-1.5 flex items-center gap-1 font-medium">
              Tempo de fechamento: <span className="font-bold text-indigo-500">{deals?.avg_days_to_close ?? 0} dias</span>
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Analysis Block */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Calls Quality Breakdown */}
        <Card className="border-border/50">
          <CardHeader>
            <CardTitle className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-2">
              <PhoneCall className="h-4 w-4 text-primary" />
              Breakdown de Atendimento
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Horizontal progress visualization for Call results */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-emerald-500">Atendidas ({calls?.answered ?? 0})</span>
                <span className="text-muted-foreground">
                  {calls?.total ? Math.round((calls.answered / calls.total) * 100) : 0}%
                </span>
              </div>
              <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 transition-all duration-500"
                  style={{ width: `${calls?.total ? (calls.answered / calls.total) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-amber-500">Caixa Postal ({calls?.voicemail ?? 0})</span>
                <span className="text-muted-foreground">
                  {calls?.total ? Math.round((calls.voicemail / calls.total) * 100) : 0}%
                </span>
              </div>
              <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-amber-500 transition-all duration-500"
                  style={{ width: `${calls?.total ? (calls.voicemail / calls.total) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-rose-500">Não Atendeu ({calls?.no_answer ?? 0})</span>
                <span className="text-muted-foreground">
                  {calls?.total ? Math.round((calls.no_answer / calls.total) * 100) : 0}%
                </span>
              </div>
              <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-rose-500 transition-all duration-500"
                  style={{ width: `${calls?.total ? (calls.no_answer / calls.total) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-gray-500">Ocupado ({calls?.busy ?? 0})</span>
                <span className="text-muted-foreground">
                  {calls?.total ? Math.round((calls.busy / calls.total) * 100) : 0}%
                </span>
              </div>
              <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-gray-500 transition-all duration-500"
                  style={{ width: `${calls?.total ? (calls.busy / calls.total) * 100 : 0}%` }}
                />
              </div>
            </div>

            <div className="pt-4 border-t border-border/50 flex justify-between items-center text-xs font-medium text-muted-foreground">
              <div className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5" />
                Duração média das chamadas
              </div>
              <span className="font-bold text-foreground text-sm">
                {calls?.avg_duration_seconds ?? 0}s
              </span>
            </div>
          </CardContent>
        </Card>

        {/* CRM Pipeline Funnel Overview */}
        <Card className="border-border/50">
          <CardHeader>
            <CardTitle className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-2">
              <Award className="h-4 w-4 text-primary" />
              Resultados de Vendas
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Visual breakdown metrics */}
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="p-3 bg-muted/40 rounded-xl">
                <p className="text-xs text-muted-foreground font-semibold">Negócios Totais</p>
                <p className="text-xl font-extrabold text-foreground mt-1">{deals?.total ?? 0}</p>
              </div>
              <div className="p-3 bg-emerald-500/5 border border-emerald-500/10 rounded-xl">
                <p className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold">Ganhos</p>
                <p className="text-xl font-extrabold text-emerald-600 dark:text-emerald-400 mt-1">
                  {deals?.won ?? 0}
                </p>
              </div>
              <div className="p-3 bg-rose-500/5 border border-rose-500/10 rounded-xl">
                <p className="text-xs text-rose-600 dark:text-rose-400 font-semibold">Perdidos</p>
                <p className="text-xl font-extrabold text-rose-600 dark:text-rose-400 mt-1">
                  {deals?.lost ?? 0}
                </p>
              </div>
            </div>

            <div className="pt-2 space-y-3">
              <div className="flex justify-between items-center text-xs font-semibold">
                <span className="text-muted-foreground">Valor em Negócios Perdidos</span>
                <span className="text-rose-500">{formatCurrency(deals?.total_lost_value ?? 0)}</span>
              </div>
              <div className="flex justify-between items-center text-xs font-semibold">
                <span className="text-muted-foreground">Negócios Abertos no Funnel</span>
                <span className="text-indigo-500">{deals?.open ?? 0} ativos</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
