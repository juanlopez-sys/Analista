/* ============================================================
   api.js — Comunicación con el backend Python (FastAPI)
   Incluye el token JWT de Supabase en cada request
   ============================================================ */

'use strict';

// ── URL del backend ──────────────────────────────────────────
const API_BASE = (() => {
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'http://localhost:8000/api';
  }
  const injected = '__BACKEND_URL__';
  if (!injected.startsWith('__')) return injected + '/api';
  return window.location.origin + '/api';
})();

/**
 * Realiza una llamada al backend.
 * Incluye automáticamente el token JWT de Supabase si hay sesión activa.
 */
async function apiCall(endpoint, data = {}, method = 'POST') {
  try {
    const token = typeof getToken === 'function' ? getToken() : null;
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const opts = { method, headers };

    let url;
    if (method === 'GET' && Object.keys(data).length > 0) {
      const params = {};
      Object.entries(data).forEach(([k, v]) => {
        if (v !== null && v !== undefined && v !== '') {
          params[sanitize(k)] = sanitize(String(v));
        }
      });
      url = `${API_BASE}/${endpoint}?${new URLSearchParams(params)}`;
    } else {
      url = `${API_BASE}/${endpoint}`;
      if (method !== 'GET') opts.body = JSON.stringify(data);
    }

    const res = await fetch(url, opts);

    if (res.status === 401) {
      if (typeof showLoginScreen === 'function') showLoginScreen();
      throw new Error('Sesión expirada — vuelve a iniciar sesión');
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
      throw new Error(err.detail || err.error || `Error del servidor: ${res.status}`);
    }

    return await res.json();

  } catch (e) {
    if (e instanceof TypeError && e.message.includes('fetch')) {
      throw new Error('No se puede conectar al servidor');
    }
    throw e;
  }
}

/* ── ENDPOINTS ── */
const API = {
  health:        ()              => apiCall('health', {}, 'GET'),
  systemInfo:    ()              => apiCall('system-info', {}, 'GET'),
  getPrices:     ()              => apiCall('get-prices', {}, 'GET'),
  updateCandles: ()              => apiCall('update-candles', {}),
  updateNews:    ()              => apiCall('update-news', {}),
  updateAll:     ()              => apiCall('update-data', {}),
  getNews:       (limit = 20)   => apiCall('get-news', { limit }, 'GET'),
  analyzeOne:    (crypto, style) => apiCall('analyze-one', { crypto, style }),
  analyzeAll:    (style)         => apiCall('analyze-all', { style }),
  analyzeBest:   (style)         => apiCall('analyze-best', { style }),
  chat:          (msg, crypto, history) => apiCall('chat', { message: msg, crypto, history }),
  getPositions:  ()              => apiCall('get-positions', {}, 'GET'),
  openPosition:  (data)          => apiCall('open-position', data),
  closePosition: (data)          => apiCall('close-position', data),
  getHistory:    (crypto = null) => apiCall('get-history', crypto ? { crypto } : {}, 'GET'),
  getLessons:    (crypto = null) => apiCall('get-lessons', crypto ? { crypto } : {}, 'GET'),
  saveCryptos:   (cryptos)       => apiCall('save-cryptos', { cryptos }),
  saveConfig:    (data)          => apiCall('save-config', data),
  getErrors:     ()              => apiCall('get-errors', {}, 'GET'),
  clearErrors:   ()              => apiCall('clear-errors', {}),
};
