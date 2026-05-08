import { create } from 'zustand'

export type DialerStatus = 'idle' | 'running' | 'paused' | 'stopped'

interface DialerSession {
  session_id:    string
  campaign_id:   number
  campaign_name: string
  status:        DialerStatus
  leads_total:   number
  leads_called:  number
  pause_reason?: string
}

interface DialerState {
  session:    DialerSession | null
  activeLead: { name: string; phone: string } | null
  callStatus: 'idle' | 'ringing' | 'answered' | 'ended'
  setSession:    (s: DialerSession | null) => void
  setActiveLead: (l: DialerState['activeLead']) => void
  setCallStatus: (s: DialerState['callStatus']) => void
}

export const useDialerStore = create<DialerState>()(set => ({
  session:       null,
  activeLead:    null,
  callStatus:    'idle',
  setSession:    session    => set({ session }),
  setActiveLead: activeLead => set({ activeLead }),
  setCallStatus: callStatus => set({ callStatus }),
}))
