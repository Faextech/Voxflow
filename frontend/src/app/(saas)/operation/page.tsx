"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  Phone,
  PhoneCall,
  PhoneOff,
  Mic,
  MicOff,
  User,
  Building,
  FileText,
  Volume2,
  Calendar,
  AlertCircle,
  Play,
  Pause,
  Loader2,
  TrendingUp,
  Bookmark,
  Activity,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { formatPhone } from "@/lib/utils";

type Agent = {
  id: number;
  status: string;
  extension: string;
  sip_username: string;
};

type CurrentCall = {
  id: number;
  call_sid: string;
  status: string;
  phone_dialed: string;
  duration_seconds: number;
};

type CurrentLead = {
  id: number;
  name: string;
  email: string | null;
  company_name: string | null;
  job_title: string | null;
  status: string;
  notes: string | null;
  phones: string[];
  primary_phone: string;
};

type Campaign = {
  id: number;
  name: string;
  status: string;
  call_script: string | null;
};

export default function OperationPage() {
  // Twilio Voice Device
  const [device, setDevice] = useState<any>(null);
  const [activeCall, setActiveCall] = useState<any>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [deviceRegistered, setDeviceRegistered] = useState(false);
  const [bridgeConnected, setBridgeConnected] = useState(false);

  // States from Backend
  const [agent, setAgent] = useState<Agent | null>(null);
  const [currentCall, setCurrentCall] = useState<CurrentCall | null>(null);
  const [currentLead, setCurrentLead] = useState<CurrentLead | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<number | null>(null);
  const [activeCampaign, setActiveCampaign] = useState<Campaign | null>(null);

  // Popup & Poller States
  const [pendingCallData, setPendingCallData] = useState<any>(null);
  const [popupOpen, setPopupOpen] = useState(false);
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [dialNumber, setDialNumber] = useState("");
  const [isDialpadOpen, setIsDialpadOpen] = useState(false);

  // Loaders & Form States
  const [loadingWorkspace, setLoadingWorkspace] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [crmNotes, setCrmNotes] = useState("");
  const [qualification, setQualification] = useState("");
  const [scheduledFor, setScheduledFor] = useState("");
  const [logs, setLogs] = useState<string[]>([]);

  // Refs for tracking
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const pollerRef = useRef<NodeJS.Timeout | null>(null);
  const activeCallRef = useRef<any>(null);

  // Add system logs
  const addLog = (message: string) => {
    const time = new Date().toLocaleTimeString("pt-BR");
    setLogs((prev) => [`[${time}] ${message}`, ...prev.slice(0, 49)]);
  };

  // Play incoming alert sound
  const playIncomingBeep = () => {
    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextClass) return;
      if (!audioCtxRef.current) {
        audioCtxRef.current = new AudioContextClass();
      }
      const ctx = audioCtxRef.current;
      if (ctx.state === "suspended") ctx.resume();

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.15);
    } catch (e) {
      console.warn("Bipe falhou:", e);
    }
  };

  // 1. Fetch campaigns and user profile
  useEffect(() => {
    async function loadCampaignsAndUser() {
      try {
        const [meRes, campaignsRes] = await Promise.all([
          fetch("/api/me"),
          fetch("/api/campaigns"),
        ]);

        if (meRes.ok) {
          const meData = await meRes.json();
          if (meData.agent_id) {
            loadAgentWorkspace(meData.agent_id);
          } else {
            setLoadingWorkspace(false);
            addLog("⚠️ Erro: Perfil do operador não encontrado.");
            toast.error("Nenhum perfil de operador associado a este usuário.");
          }
        }
        if (campaignsRes.ok) {
          const campaignsData = await campaignsRes.json();
          setCampaigns(campaignsData);
        }
      } catch (e) {
        console.error(e);
        setLoadingWorkspace(false);
      }
    }
    loadCampaignsAndUser();

    return () => {
      if (pollerRef.current) clearInterval(pollerRef.current);
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    };
  }, []);

  // Sync active campaign metadata
  useEffect(() => {
    if (selectedCampaignId) {
      const camp = campaigns.find((c) => c.id === selectedCampaignId);
      setActiveCampaign(camp || null);
    } else {
      setActiveCampaign(null);
    }
  }, [selectedCampaignId, campaigns]);

  // Load Agent workspace state
  const loadAgentWorkspace = async (agentId: number) => {
    try {
      const res = await fetch(`/api/operator/workspace/${agentId}`);
      if (res.ok) {
        const data = await res.json();
        setAgent(data.agent);
        setCurrentCall(data.current_call);
        setCurrentLead(data.current_lead);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingWorkspace(false);
    }
  };

  // Start polling Twilio pending calls / conferences
  const startPendingCallPoller = (agentId: number) => {
    if (pollerRef.current) clearInterval(pollerRef.current);

    let lastLoggedCallId: number | null = null;

    pollerRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/twilio/pending-call/${agentId}`);
        if (!res.ok) return;
        const data = await res.json();

        // Lead disconnected or finished
        if (!data.has_call) {
          if (popupOpen) {
            setPopupOpen(false);
            setPendingCallData(null);
            addLog("📴 Lead desligou — chamada encerrada.");
          }
          return;
        }

        // We have an active conference incoming!
        if (data.show_popup || data.status === "answered_waiting_agent") {
          setPendingCallData(data);
          const currentCallId = data.call_id || data.db_call_id;

          if (!popupOpen) {
            setPopupOpen(true);
            playIncomingBeep();
            addLog(`🔔 Novo lead em linha: ${data.lead?.name || "Lead"} (${data.phone_number})`);
          }
        }
      } catch (e) {
        console.error(e);
      }
    }, 850);
  };

  // Initialize Twilio Voice SDK Device
  const handleConnectWebphone = async () => {
    if (!agent) {
      toast.error("Carregando credenciais...");
      return;
    }

    addLog("🔌 Solicitando token de telefonia Twilio...");
    try {
      // 1. Get voice token
      const tokenRes = await fetch(`/api/webphone/token/${agent.id}`);
      if (!tokenRes.ok) {
        const err = await tokenRes.json();
        throw new Error(err.error || "Erro ao obter token do Twilio.");
      }
      const tokenData = await tokenRes.json();

      // 2. Import Twilio Voice SDK dynamically (client-side only)
      const { Device } = await import("@twilio/voice-sdk");

      // 3. Setup device instance
      const twilioDevice = new Device(tokenData.token, {
        logLevel: 1,
        codecPreferences: ["opus", "pcmu"] as any,
        closeProtection: true,
        edge: ["sao-paulo", "ashburn"],
      });

      twilioDevice.on("registering", () => {
        addLog("🛰️ Registrando webphone no Twilio Edge...");
      });

      twilioDevice.on("registered", () => {
        setDeviceRegistered(true);
        addLog("✅ Webphone registrado e pronto!");
        toast.success("Telefonia conectada com sucesso!");

        // Start Persistent Call Center Bridge
        setTimeout(() => connectPersistentBridge(twilioDevice, agent.id), 1000);
      });

      twilioDevice.on("error", (error: any) => {
        addLog(`❌ Erro no Webphone: ${error.message}`);
        toast.error(`Falha no webphone: ${error.message}`);
      });

      twilioDevice.on("incoming", (incomingCall) => {
        addLog("⚠️ Ignorando chamada de entrada SIP direta (usar discador)");
        incomingCall.ignore();
      });

      await twilioDevice.register();
      setDevice(twilioDevice);

      // Start poller for incoming conferences
      startPendingCallPoller(agent.id);
    } catch (e: any) {
      addLog(`❌ Falha na conexão: ${e.message}`);
      toast.error(e.message);
    }
  };

  // Connect operator to Twilio persistent conference bridge (Call Center flow)
  const connectPersistentBridge = async (deviceInstance: any, agentId: number) => {
    addLog("🌉 Estabelecendo Ponte de Áudio Persistente...");
    try {
      const bridge = await deviceInstance.connect({
        params: {
          action: "persistent_bridge",
          agent_id: String(agentId),
          aid: String(agentId),
        },
      });

      activeCallRef.current = bridge;
      setActiveCall(bridge);

      bridge.on("accept", () => {
        setBridgeConnected(true);
        addLog("✅ Ponte de áudio persistente ativa! Pronta para injetar chamadas.");
      });

      bridge.on("disconnect", () => {
        setBridgeConnected(false);
        setActiveCall(null);
        activeCallRef.current = null;
        addLog("⚠️ Ponte de áudio persistente desconectada.");
      });
    } catch (e: any) {
      addLog(`❌ Falha ao conectar ponte: ${e.message}`);
    }
  };

  // Join the waiting lead's conference bridge
  const handleAnswerCall = async () => {
    if (!pendingCallData) return;
    addLog(`🎙️ Conectando operador ao lead: ${pendingCallData.lead?.name || "Lead"}`);

    try {
      if (pendingCallData.audio_bridged) {
        // Persistent bridge handles the audio injection automatically!
        addLog("✅ Áudio integrado automaticamente pela Persistent Bridge.");
        setPopupOpen(false);
        startCallTimer();
        loadAgentWorkspace(agent!.id);
        return;
      }

      if (device) {
        const confCall = await device.connect({
          params: {
            conference_name: pendingCallData.conference_name,
            conf: pendingCallData.conference_name,
            agent_id: String(agent!.id),
          },
        });

        activeCallRef.current = confCall;
        setActiveCall(confCall);
        setPopupOpen(false);
        startCallTimer();

        confCall.on("disconnect", () => {
          stopCallTimer();
          setActiveCall(null);
          activeCallRef.current = null;
          addLog("📴 Chamada encerrada pelo lead.");
        });
      }
    } catch (e: any) {
      addLog(`❌ Erro ao atender: ${e.message}`);
    }
  };

  // Hangup active lead leg
  const handleHangupCall = async () => {
    addLog("🔌 Desconectando lead Twilio...");
    try {
      const res = await fetch("/api/dialer/hangup-lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_id: agent?.id,
          conference_name: pendingCallData?.conference_name,
        }),
      });

      if (res.ok) {
        addLog("✅ Chamada encerrada com sucesso.");
        stopCallTimer();
        if (activeCall && !bridgeConnected) {
          activeCall.disconnect();
          setActiveCall(null);
          activeCallRef.current = null;
        }
        setPopupOpen(false);
        loadAgentWorkspace(agent!.id);
      }
    } catch (e: any) {
      addLog(`❌ Erro ao desligar: ${e.message}`);
    }
  };

  // Call Timer functions
  const startCallTimer = () => {
    setTimerSeconds(0);
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    timerIntervalRef.current = setInterval(() => {
      setTimerSeconds((s) => s + 1);
    }, 1000);
  };

  const stopCallTimer = () => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
  };

  const formatTimer = (sec: number) => {
    const min = Math.floor(sec / 60);
    const s = sec % 60;
    return `${min.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  // Save CRM and classify call disposition
  const handleSaveCRM = async () => {
    const targetLeadId = pendingCallData?.lead_id || currentLead?.id;
    const targetCallId = pendingCallData?.call_id || currentCall?.id;

    if (!targetLeadId) {
      toast.error("Nenhum lead ativo carregado.");
      return;
    }
    if (!qualification) {
      toast.error("Selecione uma qualificação de atendimento");
      return;
    }

    setActionLoading(true);
    addLog(`💾 Salvando CRM para o lead ID #${targetLeadId} [${qualification}]...`);

    try {
      const res = await fetch("/api/operator/workspace/save_crm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_id: agent?.id,
          lead_id: targetLeadId,
          call_id: targetCallId,
          qualification,
          notes: crmNotes,
        }),
      });

      if (res.ok) {
        toast.success("Atendimento salvo com sucesso no CRM!");
        addLog("✅ CRM atualizado. Ficha do lead liberada.");
        setCrmNotes("");
        setQualification("");
        setPendingCallData(null);
        setPopupOpen(false);
        stopCallTimer();
        setTimerSeconds(0);
        loadAgentWorkspace(agent!.id);
      } else {
        toast.error("Erro ao salvar qualificação do CRM");
      }
    } catch {
      toast.error("Erro ao enviar CRM");
    } finally {
      setActionLoading(false);
    }
  };

  // Schedule callback and save CRM
  const handleScheduleCallback = async () => {
    const targetLeadId = pendingCallData?.lead_id || currentLead?.id;
    if (!targetLeadId) {
      toast.error("Nenhum lead ativo carregado.");
      return;
    }
    if (!scheduledFor) {
      toast.error("Selecione data e hora para o retorno.");
      return;
    }

    setActionLoading(true);
    addLog(`⏰ Agendando retorno para o lead ID #${targetLeadId} [${scheduledFor}]...`);

    try {
      // First save standard CRM
      await fetch("/api/operator/workspace/save_crm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_id: agent?.id,
          lead_id: targetLeadId,
          qualification: "retorno",
          notes: `${crmNotes} | Agendado para: ${scheduledFor}`,
        }),
      });

      // Second, register callback queue
      const res = await fetch("/api/operator/workspace/schedule_callback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_id: agent?.id,
          lead_id: targetLeadId,
          scheduled_for: scheduledFor,
        }),
      });

      if (res.ok) {
        toast.success("Retorno agendado e CRM salvo!");
        addLog("✅ Agendamento de retorno efetuado.");
        setCrmNotes("");
        setQualification("");
        setScheduledFor("");
        setPendingCallData(null);
        setPopupOpen(false);
        stopCallTimer();
        setTimerSeconds(0);
        loadAgentWorkspace(agent!.id);
      } else {
        toast.error("Não foi possível agendar o retorno");
      }
    } catch {
      toast.error("Erro de conexão ao agendar retorno");
    } finally {
      setActionLoading(false);
    }
  };

  // Skip lead number (next phone)
  const handleSkipLead = async () => {
    const targetLeadId = pendingCallData?.lead_id || currentLead?.id;
    if (!targetLeadId) {
      toast.error("Nenhum lead carregado para pular");
      return;
    }

    setActionLoading(true);
    addLog(`⏩ Pulando número atual do lead ID #${targetLeadId}...`);

    try {
      const res = await fetch("/api/operator/workspace/skip_phone", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_id: agent?.id,
          lead_id: targetLeadId,
          campaign_id: selectedCampaignId,
        }),
      });

      if (res.ok) {
        addLog("✅ Número pulado com sucesso.");
        toast.info("Próximo telefone selecionado.");
        setPopupOpen(false);
        setPendingCallData(null);
        loadAgentWorkspace(agent!.id);
      } else {
        toast.error("Erro ao pular telefone");
      }
    } catch {
      toast.error("Erro na requisição para pular lead");
    } finally {
      setActionLoading(false);
    }
  };

  // Dialer manual outgoing call
  const handleMakeManualCall = async () => {
    if (!dialNumber) {
      toast.error("Digite ou selecione um número");
      return;
    }
    addLog(`📞 Discando manualmente para o número: ${dialNumber}`);
    // Simulated or direct call depending on conference bridge
    toast.info(`Ligando para ${dialNumber}...`);
  };

  // Update Operator status
  const handleUpdateStatus = async (status: string) => {
    if (!agent) return;
    try {
      const res = await fetch("/api/operator/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: agent.id, status }),
      });
      if (res.ok) {
        setAgent((prev) => (prev ? { ...prev, status } : null));
        addLog(`👤 Status do operador alterado para: ${status}`);
        toast.success(`Status: ${status}`);
      }
    } catch {
      toast.error("Erro ao atualizar status");
    }
  };

  // Dialpad press number
  const handlePressKey = (key: string) => {
    setDialNumber((prev) => prev + key);
  };

  // Campaign control (Start/Pause)
  const handleToggleCampaign = async (status: "running" | "paused") => {
    if (!selectedCampaignId) {
      toast.error("Selecione uma campanha");
      return;
    }

    const endpoint = `/api/campaign/${selectedCampaignId}/${status === "running" ? "start" : "pause"}`;
    try {
      const res = await fetch(endpoint, { method: "POST" });
      if (res.ok) {
        setCampaigns((prev) =>
          prev.map((c) => (c.id === selectedCampaignId ? { ...c, status: status === "running" ? "running" : "paused" } : c))
        );
        addLog(`Campaign #${selectedCampaignId}: status alterado para ${status}`);
        toast.success(`Campanha ${status === "running" ? "iniciada" : "pausada"}`);
      }
    } catch {
      toast.error("Erro ao alterar status da campanha");
    }
  };

  const activeDisplayLead = pendingCallData?.lead || currentLead;
  const activeDisplayCall = pendingCallData || currentCall;

  if (loadingWorkspace) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Loader2 className="h-10 w-10 border-4 border-primary border-t-transparent rounded-full animate-spin text-primary" />
        <p className="text-sm text-muted-foreground font-medium animate-pulse">
          Inicializando terminal do operador VoxFlow...
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Discador / Webphone</h1>
          <p className="text-muted-foreground mt-1">
            Terminal de atendimento de voz integrando WebRTC Twilio e qualificação CRM rápida.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Webphone State indicators */}
          {deviceRegistered ? (
            <Badge className="bg-emerald-500 hover:bg-emerald-600 text-white gap-1 px-3 py-1 text-xs">
              <ShieldCheck className="h-3.5 w-3.5" />
              Webphone Ativo
            </Badge>
          ) : (
            <Button size="sm" onClick={handleConnectWebphone} className="gap-1.5 shadow-md shadow-primary/20">
              <Volume2 className="h-4 w-4" />
              Conectar Webphone
            </Button>
          )}

          {bridgeConnected && (
            <Badge className="bg-sky-500 text-white gap-1 px-3 py-1 text-xs">
              <Activity className="h-3.5 w-3.5" />
              Persistência Conectada
            </Badge>
          )}
        </div>
      </div>

      {/* 3-Column Premium Call Center Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* COLUMN 1: Agent & Logs Feed (4 cols) */}
        <div className="lg:col-span-3 space-y-6">
          {/* Agent Card */}
          <Card className="border-border/50 shadow-sm relative overflow-hidden">
            <CardHeader className="pb-3 border-b">
              <CardTitle className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
                Operador
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-base">
                  {agent?.sip_username?.charAt(0).toUpperCase() || "O"}
                </div>
                <div>
                  <p className="font-bold text-foreground text-sm leading-none">
                    {agent?.sip_username || "Operador"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Ramal SIP: {agent?.extension || "Sem ramal"}
                  </p>
                </div>
              </div>

              {/* Status Select */}
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold text-muted-foreground uppercase">
                  Status de Operação
                </Label>
                <select
                  value={agent?.status || "offline"}
                  onChange={(e) => handleUpdateStatus(e.target.value)}
                  className="h-9 w-full rounded-lg border border-input bg-background px-3 py-1 text-xs font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="offline">🔴 Indisponível / Offline</option>
                  <option value="available">🟢 Disponível / Recebendo</option>
                  <option value="break">⏸️ Pausa / Intervalo</option>
                </select>
              </div>

              {/* Campaign Controller select */}
              <div className="space-y-2 border-t pt-4">
                <Label className="text-xs font-semibold text-muted-foreground uppercase">
                  Campanha de Discagem
                </Label>
                <select
                  value={selectedCampaignId || ""}
                  onChange={(e) => setSelectedCampaignId(Number(e.target.value) || null)}
                  className="h-9 w-full rounded-lg border border-input bg-background px-3 py-1 text-xs font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="">Ligar Manualmente</option>
                  {campaigns.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>

                {selectedCampaignId && activeCampaign && (
                  <div className="flex gap-2 mt-2">
                    {activeCampaign.status !== "running" ? (
                      <Button
                        size="sm"
                        className="flex-1 text-xs font-semibold"
                        onClick={() => handleToggleCampaign("running")}
                      >
                        <Play className="h-3 w-3 mr-1" /> Iniciar
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        className="flex-1 text-xs font-semibold text-amber-500 border-amber-500/20 hover:bg-amber-500/5"
                        onClick={() => handleToggleCampaign("paused")}
                      >
                        <Pause className="h-3 w-3 mr-1" /> Pausar
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Call / System Live Log */}
          <Card className="border-border/50 shadow-sm">
            <CardHeader className="pb-3 border-b">
              <CardTitle className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
                Atividade em Tempo Real
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="bg-muted/40 rounded-xl p-3 border h-[180px] overflow-y-auto font-mono text-[10px] space-y-1.5 leading-relaxed">
                {logs.length === 0 ? (
                  <span className="text-muted-foreground italic">Aguardando eventos do sistema...</span>
                ) : (
                  logs.map((log, i) => <div key={i}>{log}</div>)
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* COLUMN 2: Active Call & Dialer (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Active Call Interface */}
          <Card className="border-border/50 shadow-sm relative overflow-hidden min-h-[300px] flex flex-col justify-between">
            <div className="absolute top-0 right-0 h-32 w-32 bg-primary/5 rounded-full -mr-12 -mt-12" />
            
            <CardHeader className="pb-3 border-b shrink-0">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
                  Chamada Ativa
                </CardTitle>
                {activeDisplayCall?.status && (
                  <Badge variant={activeDisplayCall.status === "in_call" || activeDisplayCall.status === "answered" ? "success" : "secondary"}>
                    {activeDisplayCall.status}
                  </Badge>
                )}
              </div>
            </CardHeader>

            <CardContent className="py-6 flex-1 flex flex-col items-center justify-center text-center">
              {activeDisplayLead ? (
                <div className="space-y-4 w-full">
                  <div>
                    <div className="h-14 w-14 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xl mx-auto shadow-sm">
                      {activeDisplayLead.name?.charAt(0).toUpperCase() || "L"}
                    </div>
                    <h2 className="text-xl font-bold text-foreground tracking-tight mt-3">
                      {activeDisplayLead.name}
                    </h2>
                    <p className="text-xs text-muted-foreground mt-1 font-semibold flex items-center justify-center gap-1.5">
                      <Building className="h-3.5 w-3.5 text-muted-foreground/60" />
                      {activeDisplayLead.company_name || "Empresa não vinculada"}
                    </p>
                  </div>

                  <div className="text-3xl font-extrabold text-foreground tracking-tight font-mono">
                    {formatTimer(timerSeconds)}
                  </div>

                  <div className="font-mono text-sm font-bold text-primary mt-1">
                    {formatPhone(activeDisplayLead.numero_1)}
                  </div>

                  {/* Hangup button */}
                  <div className="flex justify-center pt-2">
                    <Button
                      variant="destructive"
                      onClick={handleHangupCall}
                      className="rounded-full h-12 w-12 p-0 shadow-lg shadow-destructive/20"
                    >
                      <PhoneOff className="h-5 w-5" />
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mx-auto text-muted-foreground">
                    <Phone className="h-6 w-6" />
                  </div>
                  <p className="text-xs text-muted-foreground font-semibold">
                    Aguardando lead da campanha ou discagem manual...
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Script Panel */}
          {activeCampaign?.call_script && (
            <Card className="border-border/50 shadow-sm">
              <CardHeader className="pb-3 border-b">
                <CardTitle className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <FileText className="h-4 w-4 text-primary" />
                  Roteiro de Abordagem
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-4 text-xs text-foreground bg-muted/20 p-4 rounded-xl border leading-relaxed whitespace-pre-line max-h-[160px] overflow-y-auto">
                {activeCampaign.call_script}
              </CardContent>
            </Card>
          )}

          {/* Dialpad Controller */}
          <Card className="border-border/50 shadow-sm">
            <CardHeader className="pb-2 border-b shrink-0 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
                Teclado Numérico
              </CardTitle>
              <Button size="sm" variant="ghost" onClick={() => setIsDialpadOpen(!isDialpadOpen)} className="h-8 text-xs">
                {isDialpadOpen ? "Ocultar" : "Mostrar"}
              </Button>
            </CardHeader>

            {isDialpadOpen && (
              <CardContent className="pt-4 space-y-4">
                <div className="relative">
                  <Input
                    placeholder="Discar número..."
                    value={dialNumber}
                    onChange={(e) => setDialNumber(e.target.value.replace(/[^\d*#+]/g, ""))}
                    className="pr-10 font-mono text-center text-lg font-semibold tracking-wider"
                  />
                  {dialNumber && (
                    <button
                      onClick={() => setDialNumber("")}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground"
                    >
                      Limpar
                    </button>
                  )}
                </div>

                {/* Dialpad keys grid */}
                <div className="grid grid-cols-3 gap-2 max-w-[240px] mx-auto">
                  {["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"].map((key) => (
                    <Button
                      key={key}
                      variant="outline"
                      onClick={() => handlePressKey(key)}
                      className="h-10 text-base font-bold rounded-lg border-border/60 hover:bg-accent"
                    >
                      {key}
                    </Button>
                  ))}
                </div>

                <div className="flex gap-2">
                  <Button onClick={handleMakeManualCall} className="flex-1 font-semibold">
                    <Phone className="h-4 w-4 mr-2" /> Discar Manual
                  </Button>
                </div>
              </CardContent>
            )}
          </Card>
        </div>

        {/* COLUMN 3: CRM Form & Scheduling (3 cols) */}
        <div className="lg:col-span-4 space-y-6">
          <Card className="border-border/50 shadow-sm">
            <CardHeader className="pb-3 border-b">
              <CardTitle className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Bookmark className="h-4 w-4 text-primary" />
                Qualificação CRM
              </CardTitle>
            </CardHeader>

            <CardContent className="pt-4 space-y-4">
              {/* Disposition Selection */}
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold text-muted-foreground uppercase">
                  Qualificação do Lead *
                </Label>
                <select
                  value={qualification}
                  onChange={(e) => setQualification(e.target.value)}
                  className="h-9 w-full rounded-lg border border-input bg-background px-3 py-1 text-xs font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="">Selecione uma qualificação...</option>
                  <option value="ganho">🏆 Fechado / Ganho</option>
                  <option value="reuniao_agendada">📅 Reunião Agendada</option>
                  <option value="proposta_enviada">📩 Proposta Enviada</option>
                  <option value="atendeu">📞 Contato Efetivo / Sem Interesse</option>
                  <option value="caixa_postal">🤖 Caixa Postal / Secretária</option>
                  <option value="nao_atendeu">❌ Sem Resposta / Não atendeu</option>
                  <option value="ocupado">📵 Ocupado</option>
                  <option value="numero_invalido">🚫 Número Inválido / DNC</option>
                </select>
              </div>

              {/* Notes */}
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold text-muted-foreground uppercase">
                  Observações de Negócio
                </Label>
                <textarea
                  value={crmNotes}
                  onChange={(e) => setCrmNotes(e.target.value)}
                  placeholder="Anotações comerciais sobre a conversa..."
                  className="flex w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[90px] resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* CRM Save actions */}
              <div className="flex gap-2">
                <Button
                  onClick={handleSaveCRM}
                  disabled={!activeDisplayLead}
                  loading={actionLoading}
                  className="flex-1 font-semibold"
                >
                  Salvar CRM
                </Button>
                <Button
                  variant="outline"
                  onClick={handleSkipLead}
                  disabled={!activeDisplayLead}
                  loading={actionLoading}
                  className="gap-1 font-semibold"
                  title="Pular número e tentar o próximo"
                >
                  Pular <ArrowRight className="h-4 w-4" />
                </Button>
              </div>

              {/* Callback Scheduler Queue */}
              <div className="border-t pt-4 space-y-3">
                <Label className="text-xs font-bold text-muted-foreground uppercase flex items-center gap-1">
                  <Calendar className="h-4 w-4 text-primary" />
                  Agendar Retorno Automático
                </Label>

                <Input
                  type="datetime-local"
                  value={scheduledFor}
                  onChange={(e) => setScheduledFor(e.target.value)}
                  className="text-xs"
                />

                <Button
                  onClick={handleScheduleCallback}
                  variant="outline"
                  disabled={!activeDisplayLead || !scheduledFor}
                  loading={actionLoading}
                  className="w-full text-xs font-bold"
                >
                  Agendar e Salvar CRM
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

      </div>

      {/* Incoming Call Popup Overlay */}
      {popupOpen && pendingCallData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="relative bg-card rounded-2xl shadow-2xl border w-full max-w-md mx-4 overflow-hidden p-6 text-center space-y-6 animate-in zoom-in-95 duration-200">
            
            <div className="h-16 w-16 bg-primary/10 text-primary flex items-center justify-center rounded-full mx-auto animate-bounce shadow-sm">
              <PhoneCall className="h-8 w-8" />
            </div>

            <div className="space-y-2">
              <span className="text-[10px] font-bold text-primary uppercase tracking-widest bg-primary/10 px-2 py-0.5 rounded-full">
                Chamada Receptiva / Campanha
              </span>
              <h2 className="text-2xl font-black text-foreground tracking-tight">
                {pendingCallData.lead?.name || "Lead da Campanha"}
              </h2>
              <p className="text-xs text-muted-foreground font-semibold">
                {pendingCallData.phone_number ? formatPhone(pendingCallData.phone_number) : "Telefone ocultado"}
              </p>
              {pendingCallData.lead?.company_name && (
                <p className="text-xs text-muted-foreground">
                  Empresa: <span className="font-semibold text-foreground">{pendingCallData.lead.company_name}</span>
                </p>
              )}
            </div>

            <div className="flex gap-3 pt-2">
              <Button
                variant="outline"
                className="flex-1 font-bold text-destructive hover:bg-destructive/5 border-destructive/20"
                onClick={handleHangupCall}
              >
                Recusar
              </Button>
              <Button
                className="flex-1 font-bold shadow-lg shadow-primary/20"
                onClick={handleAnswerCall}
              >
                Atender
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
