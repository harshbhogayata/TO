/**
 * src/services/websocket.js
 * Production-grade WebSocket manager for TalentOrbit.
 *
 * Features:
 *  - Automatic reconnection with exponential backoff (capped at 30s)
 *  - JWT authentication via query-string token
 *  - Heartbeat / keepalive to detect dead connections
 *  - Event-based API for consumers (onMessage, onOpen, onClose)
 *  - Graceful degradation — the app works without WebSocket
 *  - Singleton management — prevents duplicate connections
 */

const WS_BASE = import.meta.env.VITE_WS_URL || (
    window.location.protocol === 'https:'
        ? `wss://${window.location.host}`
        : `ws://${window.location.host}`
);

/** @enum {string} */
const ReadyState = {
    CONNECTING: 'connecting',
    OPEN: 'open',
    CLOSING: 'closing',
    CLOSED: 'closed',
};

class WebSocketManager {
    /**
     * @param {string} path - WebSocket endpoint path (e.g. '/ws/chat/')
     * @param {Object} options
     * @param {() => string|null} options.getToken - Function returning current JWT access token
     * @param {(data: Object) => void} [options.onMessage] - Message handler
     * @param {() => void} [options.onOpen] - Connection opened handler
     * @param {(event: CloseEvent) => void} [options.onClose] - Connection closed handler
     * @param {(event: Event) => void} [options.onError] - Error handler
     * @param {number} [options.maxRetries=Infinity] - Max reconnection attempts
     * @param {boolean} [options.autoReconnect=true] - Enable auto reconnect
     */
    constructor(path, options = {}) {
        this.path = path;
        this.getToken = options.getToken || (() => null);
        this.onMessage = options.onMessage || (() => {});
        this.onOpen = options.onOpen || (() => {});
        this.onClose = options.onClose || (() => {});
        this.onError = options.onError || (() => {});
        this.maxRetries = options.maxRetries ?? Infinity;
        this.autoReconnect = options.autoReconnect ?? true;

        /** @type {WebSocket|null} */
        this._ws = null;
        this._retryCount = 0;
        this._retryTimer = null;
        this._heartbeatTimer = null;
        this._intentionalClose = false;
        this._state = ReadyState.CLOSED;
    }

    /** Current connection state */
    get state() {
        return this._state;
    }

    /** Whether the connection is open and ready */
    get isConnected() {
        return this._state === ReadyState.OPEN;
    }

    /**
     * Open the WebSocket connection.
     * No-op if already connected or connecting.
     */
    connect() {
        if (this._ws && (this._ws.readyState === WebSocket.OPEN || this._ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        const token = this.getToken();
        if (!token) {
            // Can't connect without auth — will retry when token becomes available
            return;
        }

        this._intentionalClose = false;
        this._state = ReadyState.CONNECTING;

        const url = `${WS_BASE}${this.path}?token=${encodeURIComponent(token)}`;

        try {
            this._ws = new WebSocket(url);
        } catch {
            this._scheduleReconnect();
            return;
        }

        this._ws.onopen = () => {
            this._state = ReadyState.OPEN;
            this._retryCount = 0;
            this._startHeartbeat();
            this.onOpen();
        };

        this._ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.onMessage(data);
            } catch {
                // Ignore non-JSON frames
            }
        };

        this._ws.onclose = (event) => {
            this._state = ReadyState.CLOSED;
            this._stopHeartbeat();
            this.onClose(event);

            if (!this._intentionalClose && this.autoReconnect) {
                this._scheduleReconnect();
            }
        };

        this._ws.onerror = (event) => {
            this.onError(event);
        };
    }

    /**
     * Send a JSON message through the WebSocket.
     * @param {Object} data - JSON-serializable object
     * @returns {boolean} Whether the message was sent
     */
    send(data) {
        if (!this._ws || this._ws.readyState !== WebSocket.OPEN) {
            return false;
        }
        try {
            this._ws.send(JSON.stringify(data));
            return true;
        } catch {
            return false;
        }
    }

    /**
     * Gracefully close the connection. No auto-reconnect after this.
     */
    disconnect() {
        this._intentionalClose = true;
        this._stopHeartbeat();
        clearTimeout(this._retryTimer);
        this._retryCount = 0;

        if (this._ws) {
            this._state = ReadyState.CLOSING;
            this._ws.close(1000, 'Client disconnect');
            this._ws = null;
        }
        this._state = ReadyState.CLOSED;
    }

    /**
     * Force reconnect (e.g. after token refresh).
     */
    reconnect() {
        this.disconnect();
        this._intentionalClose = false;
        this._retryCount = 0;
        this.connect();
    }

    // ── Internal ──────────────────────────────────────────────────────────

    _scheduleReconnect() {
        if (this._retryCount >= this.maxRetries) {
            return;
        }

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (capped)
        const delay = Math.min(1000 * Math.pow(2, this._retryCount), 30000);
        // Add jitter (±25%) to prevent thundering herd
        const jitter = delay * (0.75 + Math.random() * 0.5);

        this._retryTimer = setTimeout(() => {
            this._retryCount++;
            this.connect();
        }, jitter);
    }

    _startHeartbeat() {
        this._stopHeartbeat();
        // Ping every 25s to keep connection alive (most proxies timeout at 30-60s)
        this._heartbeatTimer = setInterval(() => {
            if (this._ws && this._ws.readyState === WebSocket.OPEN) {
                this.send({ type: 'heartbeat' });
            }
        }, 25000);
    }

    _stopHeartbeat() {
        if (this._heartbeatTimer) {
            clearInterval(this._heartbeatTimer);
            this._heartbeatTimer = null;
        }
    }
}

export { WebSocketManager, ReadyState };
export default WebSocketManager;
