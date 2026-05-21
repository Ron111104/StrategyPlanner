/* ============================================================
   CME Fed Funds Futures (ZQ) Strategy Planning Platform
   Utility Functions
   ============================================================ */

/* ── Formatting ───────────────────────────────────────────── */

/**
 * Format a price to fixed decimal places with comma grouping.
 * Fed funds futures prices are typically quoted to 4–5 decimals.
 * @param {number} price - The raw price value
 * @param {number} [decimals=4] - Number of decimal places
 * @returns {string} Formatted price string
 */
function formatPrice(price, decimals = 4) {
  if (price === null || price === undefined || isNaN(price)) return '—';
  const num = Number(price);
  const fixed = num.toFixed(decimals);
  const [intPart, decPart] = fixed.split('.');
  const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return decPart ? `${grouped}.${decPart}` : grouped;
}

/**
 * Format a value in basis points.
 * @param {number} bp - Basis points value
 * @param {number} [decimals=1] - Decimal places
 * @returns {string} e.g. "+3.5 bp"
 */
function formatBasisPoints(bp, decimals = 1) {
  if (bp === null || bp === undefined || isNaN(bp)) return '— bp';
  const num = Number(bp);
  const sign = num > 0 ? '+' : '';
  return `${sign}${num.toFixed(decimals)} bp`;
}

/**
 * Format a currency amount in USD.
 * @param {number} amount - Dollar amount
 * @param {number} [decimals=2] - Decimal places
 * @returns {string} e.g. "$1,234.56"
 */
function formatCurrency(amount, decimals = 2) {
  if (amount === null || amount === undefined || isNaN(amount)) return '—';
  const num = Number(amount);
  const abs = Math.abs(num);
  const formatted = abs.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  if (num < 0) return `-$${formatted}`;
  return `$${formatted}`;
}

/**
 * Format a percentage value.
 * @param {number} value - Percentage value (already in %, not decimal)
 * @param {number} [decimals=2] - Decimal places
 * @returns {string} e.g. "+1.25%"
 */
function formatPercent(value, decimals = 2) {
  if (value === null || value === undefined || isNaN(value)) return '—';
  const num = Number(value);
  const sign = num > 0 ? '+' : '';
  return `${sign}${num.toFixed(decimals)}%`;
}

/**
 * Format a unix timestamp (seconds or ms) into a human-readable string.
 * @param {number} ts - Unix timestamp (seconds or milliseconds)
 * @param {string} [format='datetime'] - One of: 'date', 'time', 'datetime', 'short', 'iso', 'relative'
 * @returns {string} Formatted timestamp
 */
function formatTimestamp(ts, format = 'datetime') {
  if (!ts) return '—';
  // Detect seconds vs milliseconds
  let ms = Number(ts);
  if (ms < 1e12) ms *= 1000;
  const d = new Date(ms);
  if (isNaN(d.getTime())) return '—';

  switch (format) {
    case 'date':
      return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    case 'time':
      return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    case 'datetime':
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' +
             d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    case 'short':
      return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    case 'iso':
      return d.toISOString();
    case 'relative':
      return _relativeTime(d);
    default:
      return d.toLocaleString('en-US');
  }
}

/**
 * Compute a relative time string (e.g. "3m ago", "2h ago").
 * @param {Date} date
 * @returns {string}
 */
function _relativeTime(date) {
  const now = Date.now();
  const diffMs = now - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  const diffWeek = Math.floor(diffDay / 7);
  return `${diffWeek}w ago`;
}

/* ── Color Helpers ────────────────────────────────────────── */

/**
 * Get color for a numeric change (positive = green, negative = red).
 * @param {number} change - Numeric change value
 * @returns {string} CSS color string
 */
function colorForChange(change) {
  if (change === null || change === undefined || isNaN(change)) return '#9ca3af';
  const num = Number(change);
  if (num > 0) return '#34d399'; // emerald
  if (num < 0) return '#fb7185'; // rose
  return '#9ca3af'; // gray
}

/**
 * Get color for a signal direction.
 * @param {string} direction - 'long', 'short', 'flat', or 'neutral'
 * @returns {string} CSS color string
 */
function colorForSignal(direction) {
  const d = (direction || '').toLowerCase();
  if (d === 'long' || d === 'buy') return '#34d399';
  if (d === 'short' || d === 'sell') return '#fb7185';
  return '#fbbf24'; // amber for neutral/flat
}

/**
 * Get color for a market regime type.
 * @param {string} regime - Regime classification
 * @returns {string} CSS color string
 */
function colorForRegime(regime) {
  const r = (regime || '').toLowerCase().replace(/[\s_]+/g, '-');
  const map = {
    'trending-up':    '#34d399',
    'trending-down':  '#fb7185',
    'range-bound':    '#fbbf24',
    'volatile':       '#a78bfa',
    'quiet':          '#9ca3af',
    'fed-day':        '#22d3ee',
    'mean-reverting': '#38bdf8',
  };
  return map[r] || '#9ca3af';
}

/**
 * Get the CSS class suffix for a regime badge.
 * @param {string} regime
 * @returns {string} e.g. 'trending-up'
 */
function regimeBadgeClass(regime) {
  return (regime || 'quiet').toLowerCase().replace(/[\s_]+/g, '-');
}

/* ── Functional Utilities ─────────────────────────────────── */

/**
 * Debounce a function — only invoke after `delay` ms of inactivity.
 * @param {Function} fn - Function to debounce
 * @param {number} delay - Delay in ms
 * @returns {Function} Debounced function with .cancel() method
 */
function debounce(fn, delay) {
  let timer = null;
  const debounced = function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn.apply(this, args);
    }, delay);
  };
  debounced.cancel = () => {
    clearTimeout(timer);
    timer = null;
  };
  return debounced;
}

/**
 * Throttle a function — invoke at most once per `delay` ms.
 * Uses leading + trailing edge invocation.
 * @param {Function} fn - Function to throttle
 * @param {number} delay - Minimum interval in ms
 * @returns {Function} Throttled function with .cancel() method
 */
function throttle(fn, delay) {
  let lastCall = 0;
  let timer = null;
  const throttled = function (...args) {
    const now = Date.now();
    const remaining = delay - (now - lastCall);
    if (remaining <= 0) {
      clearTimeout(timer);
      timer = null;
      lastCall = now;
      fn.apply(this, args);
    } else if (!timer) {
      timer = setTimeout(() => {
        lastCall = Date.now();
        timer = null;
        fn.apply(this, args);
      }, remaining);
    }
  };
  throttled.cancel = () => {
    clearTimeout(timer);
    timer = null;
  };
  return throttled;
}

/**
 * Deep-clone a JSON-serializable object.
 * @param {*} obj - Object to clone
 * @returns {*} Deep copy
 */
function deepClone(obj) {
  if (obj === null || typeof obj !== 'object') return obj;
  // Use structuredClone when available (modern browsers), fall back to JSON
  if (typeof structuredClone === 'function') {
    return structuredClone(obj);
  }
  return JSON.parse(JSON.stringify(obj));
}

/**
 * Generate a unique ID string.
 * @param {string} [prefix='id'] - Optional prefix
 * @returns {string} Unique identifier
 */
function generateId(prefix = 'id') {
  const ts = Date.now().toString(36);
  const rand = Math.random().toString(36).substring(2, 8);
  return `${prefix}_${ts}_${rand}`;
}

/* ── DOM / Notification Helpers ───────────────────────────── */

/** @type {HTMLElement|null} Cached toast container */
let _toastContainer = null;

/**
 * Ensure the toast container element exists.
 * @returns {HTMLElement}
 */
function _ensureToastContainer() {
  if (_toastContainer && document.body.contains(_toastContainer)) {
    return _toastContainer;
  }
  _toastContainer = document.createElement('div');
  _toastContainer.className = 'toast-container';
  _toastContainer.setAttribute('aria-live', 'polite');
  document.body.appendChild(_toastContainer);
  return _toastContainer;
}

/**
 * Show a toast notification.
 * @param {string} message - Notification text
 * @param {'info'|'success'|'warning'|'error'} [type='info'] - Notification type
 * @param {number} [duration=4000] - Auto-dismiss time in ms (0 = manual close)
 * @returns {HTMLElement} The toast element
 */
function showNotification(message, type = 'info', duration = 4000) {
  const container = _ensureToastContainer();

  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.setAttribute('role', 'alert');

  const icons = { info: 'ℹ', success: '✓', warning: '⚠', error: '✕' };
  const icon = icons[type] || icons.info;

  toast.innerHTML = `
    <span style="font-size:1rem;line-height:1">${icon}</span>
    <span>${_escapeHtml(message)}</span>
    <button class="toast__close" aria-label="Close">&times;</button>
  `;

  const closeBtn = toast.querySelector('.toast__close');
  const dismiss = () => {
    toast.style.animation = 'fadeOut 200ms ease-out forwards';
    setTimeout(() => toast.remove(), 200);
  };
  closeBtn.addEventListener('click', dismiss);

  container.appendChild(toast);

  if (duration > 0) {
    setTimeout(dismiss, duration);
  }

  return toast;
}

/**
 * Escape HTML to prevent XSS in toast messages.
 * @param {string} str
 * @returns {string}
 */
function _escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Show a loading overlay on an element.
 * @param {HTMLElement|string} element - Element or selector
 * @param {string} [text] - Optional loading text
 * @returns {HTMLElement} The overlay element (for later removal)
 */
function showLoading(element, text) {
  const el = typeof element === 'string' ? document.querySelector(element) : element;
  if (!el) return null;

  // Ensure relative positioning for the overlay
  const pos = getComputedStyle(el).position;
  if (pos === 'static') {
    el.style.position = 'relative';
    el.dataset._loadingRestoredPosition = 'true';
  }

  // Remove existing overlay if any
  const existing = el.querySelector('.loading-overlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.className = 'loading-overlay animate-fadeIn';
  overlay.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
      <div class="loading-spinner"></div>
      ${text ? `<span style="font-family:var(--font-mono);font-size:0.72rem;color:var(--text-tertiary)">${_escapeHtml(text)}</span>` : ''}
    </div>
  `;
  el.appendChild(overlay);
  return overlay;
}

/**
 * Hide the loading overlay on an element.
 * @param {HTMLElement|string} element - Element or selector
 */
function hideLoading(element) {
  const el = typeof element === 'string' ? document.querySelector(element) : element;
  if (!el) return;

  const overlay = el.querySelector('.loading-overlay');
  if (overlay) {
    overlay.style.animation = 'fadeOut 200ms ease-out forwards';
    setTimeout(() => overlay.remove(), 200);
  }

  if (el.dataset._loadingRestoredPosition === 'true') {
    el.style.position = '';
    delete el.dataset._loadingRestoredPosition;
  }
}

/**
 * Replace an element's content with skeleton loading placeholders.
 * @param {HTMLElement|string} element - Element or selector
 * @param {number} [lines=3] - Number of skeleton lines
 */
function showSkeleton(element, lines = 3) {
  const el = typeof element === 'string' ? document.querySelector(element) : element;
  if (!el) return;

  el.dataset._skeletonOriginal = el.innerHTML;
  let html = '';
  for (let i = 0; i < lines; i++) {
    const width = i === lines - 1 ? 'skeleton-text--short' : (i % 2 === 0 ? 'skeleton-text--full' : '');
    html += `<div class="skeleton skeleton-text ${width}"></div>`;
  }
  el.innerHTML = html;
}

/**
 * Restore the original content after skeleton loading.
 * @param {HTMLElement|string} element - Element or selector
 */
function hideSkeleton(element) {
  const el = typeof element === 'string' ? document.querySelector(element) : element;
  if (!el) return;
  if (el.dataset._skeletonOriginal !== undefined) {
    el.innerHTML = el.dataset._skeletonOriginal;
    delete el.dataset._skeletonOriginal;
  }
}

/* ── Export ────────────────────────────────────────────────── */

// Expose on window for inline scripts, Alpine.js, HTMX
window.Utils = {
  formatPrice,
  formatBasisPoints,
  formatCurrency,
  formatPercent,
  formatTimestamp,
  colorForChange,
  colorForSignal,
  colorForRegime,
  regimeBadgeClass,
  debounce,
  throttle,
  deepClone,
  generateId,
  showNotification,
  showLoading,
  hideLoading,
  showSkeleton,
  hideSkeleton,
};
