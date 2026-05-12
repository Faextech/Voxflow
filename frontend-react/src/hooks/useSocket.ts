import { useEffect, useRef } from 'react'
import { io, Socket } from 'socket.io-client'
import { useAuthStore } from '@/store/auth'
import { useDialerStore } from '@/store/dialer'

let _socket: Socket | null = null

export function useSocket() {
  const token   = useAuthStore(s => s.token)
  const setSession    = useDialerStore(s => s.setSession)
  const setActiveLead = useDialerStore(s => s.setActiveLead)
  const setCallStatus = useDialerStore(s => s.setCallStatus)
  const ready = useRef(false)

  useEffect(() => {
    if (!token || ready.current) return
    ready.current = true

    _socket = io('/', {
      auth:        { token },
      transports:  ['websocket', 'polling'],
      reconnection: true,
    })

    _socket.on('dialer_status', (data: { session?: string, active_lead?: Record<string, unknown>, call_status?: string }) => {
      setSession(data?.session ?? null)
      if (data?.active_lead) setActiveLead(data.active_lead)
      if (data?.call_status) setCallStatus(data.call_status)
    })

    _socket.on('call_update', (data: { status?: string, lead?: Record<string, unknown> }) => {
      setCallStatus(data?.status ?? 'idle')
      if (data?.lead) setActiveLead(data.lead)
    })

    return () => {
      _socket?.disconnect()
      _socket = null
      ready.current = false
    }
  }, [token, setSession, setActiveLead, setCallStatus])

  return _socket
}

export function getSocket() { return _socket }
