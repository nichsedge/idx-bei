import { StreamEvent } from '../types';

type MessageHandler = (event: StreamEvent) => void;
type StatusHandler = (connected: boolean) => void;

export class LiveStreamClient {
  private socket: WebSocket | null = null;
  private messageListeners: Set<MessageHandler> = new Set();
  private statusListeners: Set<StatusHandler> = new Set();
  private reconnectTimer: any = null;
  private reconnectAttempts = 0;
  private isConnected = false;

  constructor() {
    this.connect();
  }

  private connect() {
    if (typeof window === 'undefined') return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    let wsHost = window.location.host || 'localhost:8000';
    if (window.location.port !== '8000') {
      wsHost = `${window.location.hostname || 'localhost'}:8000`;
    }
    const wsUrl = `${protocol}//${wsHost}/ws/stream`;

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.notifyStatus(true);
      };

      this.socket.onmessage = (event) => {
        try {
          const data: StreamEvent = JSON.parse(event.data);
          this.notifyMessage(data);
        } catch (e) {
          console.debug('[WS] Parse error:', e);
        }
      };

      this.socket.onclose = () => {
        this.isConnected = false;
        this.notifyStatus(false);
        this.scheduleReconnect();
      };

      this.socket.onerror = () => {
        if (this.socket) {
          this.socket.close();
        }
      };
    } catch {
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (!this.reconnectTimer) {
      const baseDelay = 1000;
      const maxDelay = 30000;
      const delay = Math.min(
        maxDelay,
        baseDelay * Math.pow(1.5, this.reconnectAttempts) + Math.random() * 1000
      );
      this.reconnectAttempts++;
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, delay);
    }
  }

  public onMessage(handler: MessageHandler): () => void {
    this.messageListeners.add(handler);
    return () => this.messageListeners.delete(handler);
  }

  public onStatusChange(handler: StatusHandler): () => void {
    this.statusListeners.add(handler);
    handler(this.isConnected);
    return () => this.statusListeners.delete(handler);
  }

  private notifyMessage(event: StreamEvent) {
    this.messageListeners.forEach((fn) => fn(event));
  }

  private notifyStatus(connected: boolean) {
    this.statusListeners.forEach((fn) => fn(connected));
  }
}

export const liveStream = new LiveStreamClient();
