"use client";

import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppHeader } from "@/components/layout/app-header";
import { SocketProvider } from "@/providers/socket-provider";
import { AuthProvider } from "@/providers/auth-provider";
import { useAuth } from "@/providers/auth-provider";
import { AutoDialerBar } from "@/components/operation/auto-dialer-bar";

function SaasShell({ children }: { children: React.ReactNode }) {
  const { loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-primary animate-pulse" />
          <p className="text-sm text-muted-foreground">Carregando...</p>
        </div>
      </div>
    );
  }

  return (
    <SocketProvider>
      <div className="flex h-screen overflow-hidden bg-background">
        <AppSidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <AppHeader />
          <main className="flex-1 overflow-auto p-6">{children}</main>
          <AutoDialerBar />
        </div>
      </div>
    </SocketProvider>
  );
}

export default function SaasLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <SaasShell>{children}</SaasShell>
    </AuthProvider>
  );
}
