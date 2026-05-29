"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Eye, EyeOff, Mail, Lock, ShieldAlert } from "lucide-react";

const loginSchema = z.object({
  email: z.string().email("Email inválido"),
  password: z.string().min(1, "Senha obrigatória"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  // 2FA state
  const [requires2fa, setRequires2fa] = useState(false);
  const [challengeToken, setChallengeToken] = useState("");
  const [totpCode, setTotpCode] = useState("");

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormValues) => {
    setLoading(true);
    try {
      const res = await fetch("/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: data.email.toLowerCase(),
          password: data.password,
        }),
      });

      const result = await res.json();

      if (!res.ok) {
        toast.error(result.error || "Email ou senha incorretos");
        return;
      }

      if (result.requires_2fa) {
        setRequires2fa(true);
        setChallengeToken(result.challenge_token);
        toast.info("Código de autenticação 2FA necessário");
        return;
      }

      toast.success("Login realizado com sucesso!");
      router.push("/dashboard");
    } catch {
      toast.error("Erro ao fazer login. Tente novamente.");
    } finally {
      setLoading(false);
    }
  };

  const handle2faSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (totpCode.length !== 6 || isNaN(Number(totpCode))) {
      toast.error("Código inválido — deve ter 6 dígitos");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/auth/login/2fa", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          challenge_token: challengeToken,
          code: totpCode,
        }),
      });

      const result = await res.json();

      if (!res.ok) {
        toast.error(result.error || "Código 2FA incorreto ou expirado");
        return;
      }

      toast.success("Verificado! Bem-vindo.");
      router.push("/dashboard");
    } catch {
      toast.error("Erro ao verificar código. Tente novamente.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-background">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-primary via-indigo-600 to-indigo-800 p-12 flex-col justify-between relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.08),transparent)] pointer-events-none" />
        <div className="flex items-center gap-3 relative z-10">
          <div className="h-10 w-10 rounded-xl bg-white/20 flex items-center justify-center font-bold text-white text-xl">
            V
          </div>
          <span className="text-white font-bold text-xl tracking-tight">VoxFlow</span>
        </div>

        <div className="space-y-6 relative z-10">
          <blockquote className="space-y-2">
            <p className="text-2xl text-white/90 font-medium leading-relaxed">
              "A rearquitetura enterprise do VoxFlow otimizou nosso atendimento por voz.
              Gerenciamento de leads automatizado com alto rendimento Twilio AMD."
            </p>
            <footer className="text-white/70 text-sm font-medium">
              Portal do Operador & Supervisor
            </footer>
          </blockquote>
        </div>

        <div className="grid grid-cols-3 gap-6 relative z-10 border-t border-white/10 pt-8">
          {[
            { label: "Ligações/dia", value: "85.000+" },
            { label: "Leads Gerenciados", value: "5M+" },
            { label: "Recuperação AMD", value: "98.4%" },
          ].map((stat) => (
            <div key={stat.label}>
              <div className="text-xl font-bold text-white">{stat.value}</div>
              <div className="text-xs text-white/70 mt-1">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md space-y-8">
          <div className="text-center">
            <div className="lg:hidden flex items-center justify-center gap-3 mb-8">
              <div className="h-10 w-10 rounded-xl bg-primary flex items-center justify-center text-primary-foreground font-bold text-xl">
                V
              </div>
              <span className="font-bold text-xl">VoxFlow</span>
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight">
              {requires2fa ? "Segurança Adicional" : "Acesse sua conta"}
            </h1>
            <p className="mt-2 text-muted-foreground text-sm">
              {requires2fa
                ? "Insira o código gerado pelo seu aplicativo autenticador"
                : "Entre com suas credenciais corporativas"}
            </p>
          </div>

          {!requires2fa ? (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="nome@empresa.com"
                    className="pl-9"
                    {...register("email")}
                  />
                </div>
                {errors.email && (
                  <p className="text-xs text-destructive mt-1">{errors.email.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Senha</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    className="pl-9 pr-10"
                    {...register("password")}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password && (
                  <p className="text-xs text-destructive mt-1">{errors.password.message}</p>
                )}
              </div>

              <Button type="submit" className="w-full font-semibold" loading={loading}>
                Entrar
              </Button>
            </form>
          ) : (
            <form onSubmit={handle2faSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="2fa-code">Código de Autenticação (TOTP)</Label>
                <div className="relative">
                  <ShieldAlert className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="2fa-code"
                    type="text"
                    maxLength={6}
                    placeholder="123456"
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))}
                    className="pl-9 text-center font-mono tracking-widest text-lg"
                  />
                </div>
              </div>

              <Button type="submit" className="w-full font-semibold" loading={loading}>
                Verificar Código
              </Button>

              <button
                type="button"
                onClick={() => setRequires2fa(false)}
                className="w-full text-center text-xs text-muted-foreground hover:text-foreground hover:underline mt-2 cursor-pointer"
              >
                Voltar para login com senha
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
