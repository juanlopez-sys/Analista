/* ============================================================
   main.js — Inicialización del sistema
   init() es llamado por auth.js DESPUÉS del login exitoso
   ============================================================ */

'use strict';

async function checkServerStatus() {
  const dot  = document.getElementById('statusDot');
  const text = document.getElementById('statusText');
  try {
    await API.health();
    if (dot)  dot.className   = 'status-dot ok';
    if (text) text.textContent = 'Sistema conectado';
  } catch {
    if (dot)  dot.className   = 'status-dot err';
    if (text) text.textContent = 'Sin conexión — inicia api.py';
  }
}

async function refreshTopbarPrices() {
  try {
    const res = await API.getPrices();
    if (res.prices) updateTopbarPrices(res.prices);
  } catch { /* silencioso */ }
}

/**
 * Inicializa el sistema. Es llamado por auth.js tras login exitoso.
 */
function init() {
  const today   = new Date().toISOString().split('T')[0];
  const nowTime = new Date().toTimeString().slice(0, 5);

  ['openDate', 'closeDate'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = today;
  });
  ['openTime', 'closeTime'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = nowTime;
  });

  buildCryptoGrid();
  populateCryptoSelects();

  if (typeof initImportDb === 'function') initImportDb();

  checkServerStatus();
  setInterval(checkServerStatus, 30_000);

  refreshTopbarPrices();
  setInterval(refreshTopbarPrices, 60_000);

  const chatInput = document.getElementById('chatInput');
  if (chatInput) {
    chatInput.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChat();
      }
    });
  }
}
// NOTA: NO hay DOMContentLoaded aquí — auth.js llama a init() tras el login
