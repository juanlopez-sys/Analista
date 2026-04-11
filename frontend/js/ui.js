/* ============================================================
   ui.js — Output boxes, toasts, renders de datos en pantalla
   Sistema Analista Crypto
   ============================================================ */

'use strict';

/* ── OUTPUT BOX ── */

// Cache que guarda el último HTML renderizado por cada output-box
const _outputCache = {};

/**
 * Muestra líneas de progreso en un output box y guarda en cache.
 * @param {string} boxId - ID del elemento .output-box
 * @param {Array<{type, text}>} lines - Líneas a mostrar
 * @param {string|null} result - Texto largo de resultado (pre)
 */
function showOutput(boxId, lines = [], result = null) {
  const box = document.getElementById(boxId);
  if (!box) return;

  box.innerHTML = '';
  box.classList.add('visible');

  const icons = { ok: '✓', err: '✗', info: '→', warn: '⚠', loading: '◌' };

  lines.forEach(({ type, text }) => {
    const div = document.createElement('div');
    div.className = `output-line ${type}`;
    const icon = document.createElement('span');
    icon.className = 'icon';
    icon.textContent = icons[type] || '·';
    const span = document.createElement('span');
    span.textContent = text;
    div.appendChild(icon);
    div.appendChild(span);
    box.appendChild(div);
  });

  if (result !== null) {
    const pre = document.createElement('div');
    pre.className = 'output-result';
    pre.textContent = result;
    box.appendChild(pre);
  }

  // No cachear estados de carga — solo resultados finales
  const isLoading = lines.length > 0 && lines.every(l => l.type === 'loading' || l.type === 'info');
  if (!isLoading) {
    _outputCache[boxId] = box.innerHTML;
  }
}

/**
 * Restaura el último resultado guardado en un output-box.
 * @param {string} boxId
 */
function restoreOutput(boxId) {
  const box = document.getElementById(boxId);
  if (!box || !_outputCache[boxId]) return;
  box.innerHTML = _outputCache[boxId];
  box.classList.add('visible');
}

/**
 * Oculta un output box.
 * @param {string} boxId
 */
function hideOutput(boxId) {
  const box = document.getElementById(boxId);
  if (box) { box.classList.remove('visible'); box.innerHTML = ''; }
}

/* ── TOASTS ── */

/**
 * Muestra una notificación flotante temporal.
 * @param {string} msg - Mensaje a mostrar
 * @param {'success'|'error'|'warning'} type
 * @param {number} duration - Milisegundos antes de desaparecer
 */
function toast(msg, type = 'success', duration = 3000) {
  const tc = document.getElementById('toastContainer');
  if (!tc) return;

  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = String(msg).slice(0, 200); // textContent — seguro
  tc.appendChild(t);

  setTimeout(() => {
    t.style.opacity = '0';
    t.style.transition = 'opacity 0.3s';
    setTimeout(() => t.remove(), 300);
  }, duration);
}

/* ── RENDERS ESPECÍFICOS ── */

/**
 * Renderiza la tabla de precios.
 * @param {Object} prices - { BTCUSDT: 69500, ... }
 */
function renderPricesTable(prices) {
  const tbody = document.getElementById('pricesTable');
  if (!tbody || !prices) return;

  tbody.innerHTML = '';
  Object.entries(prices).forEach(([sym, price]) => {
    const tr = document.createElement('tr');

    const tdName  = document.createElement('td');
    const tdSym   = document.createElement('td');
    const tdPrice = document.createElement('td');

    tdName.textContent  = (window.CRYPTOS || {})[sym] || sym;
    tdSym.textContent   = sym.replace('USDT', '');
    tdSym.style.color   = 'var(--text3)';
    tdPrice.textContent = '$' + parseFloat(price).toLocaleString('es-CL', {
      minimumFractionDigits: 2, maximumFractionDigits: 4
    });
    tdPrice.style.fontWeight = '700';

    tr.appendChild(tdName);
    tr.appendChild(tdSym);
    tr.appendChild(tdPrice);
    tbody.appendChild(tr);
  });

  // Actualizar topbar
  updateTopbarPrices(prices);
}

/**
 * Actualiza los precios BTC/ETH/SOL del topbar.
 * @param {Object} prices
 */
function updateTopbarPrices(prices) {
  const map = {
    'BTCUSDT': 'tp-btc',
    'ETHUSDT': 'tp-eth',
    'SOLUSDT': 'tp-sol',
  };
  Object.entries(map).forEach(([sym, elId]) => {
    const el = document.getElementById(elId);
    if (el && prices[sym]) {
      el.textContent = '$' + parseFloat(prices[sym]).toLocaleString('es-CL', {
        minimumFractionDigits: 0, maximumFractionDigits: 0
      });
    }
  });
}

/**
 * Renderiza la lista de noticias.
 * @param {Array} news
 */
function renderNewsList(news) {
  const list = document.getElementById('newsList');
  if (!list) return;

  if (!news || news.length === 0) {
    list.innerHTML = '';
    list.appendChild(makeEmpty('◎', 'Sin noticias. Ejecuta Actualizar noticias primero.'));
    return;
  }

  list.innerHTML = '';
  news.forEach(n => {
    const sentEmoji = n.sentiment === 'positive' ? '🟢'
                    : n.sentiment === 'negative' ? '🔴' : '🟡';

    const div = document.createElement('div');
    div.className = 'news-item';

    const title = document.createElement('div');
    title.className = 'news-title';
    title.textContent = sentEmoji + ' ' + (n.title || '');

    const meta = document.createElement('div');
    meta.className = 'news-meta';

    const src = document.createElement('span');
    src.textContent = n.source || '';

    const impact = document.createElement('span');
    impact.className = 'badge ' + (
      n.impact === 'high'   ? 'badge-red' :
      n.impact === 'medium' ? 'badge-yellow' : 'badge-green'
    );
    impact.textContent = n.impact || 'low';

    const dt = document.createElement('span');
    dt.textContent = (n.datetime || '').slice(0, 16);

    meta.appendChild(src);
    meta.appendChild(impact);
    meta.appendChild(dt);

    if (n.categoria) {
      const cat = document.createElement('span');
      cat.className = 'badge badge-blue';
      cat.textContent = n.categoria;
      meta.appendChild(cat);
    }

    div.appendChild(title);

    if (n.resumen) {
      const sum = document.createElement('div');
      sum.className = 'news-summary';
      sum.textContent = n.resumen;
      div.appendChild(sum);
    }

    div.appendChild(meta);
    list.appendChild(div);
  });
}

/**
 * Renderiza posiciones abiertas.
 * @param {Array} positions
 * @param {string} containerId
 * @param {boolean} clickable - Si al hacer click se llena el form de cierre
 */
function renderPositions(positions, containerId, clickable = false) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!positions || positions.length === 0) {
    container.innerHTML = '';
    container.appendChild(makeEmpty('◐', 'Sin posiciones abiertas'));
    return;
  }

  container.innerHTML = '';
  positions.forEach(pos => {
    const pnl   = parseFloat(pos.pnl_pct || 0);
    const isPos = pnl >= 0;

    const div = document.createElement('div');
    div.className = 'pos-card' + (clickable ? ' clickable' : '');

    const sym = document.createElement('div');
    sym.className = 'pos-symbol';
    sym.textContent = (pos.crypto || '').replace('USDT', '');

    const details = document.createElement('div');
    details.className = 'pos-details';

    const row = document.createElement('div');
    row.className = 'pos-detail-row';

    const detailsData = [
      ['ID',             '#' + pos.id],
      ['Entrada',        '$' + parseFloat(pos.entry_price || 0).toFixed(4)],
      ['Precio actual',  '$' + parseFloat(pos.current_price || 0).toFixed(4)],
      ['Hora entrada',   pos.entry_time || '—'],
    ];

    if (pos.timeframe_focus) {
      detailsData.push(['TF', pos.timeframe_focus]);
    }

    detailsData.forEach(([label, val]) => {
      const d = document.createElement('div');
      d.className = 'pos-detail';
      const l = document.createElement('span');
      l.className = 'pos-detail-label';
      l.textContent = label;
      const v = document.createElement('span');
      v.className = 'pos-detail-val';
      v.textContent = val;
      d.appendChild(l);
      d.appendChild(v);
      row.appendChild(d);
    });

    details.appendChild(row);

    const pnlEl = document.createElement('div');
    pnlEl.className = 'pos-pnl ' + (isPos ? 'positive' : 'negative');
    pnlEl.textContent = (isPos ? '+' : '') + pnl.toFixed(2) + '%';

    div.appendChild(sym);
    div.appendChild(details);
    div.appendChild(pnlEl);

    if (clickable) {
      div.addEventListener('click', () => {
        const idEl = document.getElementById('closePosId');
        if (idEl) idEl.value = pos.id;
        toast(`Posición #${pos.id} seleccionada`, 'success');
      });
    }

    container.appendChild(div);
  });
}

/**
 * Renderiza historial de posiciones cerradas.
 * @param {Array} positions
 */
function renderHistoryTable(positions) {
  const tbody = document.getElementById('historyTable');
  if (!tbody) return;

  if (!positions || positions.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text3);">Sin posiciones cerradas</td></tr>';
    return;
  }

  tbody.innerHTML = '';
  positions.forEach(pos => {
    const pnl   = parseFloat(pos.result_pct || 0);
    const isPos = pnl >= 0;
    const tr    = document.createElement('tr');

    const cells = [
      { text: '#' + pos.id,                              style: 'color:var(--text3)' },
      { text: (pos.crypto || '').replace('USDT',''),     style: 'font-weight:700' },
      { text: '$' + parseFloat(pos.entry_price || 0).toFixed(2) },
      { text: '$' + parseFloat(pos.exit_price  || 0).toFixed(2) },
      {
        text:  (isPos ? '+' : '') + pnl.toFixed(2) + '%',
        style: 'font-weight:700;color:' + (isPos ? 'var(--accent)' : 'var(--red)')
      },
      { text: (pos.entry_time || '—'), style: 'color:var(--text3)' },
    ];

    cells.forEach(({ text, style }) => {
      const td = document.createElement('td');
      td.textContent = text;
      if (style) td.style.cssText = style;
      tr.appendChild(td);
    });

    tbody.appendChild(tr);
  });
}

/**
 * Renderiza lecciones aprendidas.
 * @param {Array} lessons
 */
function renderLessons(lessons) {
  const list = document.getElementById('lessonsList');
  if (!list) return;

  if (!lessons || lessons.length === 0) {
    list.innerHTML = '';
    list.appendChild(makeEmpty('🧠', 'Sin lecciones aún. Cierra posiciones para generarlas.'));
    return;
  }

  list.innerHTML = '';
  lessons.forEach(l => {
    const isWin = l.result === 'win';
    const pnl   = parseFloat(l.result_pct || 0);

    const div = document.createElement('div');
    div.className = 'lesson-item';

    const header = document.createElement('div');
    header.className = 'lesson-header';

    const emoji = document.createElement('span');
    emoji.textContent = isWin ? '✅' : '❌';

    const sym = document.createElement('div');
    sym.className = 'lesson-symbol';
    sym.textContent = (l.crypto || '').replace('USDT', '');

    const factor = document.createElement('span');
    factor.className = 'badge badge-blue';
    factor.textContent = l.dominant_factor || '';

    header.appendChild(emoji);
    header.appendChild(sym);
    header.appendChild(factor);

    const text = document.createElement('div');
    text.className = 'lesson-text';
    text.textContent = l.lesson_text || '';

    const meta = document.createElement('div');
    meta.className = 'lesson-meta';

    const pnlBadge = document.createElement('span');
    pnlBadge.className = 'badge ' + (isWin ? 'badge-green' : 'badge-red');
    pnlBadge.textContent = (isWin ? '+' : '') + pnl.toFixed(2) + '%';

    const dt = document.createElement('span');
    dt.textContent = (l.datetime || '').slice(0, 10);

    meta.appendChild(pnlBadge);
    meta.appendChild(dt);

    div.appendChild(header);
    div.appendChild(text);
    div.appendChild(meta);
    list.appendChild(div);
  });
}

/**
 * Renderiza errores del log.
 * @param {Array<string>} errors
 */
function renderErrors(errors) {
  const list = document.getElementById('errorsList');
  if (!list) return;

  if (!errors || errors.length === 0) {
    list.innerHTML = '';
    list.appendChild(makeEmpty('✓', 'Sin errores registrados'));
    return;
  }

  list.innerHTML = '';
  errors.forEach(e => {
    const div = document.createElement('div');
    div.className = 'error-line';
    div.textContent = e; // textContent — seguro
    list.appendChild(div);
  });
}

/* ── HELPERS ── */

/* ── INDICADOR DE ACCIÓN EN TOPBAR ── */

/**
 * Muestra el spinner en el topbar con un mensaje descriptivo.
 * Oculta el indicador de conexión mientras hay una acción activa.
 * @param {string} texto - Descripción de la acción en curso
 */
function showAction(texto) {
  const indicator  = document.getElementById('actionIndicator');
  const actionText = document.getElementById('actionText');

  if (actionText)  actionText.textContent = texto;
  if (indicator)   indicator.classList.add('visible');
}

/**
 * Oculta el spinner del topbar.
 */
function hideAction() {
  const indicator = document.getElementById('actionIndicator');
  if (indicator)  indicator.classList.remove('visible');
}

/**
 * Crea un elemento de estado vacío.
 * @param {string} icon
 * @param {string} text
 * @returns {HTMLElement}
 */
function makeEmpty(icon, text) {
  const div = document.createElement('div');
  div.className = 'empty';
  const i = document.createElement('span');
  i.className = 'empty-icon';
  i.textContent = icon;
  const t = document.createElement('span');
  t.textContent = text;
  div.appendChild(i);
  div.appendChild(t);
  return div;
}
