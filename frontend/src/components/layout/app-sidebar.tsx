"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Kanban,
  Megaphone,
  Zap,
  BarChart3,
  Settings,
  ChevronLeft,
  ChevronRight,
  UserCog,
  TrendingUp,
  Phone,
  PhoneCall,
  PhoneForwarded,
  Upload,
  Ban,
  Repeat,
  LineChart,
  Eye,
  MessageSquare,
  Plug,
  Mail,
  LifeBuoy,
  CreditCard,
  Shield,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";
import { useAuth } from "@/providers/auth-provider";

const navSections = [
  {
    section: "Principal",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/analytics", label: "Analytics", icon: LineChart },
      { href: "/supervisor", label: "Supervisor", icon: Eye, roles: ["admin", "supervisor"] },
      { href: "/leads", label: "Leads", icon: TrendingUp },
      { href: "/calls", label: "Chamadas", icon: PhoneCall },
      { href: "/callbacks", label: "Retornos", icon: PhoneForwarded },
    ],
  },
  {
    section: "Operação",
    items: [
      { href: "/operation", label: "Discador / Webphone", icon: Phone },
      { href: "/campaigns", label: "Campanhas", icon: Megaphone },
      { href: "/import", label: "Importar Leads", icon: Upload },
      { href: "/dnc", label: "DNC / Blacklist", icon: Ban, roles: ["admin"] },
      { href: "/followup", label: "Follow-up", icon: Repeat },
    ],
  },
  {
    section: "CRM & Comunicação",
    items: [
      { href: "/pipeline", label: "Pipeline CRM", icon: Kanban },
      { href: "/automation", label: "Automações", icon: Zap },
      { href: "/inbox", label: "WhatsApp Inbox", icon: MessageSquare },
      { href: "/integrations", label: "Integrações", icon: Plug },
      { href: "/email", label: "Email Marketing", icon: Mail },
      { href: "/support", label: "Suporte", icon: LifeBuoy },
    ],
  },
  {
    section: "Financeiro & Gestão",
    items: [
      { href: "/billing", label: "Crédito / PIX", icon: CreditCard },
      { href: "/reports", label: "Relatórios", icon: BarChart3 },
      { href: "/team", label: "Time", icon: UserCog, roles: ["admin"] },
      { href: "/settings", label: "Configurações", icon: Settings },
      { href: "/admin", label: "Admin Plataforma", icon: Shield, roles: ["superadmin"] },
    ],
  },
];

export function AppSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const { user } = useAuth();

  return (
    <aside
      className={cn(
        "relative flex flex-col h-full bg-sidebar border-r border-sidebar-border transition-all duration-300",
        collapsed ? "w-16" : "w-64"
      )}
    >
      <div className="flex items-center gap-3 p-4 border-b border-sidebar-border h-16">
        <div className="h-8 w-8 rounded-lg flex-shrink-0 flex items-center justify-center bg-primary text-primary-foreground font-bold text-lg shadow-md shadow-primary/20">
          V
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <p className="font-bold text-sidebar-foreground text-base tracking-tight leading-none">
              VoxFlow
            </p>
            <p className="text-[10px] font-medium text-primary mt-1 uppercase tracking-wider">
              Enterprise Portal
            </p>
          </div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto py-4 space-y-6 px-2">
        {navSections.map((section) => {
          const visibleItems = section.items.filter((item) => {
            if (!item.roles) return true;
            return user && item.roles.includes(user.role);
          });
          if (visibleItems.length === 0) return null;

          return (
            <div key={section.section}>
              {!collapsed && (
                <p className="px-2 mb-1 text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                  {section.section}
                </p>
              )}
              <ul className="space-y-0.5">
                {visibleItems.map((item) => {
                  const isActive =
                    pathname === item.href ||
                    (item.href !== "/dashboard" && pathname.startsWith(item.href));
                  const Icon = item.icon;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        className={cn(
                          "flex items-center gap-3 rounded-lg px-2 py-2 text-sm font-medium transition-colors",
                          isActive
                            ? "bg-primary text-white"
                            : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                        )}
                        title={collapsed ? item.label : undefined}
                      >
                        <Icon className="h-4 w-4 flex-shrink-0" />
                        {!collapsed && <span className="truncate">{item.label}</span>}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      <div className="border-t border-sidebar-border p-2">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center p-2 rounded-lg text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>
    </aside>
  );
}
