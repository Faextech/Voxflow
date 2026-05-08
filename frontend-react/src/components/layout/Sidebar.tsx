import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Users, PhoneCall, BarChart2, Upload,
  Settings, Headphones, UserCog, CreditCard, ListX,
  GitBranch, PhoneIncoming, Repeat, Monitor
} from 'lucide-react'
import { useAuthStore } from '@/store/auth'

const links = [
  { to: '/app/dashboard',  icon: LayoutDashboard, label: 'Dashboard'    },
  { to: '/app/campaigns',  icon: GitBranch,       label: 'Campanhas'    },
  { to: '/app/leads',      icon: Users,           label: 'Leads'        },
  { to: '/app/calls',      icon: PhoneCall,       label: 'Chamadas'     },
  { to: '/app/operation',  icon: Headphones,      label: 'Call Hub'     },
  { to: '/app/callbacks',  icon: PhoneIncoming,   label: 'Retornos'     },
  { to: '/app/followup',   icon: Repeat,          label: 'Follow-up'    },
  { to: '/app/dnc',        icon: ListX,           label: 'Lista DNC'    },
  { to: '/app/reports',    icon: BarChart2,       label: 'Relatórios'   },
  { to: '/app/analytics',  icon: BarChart2,       label: 'Analytics'    },
  { to: '/app/import',     icon: Upload,          label: 'Importar'     },
]

const adminLinks = [
  { to: '/app/supervisor', icon: Monitor,    label: 'Supervisor'     },
  { to: '/app/users',      icon: UserCog,    label: 'Usuários'       },
  { to: '/app/settings',   icon: Settings,   label: 'Configurações'  },
  { to: '/app/credito',    icon: CreditCard, label: 'Crédito'        },
]

export function Sidebar() {
  const role    = useAuthStore(s => s.user?.role)
  const isAdmin = role === 'admin' || role === 'superadmin' || role === 'supervisor'

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1>Vox<span>Flow</span></h1>
      </div>

      <div style={{ padding: '12px 0', flex: 1 }}>
        <div className="menu-title">Operação</div>
        <nav className="menu">
          {links.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `menu-link${isActive ? ' active' : ''}`}
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {isAdmin && (
          <>
            <div className="menu-title" style={{ marginTop: '12px' }}>Admin</div>
            <nav className="menu">
              {adminLinks.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) => `menu-link${isActive ? ' active' : ''}`}
                >
                  <Icon size={16} />
                  {label}
                </NavLink>
              ))}
            </nav>
          </>
        )}
      </div>
    </aside>
  )
}
