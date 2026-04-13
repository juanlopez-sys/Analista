/* ============================================================
   actions.js — Lógica de cada acción/botón del sistema
   Sistema Analista Crypto
   ============================================================ */

'use strict';

/* ── CRYPTOS ── */

// Todas las cryptos del sistema
window.CRYPTOS = {
  "BTCUSDT": "Bitcoin",        "ETHUSDT": "Ethereum",
  "SOLUSDT": "Solana",         "XRPUSDT": "Ripple",
  "DOGEUSDT": "Dogecoin",      "ADAUSDT": "Cardano",
  "AVAXUSDT": "Avalanche",     "DOTUSDT": "Polkadot",
  "XLMUSDT": "Stellar",        "ALGOUSDT": "Algorand",
  "VETUSDT": "VeChain",        "AAVEUSDT": "Aave",
  "INJUSDT": "Injective",      "GRTUSDT": "The Graph",
  "SNXUSDT": "Synthetix",      "CAKEUSDT": "PancakeSwap",
  "SANDUSDT": "The Sandbox",   "SUIUSDT": "Sui",
  "HBARUSDT": "Hedera",        "SEIUSDT": "Sei",
  "CKBUSDT": "Nervos CKB",     "FETUSDT": "Fetch.ai",
  "MASKUSDT": "Mask Network",  "AXSUSDT": "Axie Infinity",
  "SLPUSDT": "Smooth Love Potion", "APEUSDT": "ApeCoin",
  "MBOXUSDT": "Mobox",         "SHIBUSDT": "Shiba Inu",
  "ZENUSDT": "Horizen",        "LPTUSDT": "Livepeer",
  "XVGUSDT": "Verge",          "XECUSDT": "eCash",
  "TFUELUSDT": "Theta Fuel",   "POWRUSDT": "Power Ledger",
  "OGNUSDT": "Origin Protocol","C98USDT": "Coin98",
  "DUSKUSDT": "Dusk Network",  "IOTAUSDT": "IOTA",
  "SAHARAUSDT": "Sahara AI",
};

// Cryptos activas actualmente
let activeCryptos = new Set(["BTCUSDT","ETHUSDT","SOLUSDT"]);

/* ── GRID DE CRYPTOS ── */

/**
 * Construye el grid de checkboxes de cryptos.
 */
function buildCryptoGrid() {
  const grid = document.getElementById('cryptoGrid');
  if (!grid) return;

  grid.innerHTML = '';
  Object.entries(window.CRYPTOS).forEach(([sym, name]) => {
    const isActive = activeCryptos.has(sym);

    const div = document.createElement('div');
    div.className = 'crypto-check' + (isActive ? ' checked' : '');
    div.dataset.sym = sym;

    const input = document.createElement('input');
    input.type = 'checkbox';
    if (isActive) input.checked = true;

    const box = document.createElement('div');
    box.className = 'check-box';
    box.textContent = isActive ? '✓' : '';

    const label = document.createElement('span');
    label.className = 'crypto-name';
    label.textContent = sym.replace('USDT', '');

    div.appendChild(input);
    div.appendChild(box);
    div.appendChild(label);

    div.addEventListener('click', () => toggleCrypto(sym, div, box));
    grid.appendChild(div);
  });
}

/**
 * Activa/desactiva una crypto en el grid.
 */
function toggleCrypto(sym, el, boxEl) {
  if (activeCryptos.has(sym)) {
    activeCryptos.delete(sym);
    el.classList.remove('checked');
    if (boxEl) boxEl.textContent = '';
  } else {
    activeCryptos.add(sym);
    el.classList.add('checked');
    if (boxEl) boxEl.textContent = '✓';
  }
}

/**
 * Selecciona o deselecciona todas las cryptos.
 * @param {boolean} select
 */
function selectAllCryptos(select) {
  Object.keys(window.CRYPTOS).forEach(sym => {
    if (select) activeCryptos.add(sym);
    else activeCryptos.delete(sym);
  });
  buildCryptoGrid();
}

/**
 * Rellena los <select> de cryptos en todo el sistema.
 */
function populateCryptoSelects() {
  const selectIds = [
    'analyzeOneCrypto', 'chatCrypto', 'openCrypto',
    'histCrypto', 'lessonCrypto'
  ];

  selectIds.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;

    // Conservar la primera opción vacía si existe
    const firstOpt = el.options[0] && el.options[0].value === ''
      ? el.options[0].cloneNode(true) : null;

    el.innerHTML = '';
    if (firstOpt) el.appendChild(firstOpt);

    [...activeCryptos].forEach(sym => {
      const opt = document.createElement('option');
      opt.value = sym;
      opt.textContent = (window.CRYPTOS[sym] || sym) + ' (' + sym.replace('USDT','') + ')';
      el.appendChild(opt);
    });
  });
}

/* ── MODO AUTOMÁTICO ── */

let autoTimer = null;

/**
 * Inicia o detiene el modo automático de actualización.
 */
function toggleAuto() {
  const btn    = document.getElementById('btnAuto');
  const status = document.getElementById('autoStatus');

  if (autoTimer) {
    clearInterval(autoTimer);
    autoTimer = null;
    btn.textContent = '▶ Iniciar modo automático';
    btn.classList.replace('btn-danger', 'btn-secondary');
    if (status) { status.textContent = 'Modo automático detenido.'; status.className = 'auto-status'; }
    toast('Modo automático detenido', 'warning');
    return;
  }

  const minutes = validateNumber(
    document.getElementById('autoInterval')?.value, 5, 1440
  );
  if (!minutes) { toast('Intervalo válido: 5 a 1440 minutos', 'error'); return; }

  btn.textContent = '■ Detener modo automático';
  btn.classList.replace('btn-secondary', 'btn-danger');

  const tick = () => {
    API.updateAll()
      .then(() => {
        if (status) {
          status.className = 'auto-status running';
          status.textContent = `✓ Actualizado. Próxima: ${minutes} min. Última: ${new Date().toLocaleTimeString('es-CL')}`;
        }
      })
      .catch(() => {});
  };

  tick();
  autoTimer = setInterval(tick, minutes * 60 * 1000);
  toast(`Modo automático iniciado — cada ${minutes} min`, 'success');
}

/* ── CARGAR POSICIONES PARA CERRAR ── */

async function loadOpenPositionsForClose() {
  try {
    const res = await API.getPositions();
    renderPositions(res.positions || [], 'closePosList', true);
  } catch (e) {
    const container = document.getElementById('closePosList');
    if (container) {
      container.innerHTML = '';
      container.appendChild(makeEmpty('!', e.message));
    }
  }
}

/* ── ACCIÓN PRINCIPAL ── */

/**
 * Ejecuta una acción del sistema con manejo de progreso y errores.
 * @param {string} action - Identificador de la acción
 * @param {HTMLElement|null} btnEl - Botón que disparó la acción
 */
async function runAction(action, btnEl) {
  // Solo aplicar rate limit si el usuario presionó un botón (btnEl !== null)
  // Las llamadas automáticas de nav.js pasan null y no deben bloquearse
  if (btnEl && !rateLimit(action, 500)) {
    toast('Espera un momento antes de volver a ejecutar', 'warning');
    return;
  }

  const boxId = `out-${action}`;
  if (btnEl) btnEl.disabled = true;

  // Mensajes descriptivos por acción
  const actionLabels = {
    'update-candles':  '⟳ Actualizando datos de mercado (velas e indicadores)...',
    'update-news':     '◎ Recolectando noticias...',
    'get-prices':      '$ Obteniendo precios actuales...',
    'analyze-one':     '◈ Analizando con Claude...',
    'analyze-all':     '◉ Analizando todas las cryptos con Claude...',
    'analyze-best':    '★ Buscando mejor oportunidad con Claude...',
    'get-news':        '◎ Cargando noticias guardadas...',
    'get-positions':   '◐ Cargando posiciones abiertas...',
    'open-position':   '+ Abriendo posición...',
    'close-position':  '× Cerrando posición y generando lección...',
    'get-history':     '≡ Cargando historial...',
    'get-lessons':     '◈ Cargando lecciones aprendidas...',
    'save-cryptos':    '◧ Guardando cryptos activas...',
    'save-config':     '⚙ Guardando configuración...',
    'get-system-info': '⚙ Obteniendo estado del sistema...',
    'get-errors':      '! Leyendo log de errores...',
    'clear-errors':    '! Limpiando log de errores...',
  };
  showAction(actionLabels[action] || '⟳ Ejecutando...');
  showOutput(boxId, [{ type: 'loading', text: 'Ejecutando...' }]);

  try {
    switch (action) {

      /* ── DATOS ── */
      case 'update-candles': {
        showOutput(boxId, [{ type: 'loading', text: 'Descargando velas de Binance...' }]);
        const res = await API.updateCandles();
        showOutput(boxId, [
          { type: 'ok', text: `${res.total_new || 0} velas nuevas guardadas` }
        ], res.summary || null);
        toast('Velas actualizadas', 'success');
        break;
      }

      case 'update-news': {
        showOutput(boxId, [
          { type: 'loading', text: 'Descargando noticias de CryptoCompare...' },
          { type: 'info',    text: 'Claude buscando noticias macro...' },
        ]);
        const res = await API.updateNews();
        showOutput(boxId, [
          { type: 'ok', text: `${res.total_new || 0} noticias nuevas guardadas` }
        ]);
        toast('Noticias actualizadas', 'success');
        break;
      }

      case 'update-data': {
        await API.updateAll();
        toast('Datos actualizados', 'success');
        break;
      }

      /* ── PRECIOS ── */
      case 'get-prices': {
        showOutput(boxId, [{ type: 'loading', text: 'Obteniendo precios de Binance...' }]);
        const res = await API.getPrices();
        const count = Object.keys(res.prices || {}).length;
        showOutput(boxId, [{ type: 'ok', text: `${count} precios obtenidos` }]);
        renderPricesTable(res.prices || {});
        break;
      }

      /* ── NOTICIAS ── */
      case 'get-news': {
        showOutput(boxId, [{ type: 'loading', text: 'Cargando noticias de la base de datos...' }]);
        const res = await API.getNews(30);
        showOutput(boxId, [{ type: 'ok', text: `${res.news?.length || 0} noticias cargadas` }]);
        renderNewsList(res.news || []);
        break;
      }

      /* ── ANÁLISIS ── */
      case 'analyze-one': {
        const crypto = validateCrypto(document.getElementById('analyzeOneCrypto')?.value);
        const style  = document.getElementById('analyzeOneStyle')?.value || '5';
        if (!crypto) { toast('Selecciona una crypto', 'warning'); break; }

        showOutput(boxId, [
          { type: 'loading', text: `Obteniendo datos de ${window.CRYPTOS[crypto] || crypto}...` },
          { type: 'info',    text: 'Claude analizando soportes, resistencias y patrones...' },
          { type: 'info',    text: 'Generando recomendación final...' },
        ]);

        const res = await API.analyzeOne(crypto, style);
        showOutput(boxId, [{ type: 'ok', text: 'Análisis completado' }], res.response || 'Sin respuesta');
        break;
      }

      case 'analyze-all': {
        const style = document.getElementById('analyzeAllStyle')?.value || '5';
        showOutput(boxId, [
          { type: 'loading', text: `Analizando ${activeCryptos.size} cryptos activas...` },
          { type: 'info',    text: 'Esto puede tomar varios minutos...' },
        ]);
        const res = await API.analyzeAll(style);
        showOutput(boxId, [{ type: 'ok', text: 'Análisis completado' }], res.response || 'Sin respuesta');
        break;
      }

      case 'analyze-best': {
        const style = document.getElementById('bestStyle')?.value || '5';
        showOutput(boxId, [
          { type: 'loading', text: 'Comparando todas las cryptos activas...' },
          { type: 'info',    text: 'Claude evaluando la mejor oportunidad...' },
        ]);
        const res = await API.analyzeBest(style);
        showOutput(boxId, [{ type: 'ok', text: 'Análisis completado' }], res.response || 'Sin respuesta');
        break;
      }

      /* ── POSICIONES ── */
      case 'get-positions': {
        showOutput(boxId, [{ type: 'loading', text: 'Cargando posiciones abiertas...' }]);
        const res = await API.getPositions();
        showOutput(boxId, [
          { type: 'ok', text: `${res.positions?.length || 0} posiciones abiertas` }
        ]);
        renderPositions(res.positions || [], 'positionsList');
        break;
      }

      case 'open-position': {
        const crypto    = validateCrypto(document.getElementById('openCrypto')?.value);
        const price     = validateNumber(document.getElementById('openPrice')?.value, 0.0001, 10_000_000);
        const date      = validateDate(document.getElementById('openDate')?.value);
        const time      = validateTime(document.getElementById('openTime')?.value);
        const timeframe = document.getElementById('openTimeframe')?.value || null;
        const notes     = sanitizeInput(document.getElementById('openNotes')?.value || '', 500);

        if (!crypto) { toast('Selecciona una crypto',      'warning'); break; }
        if (!price)  { toast('Ingresa un precio válido',   'warning'); break; }
        if (!date)   { toast('Selecciona una fecha',       'warning'); break; }
        if (!time)   { toast('Selecciona una hora',        'warning'); break; }

        showOutput(boxId, [{ type: 'loading', text: 'Guardando posición...' }]);

        const res = await API.openPosition({
          crypto, price, date, time,
          timeframe: timeframe || null,
          notes: notes || null,
        });

        showOutput(boxId, [
          { type: 'ok', text: `Posición #${res.position_id} abierta correctamente` }
        ]);
        toast(`Posición abierta en ${window.CRYPTOS[crypto] || crypto}`, 'success');

        // Limpiar formulario
        ['openPrice','openNotes'].forEach(id => {
          const el = document.getElementById(id);
          if (el) el.value = '';
        });
        break;
      }

      case 'close-position': {
        const posId = validateNumber(document.getElementById('closePosId')?.value, 1);
        const price = validateNumber(document.getElementById('closePrice')?.value, 0.0001, 10_000_000);
        const date  = validateDate(document.getElementById('closeDate')?.value);
        const time  = validateTime(document.getElementById('closeTime')?.value);
        const notes = sanitizeInput(document.getElementById('closeNotes')?.value || '', 500);

        if (!posId) { toast('Ingresa un ID de posición válido', 'warning'); break; }
        if (!price) { toast('Ingresa un precio de salida válido', 'warning'); break; }
        if (!date)  { toast('Selecciona una fecha', 'warning'); break; }
        if (!time)  { toast('Selecciona una hora',  'warning'); break; }

        showOutput(boxId, [
          { type: 'loading', text: 'Cerrando posición...' },
          { type: 'info',    text: 'Claude generando lección aprendida...' },
        ]);

        const res = await API.closePosition({
          position_id: posId, price, date, time,
          notes: notes || null,
        });

        const pnl   = parseFloat(res.result_pct || 0);
        const isPos = pnl >= 0;

        showOutput(boxId, [
          { type: 'ok',              text: `Posición #${posId} cerrada` },
          { type: isPos ? 'ok':'err', text: `Resultado: ${isPos?'+':''}${pnl.toFixed(2)}%` },
          { type: 'info',            text: `Lección #${res.lesson_id} generada` },
        ]);

        toast(`Posición cerrada: ${isPos?'+':''}${pnl.toFixed(2)}%`,
              isPos ? 'success' : 'error');

        loadOpenPositionsForClose();
        break;
      }

      /* ── HISTORIAL ── */
      case 'get-history': {
        const crypto = document.getElementById('histCrypto')?.value || null;
        showOutput(boxId, [{ type: 'loading', text: 'Cargando historial...' }]);
        const res = await API.getHistory(crypto || null);
        showOutput(boxId, [{ type: 'ok', text: `${res.positions?.length || 0} posiciones encontradas` }]);
        renderHistoryTable(res.positions || []);
        break;
      }

      case 'get-lessons': {
        const crypto = document.getElementById('lessonCrypto')?.value || null;
        showOutput(boxId, [{ type: 'loading', text: 'Cargando lecciones...' }]);
        const res = await API.getLessons(crypto || null);
        showOutput(boxId, [{ type: 'ok', text: `${res.lessons?.length || 0} lecciones encontradas` }]);
        renderLessons(res.lessons || []);
        break;
      }

      /* ── CONFIGURACIÓN ── */
      case 'save-cryptos': {
        if (activeCryptos.size === 0) {
          toast('Selecciona al menos una crypto', 'warning');
          break;
        }
        showOutput(boxId, [{ type: 'loading', text: 'Guardando configuración...' }]);
        await API.saveCryptos([...activeCryptos]);
        showOutput(boxId, [{ type: 'ok', text: `${activeCryptos.size} cryptos activas guardadas` }]);
        populateCryptoSelects();
        toast('Cryptos activas actualizadas', 'success');
        break;
      }

      case 'save-config': {
        const newsMode = getRadioValue('newsMode') || 'ambas';
        showOutput(boxId, [{ type: 'loading', text: 'Guardando configuración...' }]);
        await API.saveConfig({ news_mode: newsMode });
        showOutput(boxId, [{ type: 'ok', text: `Modo noticias: ${newsMode}` }]);
        toast('Configuración guardada', 'success');
        break;
      }

      case 'get-system-info': {
        showOutput(boxId, [{ type: 'loading', text: 'Obteniendo estado del sistema...' }]);
        const res = await API.systemInfo();
        showOutput(boxId, [
          { type: 'ok',                    text: `Cryptos activas: ${res.active_cryptos || 0}` },
          { type: 'info',                  text: `Posiciones abiertas: ${res.open_positions || 0}` },
          { type: 'info',                  text: `Noticias en BD: ${res.news_count || 0}` },
          { type: 'info',                  text: `Modo noticias: ${res.news_mode || '—'}` },
          { type: res.claude_ok ? 'ok':'err', text: `Claude API: ${res.claude_ok ? 'conectado' : 'sin clave'}` },
        ]);
        break;
      }

      /* ── ERRORES ── */
      case 'get-errors': {
        showOutput(boxId, [{ type: 'loading', text: 'Leyendo log de errores...' }]);
        const res = await API.getErrors();
        showOutput(boxId, [{ type: 'ok', text: `${res.errors?.length || 0} errores encontrados` }]);
        renderErrors(res.errors || []);
        break;
      }

      case 'clear-errors': {
        if (!confirm('¿Seguro que quieres limpiar el log de errores?')) break;
        showOutput(boxId, [{ type: 'loading', text: 'Limpiando log...' }]);
        await API.clearErrors();
        showOutput(boxId, [{ type: 'ok', text: 'Log de errores limpiado' }]);
        renderErrors([]);
        toast('Log limpiado', 'success');
        break;
      }

      default:
        showOutput(boxId, [{ type: 'warn', text: `Acción no implementada: ${sanitize(action)}` }]);
    }

  } catch (e) {
    showOutput(boxId, [{ type: 'err', text: String(e.message) }]);
    toast(String(e.message).slice(0, 120), 'error', 5000);
  } finally {
    hideAction();
    if (btnEl) btnEl.disabled = false;
  }
}

/* ============================================================
   IMPORTAR BASE DE DATOS (.db)
   ============================================================ */

/* ============================================================
   IMPORTAR BASE DE DATOS (.db) — con progreso SSE
   ============================================================ */

function initImportDb() {
  const fileInput = document.getElementById('importDbFile');
  const fileLabel = document.getElementById('importDbFileName');
  const btnImport = document.getElementById('btnImportDb');
  const outBox    = document.getElementById('out-import-db');

  if (!fileInput) return;

  fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (file) {
      fileLabel.textContent = `✓ ${file.name} (${(file.size/1024/1024).toFixed(1)} MB)`;
      btnImport.disabled = false;
    } else {
      fileLabel.textContent = '';
      btnImport.disabled = true;
    }
  });

  btnImport.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) return;

    btnImport.disabled = true;

    // Inyectar UI de progreso
    outBox.innerHTML = `
      <div id="import-progress-wrap" style="margin-top:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <span id="import-status-text" style="font-size:12px; color:var(--text-muted, #aaa);">Subiendo archivo...</span>
          <span id="import-pct-label" style="font-size:13px; font-weight:700; color:var(--accent, #00ffaa); min-width:38px; text-align:right;">0%</span>
        </div>
        <div style="background:var(--bg-input, #1a1a2e); border-radius:6px; height:10px; overflow:hidden; position:relative;">
          <div id="import-bar" style="
            height:100%; width:0%; border-radius:6px;
            background: linear-gradient(90deg, #00c896, #00ffaa);
            transition: width 0.35s ease;
            box-shadow: 0 0 8px #00ffaa55;
          "></div>
        </div>
        <div id="import-log" style="
          margin-top:10px; max-height:160px; overflow-y:auto;
          font-size:11px; font-family:monospace; color:var(--text-muted, #888);
          line-height:1.6;
        "></div>
      </div>`;

    const bar       = document.getElementById('import-bar');
    const pctLabel  = document.getElementById('import-pct-label');
    const statusTxt = document.getElementById('import-status-text');
    const logDiv    = document.getElementById('import-log');

    function setProgress(pct) {
      bar.style.width      = pct + '%';
      pctLabel.textContent = pct + '%';
    }

    function addLog(text, color) {
      const line = document.createElement('div');
      line.textContent = text;
      if (color) line.style.color = color;
      logDiv.appendChild(line);
      logDiv.scrollTop = logDiv.scrollHeight;
    }

    try {
      const token   = typeof getToken === 'function' ? getToken() : null;
      const formData = new FormData();
      formData.append('file', file);

      const API_URL = typeof API_BASE !== 'undefined' ? API_BASE : '';
      const response = await fetch(`${API_URL}/import-db-progress`, {
        method:  'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        body:    formData,
      });

      if (response.status === 401) {
        if (typeof showLoginScreen === 'function') showLoginScreen();
        throw new Error('Sesión expirada — vuelve a iniciar sesión');
      }
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${response.status}`);
      }

      // Leer SSE del body como stream de texto
      const reader  = response.body.getReader();
      const decoder = new TextDecoder();
      let   buffer  = '';

      statusTxt.textContent = 'Importando...';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // lo que quede sin \n queda para el próximo chunk

        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          let evt;
          try { evt = JSON.parse(line.slice(5).trim()); } catch { continue; }

          if (evt.type === 'start') {
            addLog(`📂 ${evt.msg}`, '#00ffaa');
            statusTxt.textContent = evt.msg;

          } else if (evt.type === 'progress') {
            setProgress(evt.pct);
            statusTxt.textContent = `Procesando ${evt.table} (${evt.current}/${evt.total})`;

          } else if (evt.type === 'table_done') {
            setProgress(evt.pct);
            if (evt.error) {
              addLog(`⚠ ${evt.table}: error`, '#ff6b6b');
            } else if (evt.nuevas > 0) {
              addLog(`✓ ${evt.table}: ${evt.nuevas.toLocaleString()} velas nuevas`, '#00e89a');
            }

          } else if (evt.type === 'done') {
            setProgress(100);
            statusTxt.textContent = '¡Importación completada!';
            bar.style.background  = 'linear-gradient(90deg, #00c896, #00ffaa)';
            addLog(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`, '#444');
            addLog(`✅ Total velas importadas: ${evt.total_nuevas?.toLocaleString() || 0}`, '#00ffaa');
            addLog(`📁 Tablas con datos nuevos: ${evt.tablas_ok} de ${evt.total_tablas}`, '#00ffaa');
            if (evt.errores?.length) addLog(`⚠ ${evt.errores.length} errores menores`, '#ffb347');
            if (typeof toast === 'function') toast(`Importadas ${evt.total_nuevas?.toLocaleString() || 0} velas nuevas`, 'success', 5000);

          } else if (evt.type === 'error') {
            statusTxt.textContent = 'Error en la importación';
            bar.style.background  = '#ff4444';
            addLog(`❌ ${evt.msg}`, '#ff6b6b');
            if (typeof toast === 'function') toast(evt.msg.slice(0, 120), 'error', 5000);
          }
        }
      }

    } catch (e) {
      statusTxt.textContent = 'Error';
      bar.style.background  = '#ff4444';
      addLog(`❌ ${e.message}`, '#ff6b6b');
      if (typeof toast === 'function') toast(String(e.message).slice(0, 120), 'error', 5000);
    } finally {
      btnImport.disabled = false;
    }
  });
}

// initImportDb() es llamada desde main.js → init() tras el login
