/* ============================================================
   nav.js — Navegación y registro de eventos del DOM
   Sin onclick inline — todos los handlers se asignan aquí
   Sistema Analista Crypto
   ============================================================ */

'use strict';

// Mapa de panel → output-boxes que contiene
const _panelOutputs = {
  'datos':          ['out-update-candles', 'out-update-news'],
  'precios':        ['out-get-prices'],
  'noticias':       ['out-get-news'],
  'analizar-una':   ['out-analyze-one'],
  'analizar-todas': ['out-analyze-all'],
  'mejor':          ['out-analyze-best'],
  'posiciones':     ['out-get-positions'],
  'abrir':          ['out-open-position'],
  'cerrar':         ['out-close-position'],
  'historial':      ['out-get-history', 'out-get-lessons'],
  'config':         ['out-save-config', 'out-get-system-info', 'out-save-cryptos'],
  'errores':        ['out-get-errors'],
};

/**
 * Cambia el panel activo y restaura resultados previos.
 */
function switchPanel(panelId, navEl) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const panel = document.getElementById('panel-' + panelId);
  if (panel) panel.classList.add('active');
  if (navEl) navEl.classList.add('active');

  // Restaurar resultados previos del panel
  const outputs = _panelOutputs[panelId] || [];
  outputs.forEach(boxId => restoreOutput(boxId));

  // Acciones automáticas al entrar a ciertos paneles
  switch (panelId) {
    case 'cerrar':
      loadOpenPositionsForClose();
      break;
    case 'posiciones':
      if (!_outputCache['out-get-positions']) runAction('get-positions', null);
      break;
    case 'precios':
      if (!_outputCache['out-get-prices']) runAction('get-prices', null);
      break;
  }
}

/**
 * Cambia el tab activo dentro de un panel.
 */
function switchTab(allTabIds, targetId, clickedTab) {
  allTabIds.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });

  if (clickedTab && clickedTab.parentElement) {
    clickedTab.parentElement.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  }

  const target = document.getElementById(targetId);
  if (target) target.style.display = 'block';
  if (clickedTab) clickedTab.classList.add('active');
}

/**
 * Selecciona un radio button visual.
 */
function selectRadio(name, el) {
  document.querySelectorAll(`input[name="${CSS.escape(name)}"]`).forEach(r => {
    r.parentElement.classList.remove('selected');
  });
  const radio = el.querySelector('input[type="radio"]');
  if (radio) radio.checked = true;
  el.classList.add('selected');
}

/**
 * Retorna el valor del radio seleccionado en un grupo.
 */
function getRadioValue(name) {
  const checked = document.querySelector(`input[name="${CSS.escape(name)}"]:checked`);
  return checked ? checked.value : null;
}

/* ── REGISTRO DE EVENTOS ── */

document.addEventListener('DOMContentLoaded', () => {

  // ── Sidebar: cambio de panel
  document.querySelectorAll('.nav-item[data-panel]').forEach(el => {
    el.addEventListener('click', () => switchPanel(el.dataset.panel, el));
  });

  // ── Botones de acción (data-action)
  document.querySelectorAll('button[data-action]').forEach(btn => {
    btn.addEventListener('click', () => runAction(btn.dataset.action, btn));
  });

  // ── Tabs del historial
  document.querySelectorAll('.tab[data-tab-target]').forEach(tab => {
    tab.addEventListener('click', () => {
      const group  = tab.dataset.tabGroup;
      const target = tab.dataset.tabTarget;
      const allIds = [...document.querySelectorAll(`.tab[data-tab-group="${group}"]`)]
        .map(t => t.dataset.tabTarget);
      switchTab(allIds, target, tab);
    });
  });

  // ── Radio buttons de configuración
  document.querySelectorAll('.radio-item[data-radio-group]').forEach(el => {
    el.addEventListener('click', () => selectRadio(el.dataset.radioGroup, el));
  });

  // ── Cryptos: seleccionar/deseleccionar todas
  const btnAll = document.getElementById('btnSelectAll');
  const btnNone = document.getElementById('btnDeselectAll');
  if (btnAll)  btnAll.addEventListener('click',  () => selectAllCryptos(true));
  if (btnNone) btnNone.addEventListener('click', () => selectAllCryptos(false));

  // ── Modo automático
  const btnAuto = document.getElementById('btnAuto');
  if (btnAuto) btnAuto.addEventListener('click', toggleAuto);

  // ── Chat: enviar y limpiar
  const btnSend  = document.getElementById('btnSendChat');
  const btnClear = document.getElementById('btnClearChat');
  if (btnSend)  btnSend.addEventListener('click',  sendChat);
  if (btnClear) btnClear.addEventListener('click', clearChat);

});
