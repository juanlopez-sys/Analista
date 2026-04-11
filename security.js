/* ============================================================
   security.js — Sanitización, validación y protecciones
   Sistema Analista Crypto
   ============================================================ */

'use strict';

/**
 * Sanitiza texto para prevenir XSS antes de insertar en el DOM.
 * Escapa los caracteres especiales HTML.
 * @param {*} str - Valor a sanitizar
 * @returns {string} Texto seguro para insertar en HTML
 */
function sanitize(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/`/g, '&#96;');
}

/**
 * Limpia un input de texto libre eliminando caracteres peligrosos.
 * Úsalo antes de enviar strings al backend.
 * @param {string} val - Texto del usuario
 * @param {number} maxLen - Longitud máxima permitida
 * @returns {string} Texto limpio
 */
function sanitizeInput(val, maxLen = 2000) {
  return String(val)
    .replace(/[<>"'`\\]/g, '')
    .trim()
    .slice(0, maxLen);
}

/**
 * Valida que un valor sea un número dentro de un rango.
 * @param {*} val - Valor a validar
 * @param {number} [min] - Valor mínimo permitido
 * @param {number} [max] - Valor máximo permitido
 * @returns {number|null} El número si es válido, null si no
 */
function validateNumber(val, min, max) {
  const n = parseFloat(val);
  if (isNaN(n) || !isFinite(n)) return null;
  if (min !== undefined && n < min) return null;
  if (max !== undefined && n > max) return null;
  return n;
}

/**
 * Valida que un string no esté vacío y tenga longitud razonable.
 * @param {string} val
 * @param {number} maxLen
 * @returns {string|null}
 */
function validateString(val, maxLen = 500) {
  const s = String(val || '').trim();
  if (!s) return null;
  if (s.length > maxLen) return null;
  return s;
}

/**
 * Valida formato de fecha YYYY-MM-DD.
 * @param {string} val
 * @returns {string|null}
 */
function validateDate(val) {
  if (!val) return null;
  const match = /^\d{4}-\d{2}-\d{2}$/.test(val);
  if (!match) return null;
  const d = new Date(val);
  if (isNaN(d.getTime())) return null;
  return val;
}

/**
 * Valida formato de hora HH:MM.
 * @param {string} val
 * @returns {string|null}
 */
function validateTime(val) {
  if (!val) return null;
  const match = /^([01]?\d|2[0-3]):[0-5]\d$/.test(val);
  return match ? val : null;
}

/**
 * Valida que un símbolo de crypto sea de la lista permitida.
 * @param {string} val
 * @returns {string|null}
 */
function validateCrypto(val) {
  if (!val) return null;
  const allowed = Object.keys(window.CRYPTOS || {});
  return allowed.includes(val) ? val : null;
}

/* ── RATE LIMITING ── */
const _rateLimits = {};

/**
 * Controla que una acción no se ejecute más de una vez
 * en el intervalo indicado (ms).
 * @param {string} key - Identificador de la acción
 * @param {number} ms - Milisegundos de cooldown
 * @returns {boolean} true si puede ejecutar, false si debe esperar
 */
function rateLimit(key, ms = 2000) {
  const now = Date.now();
  if (_rateLimits[key] && now - _rateLimits[key] < ms) return false;
  _rateLimits[key] = now;
  return true;
}

/**
 * Resetea el rate limit de una acción específica.
 * @param {string} key
 */
function resetRateLimit(key) {
  delete _rateLimits[key];
}
