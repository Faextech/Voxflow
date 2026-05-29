"use client";

import { useEffect, useState } from "react";
import {
  Settings,
  Building,
  Phone,
  ShieldAlert,
  Trash2,
  Save,
  CheckCircle2,
  AlertTriangle,
  Play,
  Lock,
  Smartphone,
  RefreshCw,
  Copy,
  Eye,
  EyeOff,
  Loader2,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

type TwilioSettings = {
  account_sid: string;
  auth_token: string;
  phone_number: string;
  twiml_app_sid: string | null;
  voice_recording: string; // none, local, twilio
  speech_to_text: boolean;
};

type CompanySettings = {
  id: number;
  name: string;
  created_at: string;
};

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<"company" | "twilio" | "2fa" | "maintenance">("company");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [testingTwilio, setTestingTwilio] = useState(false);

  // States for configs
  const [company, setCompany] = useState<CompanySettings | null>(null);
  const [twilio, setTwilio] = useState<TwilioSettings>({
    account_sid: "",
    auth_token: "",
    phone_number: "",
    twiml_app_sid: "",
    voice_recording: "none",
    speech_to_text: false,
  });

  // Password visibility
  const [showAuthToken, setShowAuthToken] = useState(false);

  // 2FA Setup state
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false);
  const [qrCodeUrl, setQrCodeUrl] = useState<string | null>(null);
  const [secretKey, setSecretKey] = useState<string | null>(null);
  const [verificationCode, setVerificationCode] = useState("");
  const [copiedKey, setCopiedKey] = useState(false);

  // Wipe protection
  const [wipeConfirmText, setWipeConfirmText] = useState("");
  const [wipeOpen, setWipeOpen] = useState(false);

  // Load configuration
  useEffect(() => {
    async function loadConfig() {
      setLoading(true);
      try {
        const [compRes, twiRes, mfaRes] = await Promise.all([
          fetch("/api/company"),
          fetch("/api/twilio"),
          fetch("/api/2fa/status"),
        ]);

        if (compRes.ok) {
          const compData = await compRes.json();
          setCompany(compData.company || compData);
        }
        if (twiRes.ok) {
          const twiData = await twiRes.json();
          setTwilio(twiData.twilio || twiData);
        }
        if (mfaRes.ok) {
          const mfaData = await mfaRes.json();
          setTwoFactorEnabled(mfaData.enabled);
        }
      } catch (e) {
        console.error("Erro ao carregar configurações", e);
        toast.error("Erro ao obter configurações do servidor");
      } finally {
        setLoading(false);
      }
    }
    loadConfig();
  }, []);

  // Save Company settings
  const handleSaveCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!company?.name) {
      toast.error("Nome da empresa é obrigatório");
      return;
    }
    setActionLoading(true);
    try {
      const res = await fetch("/api/company", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: company.name }),
      });
      if (res.ok) {
        toast.success("Informações da empresa salvas com sucesso!");
      } else {
        const data = await res.json();
        toast.error(data.error || "Não foi possível salvar os dados");
      }
    } catch {
      toast.error("Erro na comunicação");
    } finally {
      setActionLoading(false);
    }
  };

  // Save Twilio settings
  const handleSaveTwilio = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      const res = await fetch("/api/twilio", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(twilio),
      });
      if (res.ok) {
        toast.success("Credenciais Twilio configuradas!");
      } else {
        const data = await res.json();
        toast.error(data.error || "Erro ao salvar credenciais");
      }
    } catch {
      toast.error("Erro na comunicação");
    } finally {
      setActionLoading(false);
    }
  };

  // Test Twilio Credentials connection
  const handleTestTwilio = async () => {
    setTestingTwilio(true);
    try {
      const res = await fetch("/api/twilio/test", {
        method: "POST",
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast.success(data.message || "Conexão com a API Twilio realizada com sucesso!");
      } else {
        toast.error(data.error || "A API Twilio retornou um erro. Verifique as credenciais.");
      }
    } catch {
      toast.error("Falha ao testar conexão");
    } finally {
      setTestingTwilio(false);
    }
  };

  // Setup 2FA
  const handleSetup2FA = async () => {
    setActionLoading(true);
    try {
      const res = await fetch("/api/2fa/setup", {
        method: "POST",
      });
      const data = await res.json();
      if (res.ok) {
        setQrCodeUrl(data.qr_code_base64);
        setSecretKey(data.secret);
        toast.success("Código QR de segurança gerado!");
      } else {
        toast.error(data.error || "Não foi possível iniciar setup de 2FA");
      }
    } catch {
      toast.error("Erro na conexão");
    } finally {
      setActionLoading(false);
    }
  };

  // Verify and enable 2FA
  const handleVerify2FA = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!verificationCode) return;
    setActionLoading(true);
    try {
      const res = await fetch("/api/2fa/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: verificationCode }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setTwoFactorEnabled(true);
        setQrCodeUrl(null);
        setSecretKey(null);
        setVerificationCode("");
        toast.success("Autenticação de Duplo Fator (2FA) ATIVADA com sucesso!");
      } else {
        toast.error(data.error || "Código de verificação incorreto ou expirado.");
      }
    } catch {
      toast.error("Erro na conexão");
    } finally {
      setActionLoading(false);
    }
  };

  // Disable 2FA
  const handleDisable2FA = async () => {
    if (!confirm("Deseja mesmo desativar a verificação de 2FA da sua conta? Isso diminuirá a segurança do acesso.")) return;
    setActionLoading(true);
    try {
      const res = await fetch("/api/2fa/disable", {
        method: "POST",
      });
      const data = await res.json();
      if (res.ok) {
        setTwoFactorEnabled(false);
        toast.success("Segurança de 2FA desativada.");
      } else {
        toast.error(data.error || "Erro ao desativar 2FA");
      }
    } catch {
      toast.error("Erro ao solicitar desativação");
    } finally {
      setActionLoading(false);
    }
  };

  // System maintenance data wipe
  const handleWipeData = async (e: React.FormEvent) => {
    e.preventDefault();
    if (wipeConfirmText !== "EXCLUIR TUDO") {
      toast.error("Escreva EXCLUIR TUDO exatamente como solicitado");
      return;
    }
    setActionLoading(true);
    try {
      const res = await fetch("/api/wipe-data", {
        method: "DELETE",
      });
      if (res.ok) {
        toast.success("Todos os dados operacionais foram limpos!");
        setWipeConfirmText("");
        setWipeOpen(false);
      } else {
        const data = await res.json();
        toast.error(data.error || "Não foi possível concluir a limpeza");
      }
    } catch {
      toast.error("Erro ao conectar ao servidor");
    } finally {
      setActionLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(true);
    toast.success("Chave copiada para a área de transferência!");
    setTimeout(() => setCopiedKey(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-black tracking-tight text-foreground flex items-center gap-2">
          <Settings className="h-8 w-8 text-primary animate-spin-slow" />
          Configurações do VoxFlow
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Gerencie o perfil da sua empresa, credenciais de voz da Twilio, chaves de segurança e manutenção preventiva.
        </p>
      </div>

      {/* Tabs list container */}
      <div className="flex gap-2 border-b border-border/60 pb-px">
        <button
          onClick={() => setActiveTab("company")}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold uppercase tracking-wider border-b-2 transition-all cursor-pointer ${
            activeTab === "company"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Building className="h-4 w-4" />
          Empresa / Conta
        </button>

        <button
          onClick={() => setActiveTab("twilio")}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold uppercase tracking-wider border-b-2 transition-all cursor-pointer ${
            activeTab === "twilio"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Phone className="h-4 w-4" />
          Twilio Voice SDK
        </button>

        <button
          onClick={() => setActiveTab("2fa")}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold uppercase tracking-wider border-b-2 transition-all cursor-pointer ${
            activeTab === "2fa"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Lock className="h-4 w-4" />
          Segurança (2FA)
        </button>

        <button
          onClick={() => setActiveTab("maintenance")}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold uppercase tracking-wider border-b-2 transition-all cursor-pointer ${
            activeTab === "maintenance"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <ShieldAlert className="h-4 w-4" />
          Manutenção
        </button>
      </div>

      {/* Tab Panels */}
      {loading ? (
        <Card className="bg-card border-border/50 shadow-sm">
          <CardHeader className="space-y-2">
            <div className="h-4 bg-muted/40 rounded w-1/4 animate-pulse" />
            <div className="h-3 bg-muted/20 rounded w-2/3 animate-pulse" />
          </CardHeader>
          <CardContent className="space-y-4 py-6">
            {[1, 2].map((i) => (
              <div key={i} className="space-y-1.5">
                <div className="h-3 bg-muted/30 rounded w-1/6 animate-pulse" />
                <div className="h-10 bg-muted/20 rounded w-full animate-pulse" />
              </div>
            ))}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* TAB 1: Company Profile */}
          {activeTab === "company" && company && (
            <Card className="bg-card border-border/50 shadow-sm">
              <CardHeader>
                <CardTitle className="text-lg font-bold tracking-tight text-foreground">
                  Perfil Corporativo
                </CardTitle>
                <CardDescription>
                  Altere a identificação global da sua empresa no VoxFlow.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSaveCompany} className="space-y-6">
                  <div className="space-y-2 max-w-lg">
                    <Label htmlFor="company-name">Nome da Organização</Label>
                    <Input
                      id="company-name"
                      placeholder="Empresa S/A"
                      value={company.name}
                      onChange={(e) => setCompany({ ...company, name: e.target.value })}
                    />
                  </div>

                  <div className="text-xs text-muted-foreground pt-2">
                    Conta criada em: {new Date(company.created_at).toLocaleDateString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                  </div>

                  <Button type="submit" className="font-bold shadow-md shadow-primary/10" loading={actionLoading}>
                    <Save className="h-4 w-4 mr-2" />
                    Salvar Informações
                  </Button>
                </form>
              </CardContent>
            </Card>
          )}

          {/* TAB 2: Twilio Integration */}
          {activeTab === "twilio" && (
            <Card className="bg-card border-border/50 shadow-sm">
              <CardHeader>
                <CardTitle className="text-lg font-bold tracking-tight text-foreground flex items-center justify-between">
                  Chaves de Telefonia Twilio Voice
                  <Badge variant="outline" className="bg-primary/5 text-primary border-primary/20">
                    Active WebRTC
                  </Badge>
                </CardTitle>
                <CardDescription>
                  Insira suas credenciais da API Twilio para habilitar chamadas WebRTC em tempo real direto do navegador.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSaveTwilio} className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Account SID */}
                    <div className="space-y-2">
                      <Label htmlFor="twilio-sid">Account SID *</Label>
                      <Input
                        id="twilio-sid"
                        placeholder="ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
                        value={twilio.account_sid}
                        onChange={(e) => setTwilio({ ...twilio, account_sid: e.target.value })}
                        required
                      />
                    </div>

                    {/* Auth Token */}
                    <div className="space-y-2">
                      <Label htmlFor="twilio-token">Auth Token *</Label>
                      <div className="relative">
                        <Input
                          id="twilio-token"
                          type={showAuthToken ? "text" : "password"}
                          placeholder="Tokens de Segurança Twilio"
                          value={twilio.auth_token}
                          onChange={(e) => setTwilio({ ...twilio, auth_token: e.target.value })}
                          required
                          className="pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => setShowAuthToken(!showAuthToken)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
                        >
                          {showAuthToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>

                    {/* Twiml App SID */}
                    <div className="space-y-2">
                      <Label htmlFor="twilio-twiml">TwiML App SID</Label>
                      <Input
                        id="twilio-twiml"
                        placeholder="APXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
                        value={twilio.twiml_app_sid || ""}
                        onChange={(e) => setTwilio({ ...twilio, twiml_app_sid: e.target.value || null })}
                      />
                      <p className="text-[10px] text-muted-foreground">
                        Utilizado para encaminhar as chamadas efetuadas do Webphone via WebRTC.
                      </p>
                    </div>

                    {/* Caller ID / Phone Number */}
                    <div className="space-y-2">
                      <Label htmlFor="twilio-phone">Número de Telefone Padrão (Caller ID)</Label>
                      <Input
                        id="twilio-phone"
                        placeholder="+5511999999999"
                        value={twilio.phone_number}
                        onChange={(e) => setTwilio({ ...twilio, phone_number: e.target.value })}
                      />
                      <p className="text-[10px] text-muted-foreground">
                        BINA padrão de saída utilizada quando a campanha não possui pool de IDs.
                      </p>
                    </div>

                    {/* Voice Recording settings */}
                    <div className="space-y-2">
                      <Label htmlFor="twilio-recording">Gravação de Chamadas</Label>
                      <select
                        id="twilio-recording"
                        className="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                        value={twilio.voice_recording}
                        onChange={(e) => setTwilio({ ...twilio, voice_recording: e.target.value })}
                      >
                        <option value="none">Não Gravar (Sem custos extras)</option>
                        <option value="local">Gravação de Áudio Local (Navegador)</option>
                        <option value="twilio">Gravar no Servidor Twilio</option>
                      </select>
                    </div>

                    {/* Speech to text */}
                    <div className="flex items-center gap-3 py-4">
                      <input
                        id="twilio-stt"
                        type="checkbox"
                        className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                        checked={twilio.speech_to_text}
                        onChange={(e) => setTwilio({ ...twilio, speech_to_text: e.target.checked })}
                      />
                      <Label htmlFor="twilio-stt" className="cursor-pointer font-semibold">
                        Speech-to-Text de Chamadas (Transcrição Automática AI)
                      </Label>
                    </div>
                  </div>

                  <div className="flex gap-3 pt-4 border-t">
                    <Button type="submit" className="font-bold shadow-md shadow-primary/10" loading={actionLoading}>
                      <Save className="h-4 w-4 mr-2" />
                      Salvar Chaves Twilio
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      className="font-bold"
                      onClick={handleTestTwilio}
                      disabled={testingTwilio}
                    >
                      {testingTwilio ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin text-primary" />
                          Testando Integração...
                        </>
                      ) : (
                        <>
                          <RefreshCw className="h-4 w-4 mr-2" />
                          Testar Conectividade
                        </>
                      )}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}

          {/* TAB 3: Security & 2FA */}
          {activeTab === "2fa" && (
            <Card className="bg-card border-border/50 shadow-sm">
              <CardHeader>
                <CardTitle className="text-lg font-bold tracking-tight text-foreground flex items-center justify-between">
                  Segurança da Conta (2FA)
                  <Badge
                    variant={twoFactorEnabled ? "success" : "outline"}
                    className="font-bold uppercase text-[10px]"
                  >
                    {twoFactorEnabled ? "MFA Ativado" : "Desprotegido"}
                  </Badge>
                </CardTitle>
                <CardDescription>
                  Configure a Autenticação de Dois Fatores (MFA / TOTP) utilizando aplicativos de segurança (Google Authenticator, Microsoft Authenticator ou 1Password).
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {twoFactorEnabled ? (
                  <div className="space-y-4">
                    <div className="flex gap-3 bg-emerald-500/10 border border-emerald-500/30 p-4 rounded-2xl text-emerald-600 dark:text-emerald-400 text-sm">
                      <CheckCircle2 className="h-5 w-5 shrink-0" />
                      <div className="space-y-1">
                        <p className="font-bold leading-none">Seu 2FA está ativo e configurado!</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          A partir de agora, toda autenticação exigirá o seu código de 6 dígitos gerado no celular para manter o acesso protegido.
                        </p>
                      </div>
                    </div>

                    <Button
                      variant="destructive"
                      size="sm"
                      className="font-bold"
                      onClick={handleDisable2FA}
                      loading={actionLoading}
                    >
                      Desativar Autenticação de 2 Fatores (2FA)
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {!qrCodeUrl ? (
                      <div className="space-y-4">
                        <div className="flex gap-3 bg-muted p-4 border rounded-2xl text-sm leading-relaxed max-w-xl">
                          <Lock className="h-5 w-5 shrink-0 text-muted-foreground" />
                          <div>
                            <p className="font-bold text-foreground">Por que usar autenticação 2FA?</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              Mesmo que alguém descubra a sua senha, eles ainda precisarão do seu celular físico com o token dinâmico gerado pelo aplicativo autenticador para conseguir logar no painel do VoxFlow.
                            </p>
                          </div>
                        </div>

                        <Button className="font-bold shadow-md shadow-primary/10" onClick={handleSetup2FA} loading={actionLoading}>
                          <Play className="h-4 w-4 mr-2 fill-white" />
                          Configurar Duplo Fator (2FA)
                        </Button>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 border p-6 rounded-2xl bg-muted/10">
                        {/* Step 1: Scan QR */}
                        <div className="space-y-4 text-center lg:text-left">
                          <h4 className="font-black text-sm uppercase tracking-wider text-muted-foreground">
                            Passo 1: Escaneie o Código QR
                          </h4>
                          <p className="text-xs text-muted-foreground max-w-sm">
                            Abra o aplicativo autenticador em seu celular e aponte a câmera para ler o QR Code abaixo:
                          </p>
                          
                          {/* QR Image */}
                          <div className="bg-white p-4 inline-block rounded-2xl border mx-auto">
                            <img src={qrCodeUrl} alt="2FA QR Code" className="h-48 w-48 block" />
                          </div>

                          {/* Secret Key manual */}
                          {secretKey && (
                            <div className="space-y-1.5 text-left max-w-xs mx-auto lg:mx-0">
                              <span className="text-[10px] text-muted-foreground block font-bold uppercase tracking-wider">
                                Chave de configuração manual:
                              </span>
                              <div className="flex gap-1.5 items-center">
                                <code className="text-xs font-mono bg-muted p-2 rounded-lg break-all flex-1 text-center font-bold">
                                  {secretKey}
                                </code>
                                <Button
                                  variant="outline"
                                  size="icon"
                                  onClick={() => copyToClipboard(secretKey)}
                                  className="h-9 w-9 shrink-0"
                                >
                                  {copiedKey ? <Check className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Step 2: Verification token */}
                        <div className="space-y-4 border-t lg:border-t-0 lg:border-l lg:pl-8 pt-6 lg:pt-0">
                          <h4 className="font-black text-sm uppercase tracking-wider text-muted-foreground">
                            Passo 2: Verifique o Token
                          </h4>
                          <p className="text-xs text-muted-foreground max-w-sm">
                            Insira o token de 6 dígitos gerado pelo seu aplicativo autenticador para confirmar que a sincronização deu certo:
                          </p>

                          <form onSubmit={handleVerify2FA} className="space-y-4 max-w-xs">
                            <div className="space-y-2">
                              <Label htmlFor="verification-code">Código Autenticador (6 dígitos)</Label>
                              <Input
                                id="verification-code"
                                placeholder="000000"
                                maxLength={6}
                                className="font-mono text-center text-lg tracking-widest font-black"
                                value={verificationCode}
                                onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ""))}
                                required
                              />
                            </div>

                            <div className="flex gap-2">
                              <Button type="submit" className="flex-1 font-bold" loading={actionLoading}>
                                Ativar 2FA
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                className="font-bold"
                                onClick={() => {
                                  setQrCodeUrl(null);
                                  setSecretKey(null);
                                  setVerificationCode("");
                                }}
                              >
                                Cancelar
                              </Button>
                            </div>
                          </form>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* TAB 4: Maintenance Operations */}
          {activeTab === "maintenance" && (
            <Card className="bg-card border-destructive/20 shadow-sm border">
              <CardHeader className="border-b bg-destructive/5">
                <CardTitle className="text-lg font-bold tracking-tight text-destructive flex items-center gap-1.5">
                  <AlertTriangle className="h-5 w-5 animate-pulse" />
                  Operações Destrutivas de Manutenção
                </CardTitle>
                <CardDescription className="text-destructive/80">
                  Ações de limpeza profunda e redefinição de ambiente. Prossiga com extrema cautela.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6 pt-6">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 p-5 border rounded-2xl bg-muted/20">
                  <div className="space-y-1 max-w-md">
                    <h4 className="font-bold text-foreground text-sm">Apagar Dados Operacionais (Wipe Base)</h4>
                    <p className="text-xs text-muted-foreground">
                      Remove permanentemente todos os Leads, Campanhas, Contatos, Histórico de Chamadas e Timeline de eventos do banco de dados local. Os dados cadastrais da empresa e usuários não são afetados.
                    </p>
                  </div>
                  <Button
                    variant="destructive"
                    className="font-bold gap-1.5 shrink-0 self-start md:self-center"
                    onClick={() => setWipeOpen(true)}
                  >
                    <Trash2 className="h-4 w-4" />
                    Wipe Base Operacional
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Wipe Data Modal */}
      {wipeOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setWipeOpen(false)} />
          <div className="relative bg-card rounded-2xl shadow-2xl border border-destructive/20 w-full max-w-md mx-4 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="bg-destructive/10 p-6 flex flex-col items-center text-center border-b border-destructive/10 space-y-3">
              <div className="h-12 w-12 rounded-full bg-destructive/10 text-destructive flex items-center justify-center">
                <AlertTriangle className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-lg font-black text-destructive tracking-tight">Confirmar Operação Crítica</h3>
                <p className="text-xs text-muted-foreground">
                  Esta ação é destrutiva e apagará permanentemente todos os leads, campanhas e chamadas gravadas. Esta ação não poderá ser desfeita!
                </p>
              </div>
            </div>

            <form onSubmit={handleWipeData} className="p-6 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="wipe-confirm" className="text-center font-bold text-xs block text-muted-foreground uppercase">
                  Escreva <span className="text-destructive font-black">EXCLUIR TUDO</span> para confirmar:
                </Label>
                <Input
                  id="wipe-confirm"
                  placeholder="EXCLUIR TUDO"
                  className="font-bold text-center border-destructive/30 focus:ring-destructive"
                  value={wipeConfirmText}
                  onChange={(e) => setWipeConfirmText(e.target.value)}
                  required
                />
              </div>

              <div className="flex gap-3 pt-2">
                <Button
                  type="submit"
                  variant="destructive"
                  className="flex-1 font-bold shadow-md shadow-destructive/10"
                  disabled={wipeConfirmText !== "EXCLUIR TUDO" || actionLoading}
                >
                  Confirmar Wiping
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="flex-1 font-bold"
                  onClick={() => {
                    setWipeOpen(false);
                    setWipeConfirmText("");
                  }}
                >
                  Cancelar
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
