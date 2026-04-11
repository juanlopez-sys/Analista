/* ============================================================
   chat.js — Chat interactivo con Claude
   Sistema Analista Crypto
   ============================================================ */

'use strict';

// Historial de la conversación actual (máximo últimos 10 mensajes)
const chatHistory = [];

/**
 * Agrega un mensaje al chat visual.
 * @param {'user'|'assistant'} role
 * @param {string} text
 */
function addChatMessage(role, text) {
  const container = document.getElementById('chatContainer');
  if (!container) return;

  // Remover estado vacío si existe
  const empty = container.querySelector('.empty');
  if (empty) empty.remove();

  const time = new Date().toLocaleTimeString('es-CL', {
    hour: '2-digit', minute: '2-digit'
  });

  const msg = document.createElement('div');
  msg.className = `chat-msg ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';
  bubble.textContent = text; // textContent — seguro contra XSS

  const meta = document.createElement('div');
  meta.className = 'chat-meta';
  meta.textContent = (role === 'user' ? 'Tú' : 'Claude') + ' · ' + time;

  msg.appendChild(bubble);
  msg.appendChild(meta);
  container.appendChild(msg);

  // Scroll al final
  container.scrollTop = container.scrollHeight;
}

/**
 * Envía el mensaje del usuario a Claude.
 */
async function sendChat() {
  if (!rateLimit('chat', 1000)) return;

  const input = document.getElementById('chatInput');
  const btn   = document.getElementById('btnSendChat');
  if (!input || !btn) return;

  const rawMsg = input.value;
  const msg    = sanitizeInput(rawMsg, 2000);

  if (!msg) {
    toast('Escribe un mensaje primero', 'warning');
    return;
  }

  // Limpiar input y deshabilitar mientras espera
  input.value    = '';
  input.disabled = true;
  btn.disabled   = true;

  // Mostrar mensaje del usuario
  addChatMessage('user', msg);
  chatHistory.push({ role: 'user', content: msg });

  showAction('◷ Claude está pensando...');

  // Placeholder de carga
  const container = document.getElementById('chatContainer');
  const loading   = document.createElement('div');
  loading.className = 'chat-msg assistant';
  const loadBubble = document.createElement('div');
  loadBubble.className = 'chat-bubble';
  loadBubble.style.color = 'var(--text3)';
  loadBubble.textContent = '◌ Claude está pensando...';
  loading.appendChild(loadBubble);
  container.appendChild(loading);
  container.scrollTop = container.scrollHeight;

  try {
    const cryptoEl = document.getElementById('chatCrypto');
    const crypto   = cryptoEl ? cryptoEl.value : null;

    const res = await API.chat(
      msg,
      crypto || null,
      chatHistory.slice(-10)   // Solo los últimos 10 mensajes
    );

    loading.remove();

    const reply = res.response || 'Sin respuesta del servidor';
    addChatMessage('assistant', reply);
    chatHistory.push({ role: 'assistant', content: reply });

  } catch (e) {
    loading.remove();
    addChatMessage('assistant', 'Error: ' + String(e.message));
    toast(String(e.message), 'error');
  } finally {
    hideAction();
    input.disabled = false;
    btn.disabled   = false;
    input.focus();
  }
}

/**
 * Limpia el historial del chat visual y en memoria.
 */
function clearChat() {
  chatHistory.length = 0;
  const container = document.getElementById('chatContainer');
  if (!container) return;
  container.innerHTML = '';
  container.appendChild(makeEmpty('◷', 'Inicia una conversación con Claude'));
}
