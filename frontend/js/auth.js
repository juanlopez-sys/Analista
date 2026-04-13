/* ============================================================
   auth.js — Autenticación con Supabase Auth
   Login con email/password, gestión de sesión y token JWT
   ============================================================ */

'use strict';

// ── Cliente Supabase ─────────────────────────────────────────
// Estos valores se inyectan en build time igual que BACKEND_URL.
// En local los lees desde window.ENV (definido en env.js).
const SUPABASE_URL    = (() => {
  if (window.__ENV__?.SUPABASE_URL) return window.__ENV__.SUPABASE_URL;
  const v = '__SUPABASE_URL__';
  return v.startsWith('__') ? '' : v;
})();

const SUPABASE_ANON_KEY = (() => {
  if (window.__ENV__?.SUPABASE_ANON_KEY) return window.__ENV__.SUPABASE_ANON_KEY;
  const v = '__SUPABASE_ANON_KEY__';
  return v.startsWith('__') ? '' : v;
})();

// Cliente Supabase (cargado via CDN en index.html)
let _supabase = null;

function getSupabaseClient() {
  if (_supabase) return _supabase;
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    console.error('Supabase no configurado — revisa las variables de entorno');
    return null;
  }
  _supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  return _supabase;
}

// ── Token activo (se actualiza al hacer login/refresh) ───────
let _currentToken = null;

/**
 * Retorna el JWT activo para enviarlo al backend.
 * @returns {string|null}
 */
function getToken() {
  return _currentToken;
}

// ============================================================
// LOGIN
// ============================================================

/**
 * Intenta hacer login con email y password.
 * @param {string} email
 * @param {string} password
 * @returns {Promise<{ok: boolean, error?: string}>}
 */
async function login(email, password) {
  const sb = getSupabaseClient();
  if (!sb) return { ok: false, error: 'Error de configuración — contacta al administrador' };

  const { data, error } = await sb.auth.signInWithPassword({ email, password });

  if (error) {
    // Mensajes amigables en español
    const msgs = {
      'Invalid login credentials': 'Email o contraseña incorrectos',
      'Email not confirmed':        'Debes confirmar tu email primero',
      'Too many requests':          'Demasiados intentos — espera unos minutos',
    };
    return { ok: false, error: msgs[error.message] || 'Error al iniciar sesión' };
  }

  _currentToken = data.session?.access_token || null;
  return { ok: true, user: data.user };
}

// ============================================================
// LOGOUT
// ============================================================

async function logout() {
  const sb = getSupabaseClient();
  if (sb) await sb.auth.signOut();
  _currentToken = null;
  showLoginScreen();
}

// ============================================================
// VERIFICAR SESIÓN AL ARRANCAR
// ============================================================

/**
 * Verifica si hay una sesión activa al cargar la página.
 * Supabase guarda la sesión en localStorage automáticamente.
 * @returns {Promise<boolean>}
 */
async function checkExistingSession() {
  const sb = getSupabaseClient();
  if (!sb) return false;

  const { data: { session } } = await sb.auth.getSession();

  if (session) {
    _currentToken = session.access_token;

    // Escuchar cambios de sesión (expiración, refresh automático)
    sb.auth.onAuthStateChange((event, newSession) => {
      if (event === 'SIGNED_OUT' || !newSession) {
        _currentToken = null;
        showLoginScreen();
      } else if (newSession) {
        _currentToken = newSession.access_token;
      }
    });

    return true;
  }

  return false;
}

// ============================================================
// UI — PANTALLA DE LOGIN
// ============================================================

function showLoginScreen() {
  document.getElementById('loginScreen').classList.remove('hidden');
  document.getElementById('appRoot').classList.add('hidden');
  const emailEl = document.getElementById('loginEmail');
  const passEl  = document.getElementById('loginPassword');
  if (emailEl) emailEl.value = '';
  if (passEl)  passEl.value  = '';
  clearLoginError();
}

function showAppScreen() {
  document.getElementById('loginScreen').classList.add('hidden');
  document.getElementById('appRoot').classList.remove('hidden');
}

function showLoginError(msg) {
  const el = document.getElementById('loginError');
  if (el) { el.textContent = msg; el.classList.remove('hidden'); }
}

function clearLoginError() {
  const el = document.getElementById('loginError');
  if (el) { el.textContent = ''; el.classList.add('hidden'); }
}

function setLoginLoading(loading) {
  const btn     = document.getElementById('btnLogin');
  const spinner = document.getElementById('loginSpinner');
  if (btn) btn.disabled = loading;
  if (spinner) spinner.classList.toggle('hidden', !loading);
}

// ============================================================
// HANDLER DEL FORMULARIO
// ============================================================

async function handleLogin() {
  clearLoginError();

  const email    = document.getElementById('loginEmail')?.value.trim();
  const password = document.getElementById('loginPassword')?.value;

  if (!email || !password) {
    showLoginError('Completa todos los campos');
    return;
  }

  setLoginLoading(true);

  const result = await login(email, password);

  setLoginLoading(false);

  if (!result.ok) {
    showLoginError(result.error);
    return;
  }

  // Login exitoso — mostrar la app
  showAppScreen();

  // Inicializar la app (definido en main.js)
  if (typeof init === 'function') init();
}

// ============================================================
// INICIALIZACIÓN
// ============================================================

document.addEventListener('DOMContentLoaded', async () => {
  // Enter en el form de login
  document.getElementById('loginPassword')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') handleLogin();
  });
  document.getElementById('loginEmail')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') handleLogin();
  });
  document.getElementById('btnLogin')?.addEventListener('click', handleLogin);
  document.getElementById('btnLogout')?.addEventListener('click', logout);

  // Verificar sesión existente
  const hasSession = await checkExistingSession();

  if (hasSession) {
    showAppScreen();
    if (typeof init === 'function') init();
  } else {
    showLoginScreen();
  }
});
