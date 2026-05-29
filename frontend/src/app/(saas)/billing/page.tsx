"use client";

import { useEffect, useState, useCallback } from "react";
import { CreditCard, Wallet, ArrowUpRight, Loader2, Copy, CheckCircle2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatCurrency, formatDate } from "@/lib/utils";
import { toast } from "sonner";

type Balance = { balance: number; cost_per_minute: number; has_credit: boolean; currency: string };
type Transaction = { id: number; type: string; amount: number; description: string; created_at: string };
type Payment = { payment_id: string; pix_qr_code?: string; pix_copy_paste?: string; status: string };

export default function BillingPage() {
  const [balance, setBalance] = useState<Balance | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [amount, setAmount] = useState("50");
  const [payment, setPayment] = useState<Payment | null>(null);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);

  const load = useCallback(async () => {
    try {
      const [bal, tx] = await Promise.all([
        apiFetch<Balance>("/api/billing/balance"),
        apiFetch<{ transactions: Transaction[] }>("/api/billing/transactions?per_page=20"),
      ]);
      setBalance(bal);
      setTransactions(tx.transactions || []);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const initiatePix = async () => {
    try {
      const data = await apiFetch<Payment>("/api/billing/payment/initiate", {
        method: "POST",
        body: JSON.stringify({ amount: parseFloat(amount), method: "pix" }),
      });
      setPayment(data);
      setPolling(true);
      toast.success("PIX gerado! Aguardando pagamento...");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao gerar PIX");
    }
  };

  useEffect(() => {
    if (!polling || !payment?.payment_id) return;
    const iv = setInterval(async () => {
      try {
        const status = await apiFetch<{ status: string }>(`/api/billing/payment/${payment.payment_id}/status`);
        if (status.status === "approved") {
          setPolling(false);
          setPayment(null);
          toast.success("Pagamento confirmado!");
          load();
        }
      } catch { /* ignore */ }
    }, 3000);
    return () => clearInterval(iv);
  }, [polling, payment, load]);

  const copyPix = () => {
    if (payment?.pix_copy_paste) {
      navigator.clipboard.writeText(payment.pix_copy_paste);
      toast.success("Código PIX copiado");
    }
  };

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" /></div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Crédito & Billing</h1>
        <p className="text-muted-foreground text-sm mt-1">Saldo, recarga PIX e histórico de transações</p>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="rounded-xl border bg-card p-6 md:col-span-1">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <Wallet className="h-4 w-4" />Saldo atual
          </div>
          <p className="text-3xl font-bold">{formatCurrency(balance?.balance ?? 0)}</p>
          <p className="text-sm text-muted-foreground mt-1">
            {formatCurrency(balance?.cost_per_minute ?? 0)}/min · {balance?.has_credit ? "Crédito OK" : "Saldo baixo"}
          </p>
        </div>

        <div className="rounded-xl border bg-card p-6 md:col-span-2 space-y-4">
          <h3 className="font-semibold flex items-center gap-2"><CreditCard className="h-4 w-4" />Recarga via PIX</h3>
          {!payment ? (
            <div className="flex gap-3 items-end">
              <div className="flex-1">
                <Label>Valor (mín. R$ 10)</Label>
                <Input type="number" min="10" value={amount} onChange={(e) => setAmount(e.target.value)} />
              </div>
              <Button onClick={initiatePix}>Gerar PIX</Button>
            </div>
          ) : (
            <div className="space-y-3">
              {payment.pix_qr_code && (
                <img src={`data:image/png;base64,${payment.pix_qr_code}`} alt="QR PIX" className="w-48 h-48 mx-auto rounded-lg border" />
              )}
              <Button variant="outline" className="w-full" onClick={copyPix}>
                <Copy className="h-4 w-4 mr-2" />Copiar código PIX
              </Button>
              {polling && <p className="text-sm text-center text-muted-foreground animate-pulse">Aguardando confirmação...</p>}
            </div>
          )}
        </div>
      </div>

      <div className="rounded-xl border">
        <div className="p-4 border-b font-semibold">Histórico de transações</div>
        <div className="divide-y">
          {transactions.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">Nenhuma transação</div>
          ) : transactions.map((tx) => (
            <div key={tx.id} className="flex items-center justify-between p-4">
              <div>
                <p className="font-medium text-sm">{tx.description}</p>
                <p className="text-xs text-muted-foreground">{formatDate(tx.created_at)} · {tx.type}</p>
              </div>
              <span className={`font-semibold flex items-center gap-1 ${tx.amount > 0 ? "text-green-600" : "text-red-600"}`}>
                {tx.amount > 0 && <ArrowUpRight className="h-4 w-4" />}
                {formatCurrency(Math.abs(tx.amount))}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
