'use client'
import { useEffect, useRef, useState, useCallback } from 'react'

export type WSStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export function useWebSocket<T = any>(url: string) {
  const ws = useRef<WebSocket | null>(null)
  const [status, setStatus] = useState<WSStatus>('disconnected')
  const [lastMessage, setLastMessage] = useState<T | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmounted = useRef(false)

  const connect = useCallback(() => {
    if (unmounted.current) return
    try {
      setStatus('connecting')
      ws.current = new WebSocket(url)

      ws.current.onopen = () => {
        if (!unmounted.current) setStatus('connected')
      }

      ws.current.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          if (data.type === 'ping') return
          if (!unmounted.current) setLastMessage(data)
        } catch {}
      }

      ws.current.onclose = () => {
        if (unmounted.current) return
        setStatus('disconnected')
        reconnectTimer.current = setTimeout(connect, 3000)
      }

      ws.current.onerror = () => {
        if (!unmounted.current) setStatus('error')
        ws.current?.close()
      }
    } catch {
      setStatus('error')
      reconnectTimer.current = setTimeout(connect, 5000)
    }
  }, [url])

  useEffect(() => {
    unmounted.current = false
    connect()
    return () => {
      unmounted.current = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [connect])

  return { status, lastMessage }
}
