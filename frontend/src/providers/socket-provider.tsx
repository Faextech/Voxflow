"use client";

import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode } from "react";
import { io, type Socket } from "socket.io-client";
import { toast } from "sonner";

// ─── Types ───────────────────────────────────────────────────────────────────

type SocketStatus = "disconnected" | "connecting" | "connected" | "error";

type SocketContextType = {
  socket: Socket | null;
  status: SocketStatus;
  isConnected: boolean;
  connect: () => void;
  disconnect: () => void;
  emit: (event: string, data?: unknown) => void;
  on: (event: string, handler: (...args: any[]) => void) => void;
  off: (event: string, handler?: (...args: any[]) => void) => void;
};

const SocketContext = createContext<SocketContextType>({
  socket: null,
  status: "disconnected",
  isConnected: false,
  connect: () => {},
  disconnect: () => {},
  emit: () => {},
  on: () => {},
  off: () => {},
});

export const useSocket = () => useContext(SocketContext);

// ─── Provider ────────────────────────────────────────────────────────────────

export function SocketProvider({ children }: { children: ReactNode }) {
  const socketRef = useRef<Socket | null>(null);
  const [status, setStatus] = useState<SocketStatus>("disconnected");

  const connect = useCallback(() => {
    if (socketRef.current?.connected) return;

    setStatus("connecting");

    const socket = io({
      path: "/socket.io/",
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionDelay: 2000,
      reconnectionDelayMax: 10000,
      reconnectionAttempts: 10,
      withCredentials: true,
    });

    socket.on("connect", () => {
      setStatus("connected");
      console.log("[Socket.io] Connected:", socket.id);
    });

    socket.on("disconnect", (reason) => {
      setStatus("disconnected");
      console.log("[Socket.io] Disconnected:", reason);
    });

    socket.on("connect_error", (err) => {
      setStatus("error");
      console.error("[Socket.io] Connection error:", err.message);
    });

    // Global notification events from backend
    socket.on("notification", (data: { title: string; message: string; type?: string }) => {
      if (data.type === "error") {
        toast.error(data.message, { description: data.title });
      } else if (data.type === "warning") {
        toast.warning(data.message, { description: data.title });
      } else {
        toast.info(data.message, { description: data.title });
      }
    });

    socketRef.current = socket;
  }, []);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
      setStatus("disconnected");
    }
  }, []);

  const emit = useCallback((event: string, data?: unknown) => {
    socketRef.current?.emit(event, data);
  }, []);

  const on = useCallback((event: string, handler: (...args: any[]) => void) => {
    socketRef.current?.on(event, handler);
  }, []);

  const off = useCallback((event: string, handler?: (...args: any[]) => void) => {
    if (handler) {
      socketRef.current?.off(event, handler);
    } else {
      socketRef.current?.off(event);
    }
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return (
    <SocketContext.Provider
      value={{
        socket: socketRef.current,
        status,
        isConnected: status === "connected",
        connect,
        disconnect,
        emit,
        on,
        off,
      }}
    >
      {children}
    </SocketContext.Provider>
  );
}
