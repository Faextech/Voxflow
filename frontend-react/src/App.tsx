import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppLayout } from '@/components/layout/AppLayout'
import Login      from '@/pages/Login'
import Landing    from '@/pages/Landing'
import Dashboard  from '@/pages/Dashboard'
import Campaigns  from '@/pages/Campaigns'
import Leads      from '@/pages/Leads'
import Calls      from '@/pages/Calls'
import Operation  from '@/pages/Operation'
import Callbacks  from '@/pages/Callbacks'
import FollowUp   from '@/pages/FollowUp'
import DNC        from '@/pages/DNC'
import Reports    from '@/pages/Reports'
import Analytics  from '@/pages/Analytics'
import Import     from '@/pages/Import'
import Supervisor from '@/pages/Supervisor'
import Users      from '@/pages/Users'
import Settings   from '@/pages/Settings'
import Credito    from '@/pages/Credito'

const qc = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter basename="/">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/app" element={<AppLayout />}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard"  element={<Dashboard  />} />
            <Route path="campaigns"  element={<Campaigns  />} />
            <Route path="leads"      element={<Leads      />} />
            <Route path="calls"      element={<Calls      />} />
            <Route path="operation"  element={<Operation  />} />
            <Route path="callbacks"  element={<Callbacks  />} />
            <Route path="followup"   element={<FollowUp   />} />
            <Route path="dnc"        element={<DNC        />} />
            <Route path="reports"    element={<Reports    />} />
            <Route path="analytics"  element={<Analytics  />} />
            <Route path="import"     element={<Import     />} />
            <Route path="supervisor" element={<Supervisor />} />
            <Route path="users"      element={<Users      />} />
            <Route path="settings"   element={<Settings   />} />
            <Route path="credito"    element={<Credito    />} />
          </Route>
          <Route path="*" element={<Navigate to="/app/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
