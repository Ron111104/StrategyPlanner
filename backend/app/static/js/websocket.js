/* ============================================================
   CME Fed Funds Futures (ZQ) Strategy Planning Platform
   WebSocket Client Module
   ============================================================ */

/**
 * WebSocket client with automatic reconnection, channel-based
 * publish/subscribe, and heartbeat support.
 *
 * Usage:
 *   const ws = new WSClient('ws://localhost:8000/ws');
 *   ws.connect();
 *   ws.subscribe('market:ZQM2025', (data) => { ... });
 *   ws.subscribe('signals', (data) => { ... });
 */
class WSClient {
  /**
   * @param {string} url - WebSocket server URL
   * @param {Object} [options]
   * @param {boolean} [options.autoReconnect=true] - Enable automatic reconnection
   * @param {number} [options.reconnectBaseMs=1000] - Base reconnect delay
   * @param {number} [options.reconnectMaxMs=30000] - Max reconnect delay
   * @param {number} [options.heartbeatIntervalMs=30000] - Heartbeat ping interval
   * @param {number} [options.heartbeatTimeoutMs=10000] - Heartbeat pong timeout
   * @param {number} [options.maxReconnectAttempts=Infinity] - Max reconnection attempts
   */
  constructor(url, options = {}) {
    this.url = url;
    this.autoReconnect = options.autoReconnect !== false;
    this.reconnectBaseMs = options.reconnectBaseMs || 1000;
    this.reconnectMaxMs = options.reconnectMaxMs || 30000;
    this.heartbeatIntervalMs = options.heartbeatIntervalMs || 30000;
    this.heartbeatTimeoutMs = options.heartbeatTimeoutMs || 10000;
    this.maxReconnectAttempts = options.maxReconnectAttempts || Infinity;

    /** @type {WebSocket|null} */
    this._ws = null;

    /** @type {Map<string, Set<Function>>} Channel subscriptions */
    this._channels = new Map();

    /** @type {Set<Function>} Global message handlers */
    this._messageHandlers = new Set();

    /** @type {Set<Function>} Error handlers */
    this._errorHandlers = new Set();

    /** @type {Set<Function>} Close handlers */
    this._closeHandlers = new Set();

    /** @type {Set<Function>} Open handlers */
    this._openHandlers = new Set();

    // Reconnection state
    this._reconnectAttempt = 0;
    this._reconnectTimer = null;
    this._intentionalClose = false;

    // Heartbeat state
    this._heartbeatInterval = null;
    this._heartbeatTimeout = null;
    this._lastPong = 0;

    // Connection state
    this._isConnected = false;
    this._connectionPromise = null;
  }

  /* ── Connection Lifecycle ─────────────────────────────── */

  /**
   * Open the WebSocket connection.
   * Returns a promise that resolves when the connection is established.
   * @returns {Promise<void>}
   */
  connect() {
    if (this._ws && (this._ws.readyState === WebSocket.OPEN || this._ws.readyState === WebSocket.CONNECTING)) {
      return this._connectionPromise || Promise.resolve();
    }

    this._intentionalClose = false;
    this._connectionPromise = new Promise((resolve, reject) => {
      try {
        this._ws = new WebSocket(this.url);
      } catch (err) {
        reject(err);
        return;
      }

      this._ws.onopen = () => {
        this._isConnected = true;
        this._reconnectAttempt = 0;
        this._startHeartbeat();

        // Re-subscribe to all channels on reconnect
        for (const channel of this._channels.keys()) {
          this._sendSubscribe(channel);
        }

        this._openHandlers.forEach((handler) => {
          try { handler(); } catch (e) { console.error('[WSClient] open handler error:', e); }
        });

        console.log(`%c[WSClient] Connected to ${this.url}`, 'color:#34d399');
        resolve();
      };

      this._ws.onmessage = (event) => {
        this._handleMessage(event);
      };

      this._ws.onerror = (event) => {
        this._errorHandlers.forEach((handler) => {
          try { handler(event); } catch (e) { console.error('[WSClient] error handler error:', e); }
        });
        console.error('[WSClient] Error:', event);
      };

      this._ws.onclose = (event) => {
        this._isConnected = false;
        this._stopHeartbeat();

        this._closeHandlers.forEach((handler) => {
          try { handler(event); } catch (e) { console.error('[WSClient] close handler error:', e); }
        });

        console.log(`%c[WSClient] Disconnected (code=${event.code}, reason=${event.reason || 'none'})`, 'color:#fb7185');

        if (!this._intentionalClose && this.autoReconnect) {
          this._scheduleReconnect();
        }
      };
    });

    return this._connectionPromise;
  }

  /**
   * Intentionally close the connection.
   * @param {number} [code=1000] - Close code
   * @param {string} [reason='Client disconnect'] - Close reason
   */
  disconnect(code = 1000, reason = 'Client disconnect') {
    this._intentionalClose = true;
    this._clearReconnectTimer();
    this._stopHeartbeat();

    if (this._ws) {
      if (this._ws.readyState === WebSocket.OPEN || this._ws.readyState === WebSocket.CONNECTING) {
        this._ws.close(code, reason);
      }
      this._ws = null;
    }
    this._isConnected = false;
    this._connectionPromise = null;
  }

  /**
   * Check if currently connected.
   * @returns {boolean}
   */
  get connected() {
    return this._isConnected && this._ws !== null && this._ws.readyState === WebSocket.OPEN;
  }

  /* ── Channel Pub/Sub ──────────────────────────────────── */

  /**
   * Subscribe to a named channel.
   * @param {string} channel - Channel name (e.g. 'market:ZQM2025', 'signals')
   * @param {Function} callback - Handler receiving the message data
   * @returns {Function} Unsubscribe function
   */
  subscribe(channel, callback) {
    if (!this._channels.has(channel)) {
      this._channels.set(channel, new Set());
    }
    this._channels.get(channel).add(callback);

    // If already connected, send subscription message to server
    if (this.connected) {
      this._sendSubscribe(channel);
    }

    // Return unsubscribe function
    return () => this.unsubscribe(channel, callback);
  }

  /**
   * Unsubscribe a callback from a channel.
   * If no callback is provided, remove all callbacks for the channel.
   * @param {string} channel - Channel name
   * @param {Function} [callback] - Specific callback to remove
   */
  unsubscribe(channel, callback) {
    if (!this._channels.has(channel)) return;

    if (callback) {
      this._channels.get(channel).delete(callback);
      // Clean up empty channel sets
      if (this._channels.get(channel).size === 0) {
        this._channels.delete(channel);
        if (this.connected) {
          this._sendUnsubscribe(channel);
        }
      }
    } else {
      this._channels.delete(channel);
      if (this.connected) {
        this._sendUnsubscribe(channel);
      }
    }
  }

  /**
   * Register a global message handler (receives all messages).
   * @param {Function} handler - Callback receiving parsed message data
   * @returns {Function} Unregister function
   */
  onMessage(handler) {
    this._messageHandlers.add(handler);
    return () => this._messageHandlers.delete(handler);
  }

  /**
   * Register an error handler.
   * @param {Function} handler - Callback receiving error event
   * @returns {Function} Unregister function
   */
  onError(handler) {
    this._errorHandlers.add(handler);
    return () => this._errorHandlers.delete(handler);
  }

  /**
   * Register a close handler.
   * @param {Function} handler - Callback receiving close event
   * @returns {Function} Unregister function
   */
  onClose(handler) {
    this._closeHandlers.add(handler);
    return () => this._closeHandlers.delete(handler);
  }

  /**
   * Register an open handler.
   * @param {Function} handler - Callback receiving open event
   * @returns {Function} Unregister function
   */
  onOpen(handler) {
    this._openHandlers.add(handler);
    return () => this._openHandlers.delete(handler);
  }

  /**
   * Send a raw message to the server.
   * @param {Object} data - Data to send (will be JSON-stringified)
   */
  send(data) {
    if (!this.connected) {
      console.warn('[WSClient] Cannot send — not connected');
      return;
    }
    this._ws.send(JSON.stringify(data));
  }

  /* ── Internal: Message Handling ───────────────────────── */

  /**
   * Parse and route incoming WebSocket messages.
   * Expected server message format:
   *   { "channel": "market:ZQM2025", "data": { ... } }
   * or a simple pong:
   *   { "type": "pong" }
   * @param {MessageEvent} event
   */
  _handleMessage(event) {
    let parsed;
    try {
      parsed = JSON.parse(event.data);
    } catch {
      // Non-JSON message — forward raw to global handlers
      this._messageHandlers.forEach((handler) => {
        try { handler(event.data); } catch (e) { console.error('[WSClient] handler error:', e); }
      });
      return;
    }

    // Handle heartbeat pong
    if (parsed.type === 'pong') {
      this._lastPong = Date.now();
      this._clearHeartbeatTimeout();
      return;
    }

    // Notify global handlers
    this._messageHandlers.forEach((handler) => {
      try { handler(parsed); } catch (e) { console.error('[WSClient] handler error:', e); }
    });

    // Route to channel subscribers
    const channel = parsed.channel;
    if (channel && this._channels.has(channel)) {
      this._channels.get(channel).forEach((callback) => {
        try { callback(parsed.data, parsed); } catch (e) { console.error(`[WSClient] channel "${channel}" handler error:`, e); }
      });
    }
  }

  /**
   * Send a subscription message to the server.
   * @param {string} channel
   */
  _sendSubscribe(channel) {
    this.send({ type: 'subscribe', channel });
  }

  /**
   * Send an unsubscription message to the server.
   * @param {string} channel
   */
  _sendUnsubscribe(channel) {
    this.send({ type: 'unsubscribe', channel });
  }

  /* ── Internal: Heartbeat ──────────────────────────────── */

  /**
   * Start the heartbeat ping/pong cycle.
   */
  _startHeartbeat() {
    this._stopHeartbeat();
    this._lastPong = Date.now();

    this._heartbeatInterval = setInterval(() => {
      if (!this.connected) return;

      // Send ping
      this.send({ type: 'ping', ts: Date.now() });

      // Set pong timeout
      this._heartbeatTimeout = setTimeout(() => {
        console.warn('[WSClient] Heartbeat timeout — no pong received');
        // Force close so reconnection kicks in
        if (this._ws) {
          this._ws.close(4000, 'Heartbeat timeout');
        }
      }, this.heartbeatTimeoutMs);
    }, this.heartbeatIntervalMs);
  }

  /**
   * Stop heartbeat.
   */
  _stopHeartbeat() {
    clearInterval(this._heartbeatInterval);
    this._heartbeatInterval = null;
    this._clearHeartbeatTimeout();
  }

  /**
   * Clear the pong timeout (called when pong is received).
   */
  _clearHeartbeatTimeout() {
    clearTimeout(this._heartbeatTimeout);
    this._heartbeatTimeout = null;
  }

  /* ── Internal: Reconnection ───────────────────────────── */

  /**
   * Schedule a reconnection attempt with exponential backoff.
   */
  _scheduleReconnect() {
    if (this._reconnectAttempt >= this.maxReconnectAttempts) {
      console.error(`[WSClient] Max reconnect attempts (${this.maxReconnectAttempts}) reached. Giving up.`);
      return;
    }

    this._reconnectAttempt++;
    // Exponential backoff with jitter
    const base = Math.min(
      this.reconnectBaseMs * Math.pow(2, this._reconnectAttempt - 1),
      this.reconnectMaxMs
    );
    const jitter = base * 0.2 * Math.random(); // ±20% jitter
    const delay = Math.round(base + jitter);

    console.log(
      `%c[WSClient] Reconnecting in ${delay}ms (attempt ${this._reconnectAttempt})`,
      'color:#fbbf24'
    );

    this._reconnectTimer = setTimeout(() => {
      this._reconnectTimer = null;
      this.connect().catch((err) => {
        console.error('[WSClient] Reconnect failed:', err);
      });
    }, delay);
  }

  /**
   * Clear pending reconnection timer.
   */
  _clearReconnectTimer() {
    clearTimeout(this._reconnectTimer);
    this._reconnectTimer = null;
  }

  /**
   * Force an immediate reconnection attempt.
   */
  reconnect() {
    this.disconnect();
    this._intentionalClose = false;
    this._reconnectAttempt = 0;
    return this.connect();
  }
}

/* ── Singleton Export ──────────────────────────────────────── */

// Determine WS URL from current page location
const _wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const _wsUrl = `${_wsProtocol}//${window.location.host}/ws`;

/**
 * Default shared WebSocket client instance.
 */
const wsClient = new WSClient(_wsUrl);

// Expose globally
window.WSClient = WSClient;
window.wsClient = wsClient;
