import { Device } from "@twilio/voice-sdk";

let device = null;
let activeCall = null;
let currentToken = null;
let currentWorkspace = null;
let isMuted = false;
let isConnectingBridge = false; // Trava para evitar múltiplas conexões à ponte persistente
let bridgeReconnectTimeout = null;

// Cooldown para evitar loops de limpeza
let lastCallIdCooldown = null;
let lastLeadTimestampCooldown = 0;
const COOLDOWN_MS = 1800;

// Watchdog de estado de chamada
let callStateWatchdog = null;

// ==============================
// CONTROLE DE POPUP / CONFERENCE
// ==============================
let pendingConferenceData = null;
let currentPopupConferenceName = null;
let popupOpen = false;
let conferenceAnswerInProgress = false;
let dismissedConferences = new Set();
let pendingConferencePoller = null;
let operatorStatePoller = null;
let lastOperatorCallStatus = null;
let webphoneLastPopupOpenTime = 0;

// Rastreamento de estado da campanha para log em tempo real
let _lastLoggedCampaignLeadId = null;
let _lastLoggedCampaignStatus = null;

// Lead cujo popup foi dispensado manualmente durante a chamada (não reabre enquanto chamada ativa)
let _dismissedLeadId = null;

// Grace period: mantém popup aberto N segundos após lead desligar para classificar
const CLASSIFICATION_GRACE_SECONDS = 35;
let _graceActive = false;
let _graceTimer  = null;

function _startClassificationGrace() {
    if (_graceActive) return;
    _graceActive = true;
    let remaining = CLASSIFICATION_GRACE_SECONDS;
    window.dispatchEvent(new CustomEvent('nexdial:classification_grace', { detail: { seconds: remaining } }));
    _graceTimer = setInterval(() => {
        remaining--;
        window.dispatchEvent(new CustomEvent('nexdial:classification_grace', { detail: { seconds: remaining } }));
        if (remaining <= 0) _endClassificationGrace();
    }, 1000);
}

function _endClassificationGrace() {
    _graceActive = false;
    if (_graceTimer) { clearInterval(_graceTimer); _graceTimer = null; }
    window.dispatchEvent(new CustomEvent('nexdial:classification_grace', { detail: { seconds: 0 } }));
    if (popupOpen) hidePendingConferencePopup(true);
}

function _ts() {
    return new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function updateCampaignLog(data) {
    const leadId = data?.lead_id;
    const status = data?.status || '';
    const leadName  = data?.lead?.name  || '';
    const leadPhone = data?.lead?.phone || data?.phone_number || '';
    const label = leadName ? `${leadName}${leadPhone ? ' (' + leadPhone + ')' : ''}` : leadPhone || 'Lead';

    // Lead novo — reseta rastreamento
    if (leadId && leadId !== _lastLoggedCampaignLeadId) {
        _lastLoggedCampaignLeadId = leadId;
        _lastLoggedCampaignStatus = null;
    }

    if (!data?.has_call) {
        if (_lastLoggedCampaignStatus !== null && _lastLoggedCampaignStatus !== 'idle') {
            const msg = `[${_ts()}] 📴 Chamada encerrada`;
            log(msg);
            _hubLog(msg);
            _lastLoggedCampaignStatus = 'idle';
        }
        _updateCampaignStatusBox('idle', '');
        return;
    }

    if (status === _lastLoggedCampaignStatus) return;
    _lastLoggedCampaignStatus = status;

    const msgs = {
        'ringing_lead':           `[${_ts()}] 🔔 Discando ${label}...`,
        'answered_waiting_agent': `[${_ts()}] ✅ ${label} atendeu!`,
        'agent_joining':          `[${_ts()}] 🎙️ Conectando áudio com ${label}...`,
        'agent_joined':           `[${_ts()}] 🎙️ Em conversa com ${label}`,
        'machine_dropped':        `[${_ts()}] 🤖 Caixa postal detectada — pulando`,
        'no_answer':              `[${_ts()}] ❌ Sem resposta — ${label}`,
    };
    if (msgs[status]) {
        log(msgs[status]);
        _hubLog(msgs[status]);
    }

    _updateCampaignStatusBox(status, label);
}

function _hubLog(msg) {
    const box = document.getElementById('hubLogBox');
    if (!box) return;
    box.textContent = msg + '\n' + box.textContent;
}

function _updateCampaignStatusBox(status, label) {
    const box = document.getElementById('campaignStatusBox');
    if (!box) return;
    const icons = {
        'ringing_lead':           '🔔',
        'answered_waiting_agent': '✅',
        'agent_joining':          '🎙️',
        'agent_joined':           '🎙️',
        'machine_dropped':        '🤖',
        'no_answer':              '❌',
        'idle':                   '⏳',
    };
    const labels = {
        'ringing_lead':           `Discando ${label}`,
        'answered_waiting_agent': `Atendeu: ${label}`,
        'agent_joining':          `Conectando: ${label}`,
        'agent_joined':           `Em conversa: ${label}`,
        'machine_dropped':        'Caixa postal — pulando',
        'no_answer':              `Sem resposta: ${label}`,
        'idle':                   'Aguardando próximo lead...',
    };
    const colors = {
        'ringing_lead':           '#f59e0b',
        'answered_waiting_agent': '#22c55e',
        'agent_joining':          '#22c55e',
        'agent_joined':           '#22c55e',
        'machine_dropped':        '#94a3b8',
        'no_answer':              '#ef4444',
        'idle':                   '#475569',
    };
    box.textContent = `${icons[status] || '•'} ${labels[status] || status}`;
    box.style.borderColor = colors[status] || '#334155';
    box.style.color       = colors[status] || '#94a3b8';
}

// Verdadeiro somente após device.on("registered") — evita beep antes de iniciar webphone
let webphoneInitialized = false;
// Timestamp (ms) em que o device ficou registrado — usado para ignorar bipes no primeiro ciclo
let webphoneRegisteredAt = 0;

window.setPopupOpenTime = function() {
    webphoneLastPopupOpenTime = Date.now();
    // Força o resume do AudioContext em cada gesto de interação
    if (window.__nexdialAudioCtx && window.__nexdialAudioCtx.state === 'suspended') {
        window.__nexdialAudioCtx.resume();
    }
};

function dispatchIncomingCallEvent(data) {
    const event = new CustomEvent('nexdial:incoming_call', { detail: data });
    window.dispatchEvent(event);
}

function dispatchCallEndedEvent() {
    const event = new CustomEvent('nexdial:call_ended');
    window.dispatchEvent(event);
}

function el(id) {
  return document.getElementById(id);
}

// Retorna headers com Authorization Bearer lido do localStorage.
// Merge com quaisquer headers extras (ex: Content-Type).
function _authHeaders(extra = {}) {
  const token = localStorage.getItem("nexdial_token") || "";
  if (token) return { Authorization: `Bearer ${token}`, ...extra };
  return { ...extra };
}

function log(message) {
  const box = el("logBox");
  if (!box) return;
  const time = new Date().toLocaleTimeString("pt-BR");
  box.textContent = `[${time}] ${message}\n` + box.textContent;
  console.log(message);
}

function setDeviceStatus(message) {
  const node = el("deviceStatus");
  if (node) node.textContent = `Device: ${message}`;
}

function setCallStatus(message) {
  const node = el("callStatus");
  if (node) node.textContent = `Chamada: ${message}`;
}

function setOperatorStatusBox(message) {
  const node = el("operatorStatusBox");
  if (node) node.textContent = `Operador: ${message}`;
}

function getAgentId() {
  const fromDOM = el("agentId")?.value;
  if (fromDOM && fromDOM !== "0") {
     localStorage.setItem('agent_id', fromDOM);
     return parseInt(fromDOM, 10);
  }
  return parseInt(localStorage.getItem('agent_id') || "0", 10);
}

function getDialNumber() {
  return (el("dialNumber")?.value || "").trim();
}

function setDialNumber(value) {
  const node = el("dialNumber");
  if (node) node.value = value;
}

function sanitizePhone(phone) {
  return String(phone || "").replace(/[^\d*#+]/g, "").trim();
}

function pressKey(key) {
  setDialNumber((getDialNumber() || "") + key);
}

function backspaceNumber() {
  const current = getDialNumber();
  setDialNumber(current.slice(0, -1));
}

function clearNumber() {
  setDialNumber("");
}

function renderLeadPhones(phones) {
  const container = el("leadPhonesView");
  if (!container) return;

  container.innerHTML = "";

  if (!phones || !phones.length) {
    container.innerHTML = `<span class="muted">Nenhum telefone carregado</span>`;
    return;
  }

  phones.forEach((phone) => {
    const btn = document.createElement("button");
    btn.className = "lead-phone-btn";
    btn.textContent = phone;
    btn.onclick = () => {
      setDialNumber(phone);
      log(`Telefone do lead selecionado: ${phone}`);
    };
    container.appendChild(btn);
  });
}

function renderWorkspace(data) {
  currentWorkspace = data || null;

  const lead = data?.current_lead || null;
  const call = data?.current_call || null;
  const agent = data?.agent || null;

  if (el("leadIdView")) el("leadIdView").textContent = lead?.id ?? "-";
  if (el("leadNameView")) el("leadNameView").textContent = lead?.name ?? "-";
  if (el("leadCompanyView")) {
    el("leadCompanyView").textContent = lead
      ? `${lead.company_name || "-"} / ${lead.job_title || "-"}`
      : "-";
  }
  if (el("leadStatusView")) el("leadStatusView").textContent = lead?.status ?? "-";
  if (el("callIdView")) el("callIdView").textContent = call?.id ?? "-";

  renderLeadPhones(lead?.phones || []);

  if (agent?.status && el("agentStatus")) {
    el("agentStatus").value = agent.status;
    setOperatorStatusBox(agent.status);
  }
}

async function safeJson(response) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    throw new Error(
      text?.startsWith("<!doctype") || text?.startsWith("<html")
        ? "resposta HTML recebida em vez de JSON"
        : "resposta inválida do servidor"
    );
  }
  return await response.json();
}

// Referência global ao elemento <audio> remoto do Twilio SDK.
// O SDK cria este elemento via `new Audio()` — ele NÃO é adicionado ao DOM,
// então document.querySelectorAll("audio") nunca o encontra.
// Capturamos a referência no evento "audio" e mantemos aqui para os retries.
let _twilioRemoteAudioEl = null;

/**
 * Tenta garantir que um elemento <audio> específico esteja tocando,
 * usando o truque muted-first para contornar a política de autoplay do Chrome.
 * Verifica se srcObject está definido antes de tentar (pode não estar imediatamente).
 */
function _playAudioEl(el, attempt) {
  if (!el) return;
  attempt = attempt || 0;
  if (!el.srcObject && !el.src) {
    // srcObject ainda não foi definido pelo SDK — aguarda um pouco
    if (attempt < 10) {
      setTimeout(() => _playAudioEl(el, attempt + 1), 60);
    }
    return;
  }
  el.setAttribute("playsinline", "");
  el.volume = 1;
  el.muted = true;
  el.play()
    .then(() => { el.muted = false; })
    .catch(() => {
      // Retry muted-first: nunca tentar unmuted (falha autoplay policy)
      setTimeout(() => {
        el.muted = true;
        el.play()
          .then(() => { el.muted = false; })
          .catch(() => {});
      }, 400);
    });
}

/** Restaura AudioContext e tenta dar play em elementos <audio> (Twilio usa isso para o remoto).
 *  Inclui fallback com retry para elementos criados tardiamente pelo SDK Voice.
 */
async function resumeTwilioAudioPipeline() {
  // Tenta todos os AudioContexts conhecidos em paralelo
  const contexts = [
    typeof Device !== "undefined" ? Device.audioContext : null,
    device?.audio?.audioContext,
    window.__nexdialAudioCtx,
  ].filter(Boolean);

  await Promise.allSettled(
    contexts.map(ctx => ctx.state === "suspended" ? ctx.resume() : Promise.resolve())
  );

  const unlockAudioElements = () => {
    // ── Método 1: Elemento armazenado da referência direta do evento "audio" ──
    // O SDK cria o elemento fora do DOM — querySelectorAll nunca o encontra.
    // Este é o caminho mais confiável no Chrome (que usa setSinkId).
    if (_twilioRemoteAudioEl) {
      try {
        if (_twilioRemoteAudioEl.srcObject && _twilioRemoteAudioEl.paused) {
          _playAudioEl(_twilioRemoteAudioEl);
        }
      } catch (_) {}
    }

    // ── Método 2: Elementos <audio> no DOM (fallback para Firefox/outros) ──
    document.querySelectorAll("audio").forEach((el) => {
      // Ignora os áudios do nosso próprio sistema de alerta
      if (el.id === "incomingCallSound" || el.id === "notificationBeep") return;
      try {
        el.setAttribute("playsinline", "");
        el.volume = 1;
        // ── Muted-first: Chrome sempre permite autoplay mudo ──────────────────
        el.muted = true;
        el.play()
          .then(() => { el.muted = false; })
          .catch(() => {
            setTimeout(() => {
              el.muted = true;
              el.play()
                .then(() => { el.muted = false; })
                .catch(() => {});
            }, 400);
          });
      } catch (_) {}
    });
  };
  unlockAudioElements();
  return unlockAudioElements; // retorna para reuso no caller
}

async function prepareBrowserAudio() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
  } catch (err) {
    log(`Aviso: getUserMedia falhou (pode funcionar mesmo assim): ${err.message}`);
  }

  const AudioCtx = window.AudioContext || /** @type {any} */ (window)["webkitAudioContext"];
  if (AudioCtx) {
    try {
      window.__nexdialAudioCtx = window.__nexdialAudioCtx || new AudioCtx();
      if (window.__nexdialAudioCtx.state === "suspended") {
        await window.__nexdialAudioCtx.resume();
      }
    } catch (err) {
      log(`Aviso: AudioContext falhou: ${err.message}`);
    }
  }

  await resumeTwilioAudioPipeline();
  log("Áudio preparado no navegador.");
}

async function loadToken() {
  const agentId = getAgentId();
  if (!agentId) throw new Error("agent_id inválido");

  const response = await fetch(`/api/webphone/token/${agentId}`, {
    headers: _authHeaders(),
  });
  const data = await safeJson(response);

  if (!response.ok) {
    throw new Error(data.error || data.details || "erro ao carregar token");
  }

  currentToken = data.token?.trim();
  if (!currentToken) {
    throw new Error("token inválido retornado pelo backend");
  }

  log(`Token carregado com sucesso para o operador ${agentId}. Identity: ${data.identity}`);
  setDeviceStatus("token carregado");
  return data;
}

// Objeto simples — constraints aninhadas podem falhar em alguns browsers com o SDK
const DEFAULT_RTC_AUDIO = { audio: true };

function bindCallEvents(call, direction = "chamada") {
  call.on("audio", (remoteAudioEl) => {
    try {
      if (remoteAudioEl) {
        // CRÍTICO: o evento "audio" dispara ANTES de srcObject ser definido pelo SDK.
        // _playAudioEl aguarda (até 600ms) até srcObject estar disponível antes de play().
        _twilioRemoteAudioEl = remoteAudioEl;
        _playAudioEl(remoteAudioEl);
        log(`🔊 [${direction}] Elemento de áudio remoto capturado — play agendado.`);
      }
    } catch (e) {
      console.warn(e);
    }
  });

  call.on("accept", async () => {
    await resumeTwilioAudioPipeline();
    setCallStatus("em chamada");
    log(`${direction} conectada.`);
    startCallStateWatchdog();
    // NOTA: popup NÃO deve ser disparado aqui.
    // O gatilho de popup fica exclusivamente no pollPendingConference.
    // Disparar popup no 'accept' causava popup fantasma quando a Ponte
    // Persistente conectava antes do lead atender.
  });

  call.on("disconnect", () => {
    const isBridgeCall = direction.includes("ponte persistente");

    // Só nulifica activeCall se ainda aponta para ESTE call object.
    // Caso answerConference() tenha sobrescrito activeCall com outro call
    // antes deste disconnect chegar, não devemos apagar a referência ativa.
    if (activeCall === call) {
      activeCall = null;
      isMuted = false;
      setCallStatus("encerrada");
      clearCallStateWatchdog();
    }
    log(`${direction} encerrada.`);

    if (direction.includes("conference")) {
      hidePendingConferencePopup(true);
    }

    // ── AUTO-RECONNECT Persistent Bridge ───────────────────────────────
    if (isBridgeCall && webphoneInitialized) {
        log("⚠️ Ponte Persistente desconectada. Tentando reconectar em 3s...");
        if (bridgeReconnectTimeout) clearTimeout(bridgeReconnectTimeout);
        bridgeReconnectTimeout = setTimeout(() => {
            if (device && device.state === 'registered') {
                connectToPersistentBridge();
            }
        }, 3000);
    }
  });

  call.on("cancel", () => {
    if (activeCall === call) {
      activeCall = null;
      isMuted = false;
      setCallStatus("cancelada");
      clearCallStateWatchdog();
    }
    log(`${direction} cancelada.`);

    if (direction.includes("conference")) {
      hidePendingConferencePopup(true);
    }
  });

  call.on("reject", () => {
    if (activeCall === call) {
      activeCall = null;
      isMuted = false;
      setCallStatus("rejeitada");
      clearCallStateWatchdog();
    }
    log(`${direction} rejeitada.`);

    if (direction.includes("conference")) {
      hidePendingConferencePopup(true);
    }
  });

  call.on("error", (error) => {
    console.error(error);
    setCallStatus("erro");
    log(`Erro na ${direction}: ${error.message || JSON.stringify(error)}`);
    clearCallStateWatchdog();

    if (direction.includes("conference")) {
      hidePendingConferencePopup(false);
    }
  });

  call.on("ringing", () => {
    log(`${direction} tocando...`);
  });
}

function playNotificationBeep() {
  try {
    const AudioCtx = window.AudioContext || /** @type {any} */ (window)["webkitAudioContext"];
    if (!AudioCtx) return;
    const ctx = window.__nexdialAudioCtx || new AudioCtx();
    if (!window.__nexdialAudioCtx) window.__nexdialAudioCtx = ctx;
    if (ctx.state === "suspended") ctx.resume();

    // Um bipe curto e discreto — sinal visual é suficiente, áudio apenas complementar
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.12);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.12);
  } catch (e) {
    console.warn("Beep falhou:", e);
  }
}

function showPendingConferencePopup(data) {
  if (!data || !data.conference_name) return;

  const isNew = currentPopupConferenceName !== data.conference_name;

  pendingConferenceData = data;
  currentPopupConferenceName = data.conference_name;
  popupOpen = true;
  window.setPopupOpenTime();

  // O bipe agora é tocado explicitamente apenas quando a ligação é atendida
  // (controle movido para pollPendingConference).
  
  // Em vez de manipular o DOM aqui, disparamos o evento para o dashboard.html
  // que já tem toda a lógica de renderização completa (com campanha, notes, etc).
  data.webphone_connected = !!activeCall;
  dispatchIncomingCallEvent(data);
  log(`Aviso de conference ${data.conference_name} disparado para a interface.`);
}

function hidePendingConferencePopup(resetConference = false) {
  const dataToCleanup = pendingConferenceData;
  popupOpen = false;
  conferenceAnswerInProgress = false;
  pendingConferenceData = null;

  // Cancela grace period se o operador fechou manualmente antes do tempo
  if (_graceActive) {
      _graceActive = false;
      if (_graceTimer) { clearInterval(_graceTimer); _graceTimer = null; }
      window.dispatchEvent(new CustomEvent('nexdial:classification_grace', { detail: { seconds: 0 } }));
  }

  if (resetConference) {
    if (dataToCleanup?.call_id) {
      dismissedConferences.add(`call_${dataToCleanup.call_id}`);
    }

    // Cooldown para evitar re-abertura imediata da mesma chamada
    if (dataToCleanup) {
        lastCallIdCooldown = dataToCleanup.call_id;
        lastLeadTimestampCooldown = Date.now();
    }

    currentPopupConferenceName = null;
    dispatchCallEndedEvent();
  }
}

/**
 * Reset forçado do estado de chamada.
 */
function resetCallState() {
    conferenceAnswerInProgress = false;
    if (activeCall) {
        try { activeCall.disconnect(); } catch(e) {}
        activeCall = null;
    }
    isConnectingBridge = false;
    isMuted = false;
    
    // Resetar UI
    setCallStatus('ocioso');
    log('🔄 Estado de chamada resetado.');
    clearCallStateWatchdog();
}

function startCallStateWatchdog() {
    clearTimeout(callStateWatchdog);
    callStateWatchdog = setTimeout(() => {
        if (activeCall && activeCall.status() !== 'closed') {
            log('⚠️ Watchdog: chamada travada há 10min. Resetando estado...');
            resetCallState();
        }
    }, 10 * 60 * 1000); // 10 minutos
}

function clearCallStateWatchdog() {
    clearTimeout(callStateWatchdog);
}

async function answerPendingConference() {
  try {
    if (!device) throw new Error("webphone não iniciado");
    if (!pendingConferenceData?.conference_name) {
      throw new Error("nenhuma conference pendente encontrada");
    }

    // ── Persistent Bridge: áudio já está conectado via agent_bridge ────────
    // Quando audio_bridged=true o lead foi injetado na ponte pelo AMD — não
    // precisamos (nem devemos) criar novo device.connect(). O activeCall já é
    // a ponte. Apenas atualizamos o UI para mostrar que a chamada está ativa.
    if (pendingConferenceData.audio_bridged) {
      if (activeCall) {
        log(`✅ Áudio já está na Persistent Bridge — exibindo lead sem nova conexão WebRTC.`);
        setCallStatus("em chamada");
        hidePendingConferencePopup(false);
        return;
      }
      // Bridge desconectada (reconexão em andamento) — aguarda sem criar nova call
      log("⚠️ audio_bridged=true mas ponte desconectada — aguardando reconexão automática.");
      return;
    }

    // Proteção contra sobrescrever a Persistent Bridge quando ela está
    // conectada (open) OU ainda estabelecendo conexão (connecting/pending).
    if (activeCall) {
      const st = activeCall.status ? activeCall.status() : "";
      if (st !== "closed" && st !== "") {
        log(`Já existe uma chamada WebRTC ativa (status=${st}). Ignorando answerConference.`);
        return;
      }
    }

    conferenceAnswerInProgress = true;

    const conferenceName = pendingConferenceData.conference_name;
    const agentId = getAgentId();

    log(`Entrando na conference ${conferenceName}...`);
    setCallStatus("entrando na conference...");

    activeCall = await device.connect({
      params: {
        conference_name: conferenceName,
        conf: conferenceName,
        agent_id: String(agentId),
        aid: String(agentId),
      },
      rtcConstraints: DEFAULT_RTC_AUDIO,
    });

    try {
      const m = activeCall.customParameters;
      if (m && typeof m.entries === "function" && m.size) {
        log(`CustomParameters Twilio: ${JSON.stringify(Object.fromEntries(m.entries()))}`);
      }
    } catch (_) {}

    void resumeTwilioAudioPipeline();

    bindCallEvents(activeCall, "conference do discador");

    // ── Detecção de drop rápido (lead desligou logo após conectar) ────────────────
    let acceptedAt = 0;
    activeCall.on("accept", async () => {
      acceptedAt = Date.now();
      log(`Conference ${conferenceName} conectada.`);

      // Áudio Instantâneo: resume agressivo + 2 retries com delay
      const unlock = await resumeTwilioAudioPipeline();
      setTimeout(() => { resumeTwilioAudioPipeline(); }, 300);
      setTimeout(() => { resumeTwilioAudioPipeline(); }, 800);

      setCallStatus("em chamada");
      hidePendingConferencePopup(false);
    });

    activeCall.on("disconnect", () => {
      const sessionMs = acceptedAt ? Date.now() - acceptedAt : 0;
      if (acceptedAt && sessionMs < 3000) {
        // Chamada durou < 3s — lead desligou antes de o áudio estabilizar
        log(`❌ Lead desligou ${sessionMs < 500 ? 'imediatamente' : `após ${(sessionMs/1000).toFixed(1)}s`} — conference ${conferenceName} encerrada.`);
      } else {
        log(`Conference ${conferenceName} encerrada.`);
      }
      hidePendingConferencePopup(true);
    });

    activeCall.on("cancel", () => {
      log(`Conference ${conferenceName} cancelada.`);
      hidePendingConferencePopup(true);
    });

    activeCall.on("reject", () => {
      log(`Conference ${conferenceName} rejeitada.`);
      hidePendingConferencePopup(true);
    });

    activeCall.on("error", (error) => {
      log(`Erro na conference ${conferenceName}: ${error.message || error}`);
      hidePendingConferencePopup(false);
    });
  } catch (error) {
    console.error(error);
    conferenceAnswerInProgress = false;
    log(`Erro ao atender conference: ${error.message || error}`);
  }
}

/**
 * Deve ser chamado no clique do operador (mesmo gesto do Chrome para microfone + áudio).
 * Não dispare automaticamente pelo poller — sem gesto o WebRTC fica mudo dos dois lados.
 */
async function joinConferenceFromUserClick() {
  try {
    // Se o webphone não foi iniciado, inicia agora aproveitando o gesto do usuário
    if (!device) {
      log("⚠️ Webphone não iniciado. Iniciando agora...");
      await startWebphone();
      await new Promise(resolve => setTimeout(resolve, 2500));
    }

    // ── Pre-flight: verifica se a conference ainda está ativa antes de conectar ──
    // Evita o cenário: lead desligou → conference limpa → operador clica → cai
    if (pendingConferenceData?.conference_name) {
      try {
        const agentId = getAgentId();
        const chk = await fetch(`/api/twilio/pending-call/${agentId}`);
        const chkData = await chk.json();
        if (!chkData?.has_call) {
          log("❌ Lead já desligou — chamada não disponível.");
          hidePendingConferencePopup(true);
          return;
        }
      } catch (_) { /* continua mesmo se o check falhar */ }
    }

    // Resume contextos de áudio — pula getUserMedia se AudioContext já está rodando
    try {
      const ctxState = window.__nexdialAudioCtx?.state
                    || device?.audio?.audioContext?.state
                    || 'suspended';
      if (ctxState !== 'running') {
        // AudioContext suspenso — precisa de gesto para desbloquear
        await prepareBrowserAudio();
      } else {
        // Já desbloqueado, apenas garante resume
        await resumeTwilioAudioPipeline();
      }
    } catch (audioErr) {
      console.warn("audio resume:", audioErr.message);
      await resumeTwilioAudioPipeline();
    }

    await answerPendingConference();

    const wrap = document.getElementById("premiumConnectCallWrap");
    if (wrap) wrap.style.display = "none";
  } catch (e) {
    console.error(e);
    const msg = e.message || String(e);
    log(`❌ Erro ao conectar: ${msg}`);
    alert(`Erro ao conectar na chamada:\n${msg}\n\nVerifique se o webphone está iniciado e o microfone está permitido.`);
  }
}

async function dismissPendingConference() {
  log("Popup minimizado/fechado pelo operador.");
  // Marca esta chamada como dispensada: o popup não reabre enquanto a chamada ainda estiver ativa.
  // Quando o lead desligar (!has_call), o flag é limpo sem abrir grace period.
  _dismissedLeadId = pendingConferenceData?.call_id ?? null;
  hidePendingConferencePopup(false);
  
  // Apenas fecha o modal visualmente no dashboard
  if (window.closeIncomingCallPopup) {
      window.closeIncomingCallPopup();
  }
  
  // Resume áudio se necessário
  if (window.__nexdialAudioCtx && window.__nexdialAudioCtx.state === 'suspended') {
      window.__nexdialAudioCtx.resume();
  }
}

async function skipToNextPhone() {
  try {
    const agentId = getAgentId();
    const leadId = pendingConferenceData?.lead_id
                || currentWorkspace?.current_lead?.id;
    const campaignId = pendingConferenceData?.campaign_id
                    || currentWorkspace?.current_campaign?.id
                    || localStorage.getItem('current_campaign_id');

    if (!leadId) {
      log("Nenhum lead loaded para pular número");
      return;
    }

    log("Pular para próximo lead...");

    // Chamar API para pular número (agora com campaign_id para discador automático)
    const response = await fetch("/api/operator/workspace/skip_phone", {
      method: "POST",
      headers: _authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        agent_id: agentId,
        lead_id: leadId,
        campaign_id: campaignId ? parseInt(campaignId, 10) : null
      }),
    });
    
    const data = await safeJson(response);
    
    if (!response.ok) {
      throw new Error(data.error || "erro ao pular número");
    }
    
    log(`Número pulado: ${data.phone_tried || 'atual'}`);
    
    // Recarregar workspace para pegar próximo número
    await loadWorkspace();
    
    //Fecha popup
    hidePendingConferencePopup(false);
    if (window.closeIncomingCallPopup) {
      window.closeIncomingCallPopup();
    }
    
  } catch (error) {
    console.error(error);
    log(`Erro ao pular número: ${error.message}`);
  }
}

/**
 * Conecta à Ponte Persistente do agente usando action=persistent_bridge.
 * Esta função é EXCLUSIVA para conexão da ponte — não abre popup.
 * Funciona sem pendingConferenceData (conexão independente de campanha ativa).
 */
async function startPersistentBridge() {
    if (isConnectingBridge || !device) return;
    if (activeCall && activeCall.status && activeCall.status() !== 'closed') return;

    const agentId = getAgentId();
    if (!agentId) return;

    isConnectingBridge = true;
    log("🌉 Conectando à Ponte Persistente do operador...");
    try {
        const bridgeCall = await device.connect({
            params: {
                action:   "persistent_bridge",
                agent_id: String(agentId),
                aid:      String(agentId),
            },
            rtcConstraints: DEFAULT_RTC_AUDIO,
        });

        activeCall = bridgeCall;

        // ── CRÍTICO: handler de áudio remoto da Ponte Persistente ─────────────
        // O SDK dispara "audio" com o HTMLAudioElement MAS srcObject ainda não
        // está definido neste momento — o SDK define logo depois (assíncrono).
        // _playAudioEl() aguarda srcObject aparecer (até 600ms) antes de chamar
        // play() com muted-first, garantindo desbloqueio pelo autoplay do Chrome.
        bridgeCall.on("audio", (remoteAudioEl) => {
            try {
                if (remoteAudioEl) {
                    _twilioRemoteAudioEl = remoteAudioEl; // referência global para retries
                    _playAudioEl(remoteAudioEl);
                    log("🔊 [BRIDGE] Elemento de áudio remoto capturado — play agendado (muted-first).");
                }
            } catch(e) { console.warn("[BRIDGE-AUDIO]", e); }
        });

        bridgeCall.on("accept", async () => {
            await resumeTwilioAudioPipeline();
            // Retries: elemento de áudio pode ser criado APÓS o accept
            setTimeout(() => resumeTwilioAudioPipeline(), 300);
            setTimeout(() => resumeTwilioAudioPipeline(), 800);
            setTimeout(() => resumeTwilioAudioPipeline(), 2000);
            setCallStatus("ponte ativa — aguardando ligações...");
            log("✅ Ponte Persistente estabelecida. Pronto para receber leads.");
        });

        bridgeCall.on("disconnect", () => {
            if (activeCall === bridgeCall) {
                activeCall = null;
                isMuted = false;
                setCallStatus("ponte desconectada");
                clearCallStateWatchdog();
            }
            log("⚠️ Ponte Persistente desconectada. Reconectando em 3s...");
            if (webphoneInitialized) {
                if (bridgeReconnectTimeout) clearTimeout(bridgeReconnectTimeout);
                bridgeReconnectTimeout = setTimeout(() => {
                    if (device && device.state === 'registered') {
                        startPersistentBridge();
                    }
                }, 3000);
            }
        });

        bridgeCall.on("cancel",  () => { if (activeCall === bridgeCall) { activeCall = null; } });
        bridgeCall.on("reject",  () => { if (activeCall === bridgeCall) { activeCall = null; } });
        bridgeCall.on("error", (error) => {
            log(`❌ Erro na Ponte Persistente: ${error.message || error}`);
            if (activeCall === bridgeCall) activeCall = null;
        });

    } catch (e) {
        console.error('startPersistentBridge error:', e);
        log(`Erro ao estabelecer Ponte Persistente: ${e.message || e}`);
    } finally {
        isConnectingBridge = false;
    }
}

/**
 * Alias mantido para compatibilidade — agora delega para startPersistentBridge.
 * NÃO usa pendingConferenceData para evitar popup fantasma.
 */
async function connectToPersistentBridge() {
    await startPersistentBridge();
}


async function startWebphone() {
  try {
    await prepareBrowserAudio();

    if (!currentToken) {
      await loadToken();
    }

    if (!device) {
      device = new Device(currentToken, {
        logLevel: 1,
        codecPreferences: ["opus", "pcmu"],
        closeProtection: true,
        edge: ["sao-paulo", "ashburn"],  // Prioriza São Paulo para menor latência no Brasil
        allowIncomingWhileBusy: true,
        sounds: {
          outgoing: '', // Desabilita o som de "chamando" antigo (SDK 1.x)
          disconnect: '' // Desabilita o som de queda
        }
      });

      // Desabilita o som de "chamando" novo (SDK 2.x+)
      if (device.audio && typeof device.audio.outgoing === 'function') {
         device.audio.outgoing(false);
         device.audio.disconnect(false);
      }

      device.on("registering", () => {
        setDeviceStatus("registrando...");
        log("Registrando device...");
      });

      device.on("registered", async () => {
        webphoneInitialized = true;
        webphoneRegisteredAt = Date.now();
        setDeviceStatus("registrado");
        log("Twilio Device registrado e pronto para receber chamadas.");
        
        // ── PERSISTENT BRIDGE (Calix-style) ───────────────────────────
        // 1.5s de delay para garantir que o SIP esteja estável.
        // Usa startPersistentBridge() que conecta com action=persistent_bridge
        // sem abrir popup nem depender de pendingConferenceData.
        setTimeout(() => startPersistentBridge(), 1500);
      });

      device.on("unregistered", () => {
        setDeviceStatus("não registrado");
        log("Twilio Device desregistrado.");
      });

      device.on("error", (error) => {
        console.error(error);
        setDeviceStatus("erro");
        const code = error.code || (error.twilioError && error.twilioError.code) || '';
        log(`❌ Erro Twilio [${code}]: ${error.message || JSON.stringify(error)}`);
        // Códigos comuns:
        // 31208 = microfone negado | 31205 = DTLS falhou (sem áudio) | 31009 = transporte não encontrado
        if (code === 31208) log("🎤 PERMISSÃO DE MICROFONE NEGADA — verifique as permissões do navegador");
        if (code === 31205) log("🔇 DTLS handshake falhou — conexão sem áudio. Tente recarregar a página.");
        if (code === 31009) log("🌐 Sem conectividade com Twilio Edge. Verifique a internet/firewall.");
      });

      device.on("incoming", async (call) => {
        log("Chamada recebida no browser (ignorada) — o discador usa device.connect().");
        try {
          call.ignore();
        } catch (_) {
          try {
            call.reject();
          } catch (__) {}
        }
      });

      device.on("tokenWillExpire", async () => {
        try {
          log("Token perto de expirar. Renovando...");
          await loadToken();
          await device.updateToken(currentToken);
          log("Token atualizado com sucesso.");
        } catch (error) {
          console.error(error);
          log(`Erro ao renovar token: ${error.message || error}`);
        }
      });
    } else {
      await device.updateToken(currentToken);
      log("Device já existente. Token atualizado.");
    }

    // SDK v2: device.state é string ("registered"|"registering"|"unregistered"|"destroyed").
    // O check original usava typeof === "function" que retorna "unknown" no SDK v2 — nunca
    // entrava no early-return e chamava device.register() em loop sem efeito.
    const state = (typeof device.state === "function" ? device.state() : device.state) || "unknown";

    if (state === "registered") {
      log("Device já registrado.");
      setDeviceStatus("registrado");
      // Se a Ponte Persistente caiu (activeCall nulo), reconecta imediatamente.
      // Isso permite que o botão "Conectar Webphone" sirva de recuperação manual da ponte.
      if (!activeCall) {
        log("⚠️ Device registrado mas ponte offline — reconectando ponte...");
        setTimeout(() => startPersistentBridge(), 300);
      }
      return;
    }

    if (state === "registering") {
      log("Device já está registrando...");
      setDeviceStatus("registrando...");
      return;
    }

    setDeviceStatus("iniciando...");
    await device.register();
  } catch (error) {
    console.error(error);
    setDeviceStatus("falha ao iniciar");
    log(`Erro ao iniciar webphone: ${error.message || error}`);
  }
}

async function loadWorkspace() {
  try {
    const agentId = getAgentId();
    if (!agentId) throw new Error("agent_id inválido");

    const response = await fetch(`/api/operator/workspace/${agentId}`, {
      headers: _authHeaders(),
    });
    const data = await safeJson(response);

    if (!response.ok) {
      throw new Error(data.error || "erro ao carregar workspace");
    }

    renderWorkspace(data);
  } catch (error) {
    console.error(error);
    log(`Erro ao carregar workspace: ${error.message}`);
  }
}

async function setOperatorStatus() {
  try {
    const agentId = getAgentId();
    const status = el("agentStatus")?.value;

    const response = await fetch("/api/operator/status", {
      method: "POST",
      headers: _authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ agent_id: agentId, status }),
    });

    const data = await safeJson(response);

    if (!response.ok) {
      throw new Error(data.error || "erro ao atualizar status");
    }

    setOperatorStatusBox(status);
    log(`Status do operador atualizado para: ${status}`);
  } catch (error) {
    console.error(error);
    log(`Erro ao salvar status do operador: ${error.message}`);
  }
}

function copyLeadPrimaryPhone() {
  const primaryPhone = currentWorkspace?.current_lead?.primary_phone;
  if (!primaryPhone) {
    log("O lead atual não possui telefone principal.");
    return;
  }
  setDialNumber(primaryPhone);
  log(`Telefone principal carregado: ${primaryPhone}`);
}

async function makeCall() {
  try {
    if (!device) throw new Error("webphone não iniciado");

    const phoneNumber = sanitizePhone(getDialNumber());
    if (!phoneNumber) throw new Error("digite um número para ligar");

    const agentId = getAgentId();
    if (!agentId) throw new Error("operador não identificado");

    setCallStatus("discando...");
    log(`Iniciando chamada para ${phoneNumber}...`);

    const body = { to: phoneNumber, agent_id: String(agentId) };
    const leadId = currentWorkspace?.current_lead?.id;
    if (leadId) body.lead_id = String(leadId);

    const resp = await fetch("/api/twilio/manual-call", {
      method: "POST",
      headers: { "Content-Type": "application/json", ..._authHeaders() },
      body: JSON.stringify(body),
    });

    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "Erro ao ligar");

    log(`Chamada discada para ${phoneNumber}. Aguardando atendimento...`);
    setCallStatus("chamando...");
  } catch (error) {
    console.error(error);
    setCallStatus("falha");
    log(`Erro ao ligar: ${error.message}`);
  }
}

async function endPersistentBridge() {
  // Encerra a conferência via REST API — necessário porque endConferenceOnExit=False
  // no TwiML do agente. Sem esta chamada, a conferência ficaria viva indefinidamente.
  const agentId = getAgentId();
  if (!agentId) return;
  try {
    await fetch(`/api/twilio/end-bridge/${agentId}`, {
      method: "POST",
      headers: _authHeaders(),
    });
    log("Ponte Persistente encerrada via API.");
  } catch (e) {
    console.warn("Erro ao encerrar ponte via API:", e.message);
  }
}

function hangupCall() {
  try {
    if (!activeCall) {
      log("Nenhuma chamada ativa para desligar.");
      return;
    }
    activeCall.disconnect();
    activeCall = null;
    setCallStatus("encerrada");
    log("Chamada desligada manualmente.");
  } catch (error) {
    console.error(error);
    log(`Erro ao desligar chamada: ${error.message}`);
  }
}

function toggleMute() {
  try {
    if (!activeCall) {
      log("Nenhuma chamada ativa para mutar.");
      return;
    }
    isMuted = !isMuted;
    activeCall.mute(isMuted);
    log(isMuted ? "Microfone mutado." : "Microfone reativado.");
  } catch (error) {
    console.error(error);
    log(`Erro ao alterar mute: ${error.message}`);
  }
}

async function saveCRM() {
  try {
    const agentId = getAgentId();
    const leadId = currentWorkspace?.current_lead?.id;
    const callId = currentWorkspace?.current_call?.id || null;

    const payload = {
      agent_id: agentId,
      lead_id: leadId,
      call_id: callId,
      qualification: el("qualification")?.value || "",
      notes: el("crmNotes")?.value || "",
      follow_up: el("followUp")?.value || "",
    };

    const response = await fetch("/api/operator/workspace/save_crm", {
      method: "POST",
      headers: _authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });

    const data = await safeJson(response);

    if (!response.ok) {
      throw new Error(data.error || "erro ao salvar CRM");
    }

    log("Atendimento salvo com sucesso no CRM.");
    
    // Limpar formulário
    if (el("qualification")) el("qualification").value = "";
    if (el("crmNotes")) el("crmNotes").value = "";
    if (el("followUp")) el("followUp").value = "";
    
    await loadWorkspace();
  } catch (error) {
    console.error(error);
    log(`Erro ao salvar CRM: ${error.message}`);
  }
}

async function scheduleAndSave() {
  try {
      const agentId = getAgentId();
      const leadId = currentWorkspace?.current_lead?.id;
      const scheduledFor = el("scheduledFor")?.value;
      const campaignId = currentWorkspace?.current_call?.campaign_id;

      if (!scheduledFor) {
          alert("Selecione uma data e hora para o retorno.");
          return;
      }

      // Primeiro salva o CRM
      await saveCRM();

      // Depois agenda o retorno
      const response = await fetch("/api/operator/workspace/schedule_callback", {
          method: "POST",
          headers: _authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
              agent_id: agentId,
              lead_id: leadId,
              scheduled_for: scheduledFor,
              campaign_id: campaignId
          }),
      });

      const data = await safeJson(response);
      if (!response.ok) throw new Error(data.error || "Erro ao agendar");

      log(`Retorno agendado para ${scheduledFor}`);
      alert("Atendimento salvo e retorno agendado!");
      
      // Limpar campos
      if (el("scheduledFor")) el("scheduledFor").value = "";
      if (el("qualification")) el("qualification").value = "";
      if (el("crmNotes")) el("crmNotes").value = "";
      
  } catch (error) {
      console.error(error);
      log(`Erro no agendamento: ${error.message}`);
      alert(`Erro: ${error.message}`);
  }
}

async function pollOperatorState() {
  try {
    const agentId = getAgentId();
    if (!agentId) return;

    const response = await fetch(`/api/operator/workspace/${agentId}`, {
      headers: _authHeaders(),
    });
    const data = await safeJson(response);

    if (!response.ok) return;

    renderWorkspace(data);

    const currentCall = data?.current_call || null;

    if (!currentCall) {
      if (lastOperatorCallStatus !== "ocioso") {
        setCallStatus("ocioso");
        lastOperatorCallStatus = "ocioso";
      }
      return;
    }

    const status = currentCall.status || "desconhecido";
    const isInitialLoad = (lastOperatorCallStatus === undefined);

    if (lastOperatorCallStatus === status) {
      return;
    }

    lastOperatorCallStatus = status;
    setCallStatus(status);

    // Evita poluir o log visual se for a carga inicial da página
    if (!isInitialLoad) {
      if (status === "completed") {
        log("Chamada finalizada.");
      } else if (status === "failed") {
        log("Chamada falhou.");
      } else if (status === "busy") {
        log("Telefone ocupado.");
      } else if (status === "no-answer" || status === "no_answer") {
        log("Sem resposta.");
      } else if (status === "canceled") {
        log("Chamada cancelada.");
      } else if (status === "ringing") {
        log("Telefone tocando...");
      } else if (status === "in-progress" || status === "answered" || status === "agent_joined") {
        log("Chamada em andamento.");
      }
    }
  } catch (error) {
    console.error(error);
  }
}

async function pollPendingConference() {
  try {
    const agentId = getAgentId();
    if (!agentId) return;

    const response = await fetch(`/api/twilio/pending-call/${agentId}`);
    const data = await safeJson(response);

    if (!response.ok) return;

    // Bug #2: Loop Infinito "Aguardando ciclo de limpeza"
    // Só aguardar se o cooldown ainda está ativo E a chamada atual é a mesma que saiu
    if (!popupOpen && !pendingConferenceData && lastCallIdCooldown && Date.now() - lastLeadTimestampCooldown < COOLDOWN_MS) {
        const currentCallId = data?.call_id || data?.db_call_id;
        if (!currentCallId || currentCallId === lastCallIdCooldown) {
            // log(`⏳ Aguardando ciclo de limpeza...`);
            return;
        }
        // Chamada diferente chegou — resetar cooldown e deixar passar
        lastCallIdCooldown = null;
        lastLeadTimestampCooldown = 0;
    }

    // WATCHDOG — Ponte caiu mas bridge não está reconectando automaticamente
    // Só dispara se NENHUM lead está ativo E não há popup de conferência aberto
    // CRÍTICO: Se o popup está aberto ou há uma resposta em andamento, NÃO reconectar
    const watchdogLeadId = data?.lead_id ?? data?.lead?.id ?? null;
    const hasActiveConference = popupOpen || conferenceAnswerInProgress || data?.status === 'answered_waiting_agent';
    if (!activeCall && !isConnectingBridge && device && !watchdogLeadId && !hasActiveConference) {
        // Bridge ociosa e desconectada — reconectar silenciosamente
        log("🔌 [WATCHDOG] Ponte ociosa desconectada. Reconectando...");
        startPersistentBridge();
    }

    // 1. Verificação de chamada finalizada (has_call = false)
    if (!data?.has_call) {
      if (_dismissedLeadId !== null) {
          // Operador já dispensou o popup durante a chamada: não abre grace, apenas limpa
          _dismissedLeadId = null;
      } else if (popupOpen && !_graceActive) {
          // Popup ainda estava aberto: inicia grace period para classificar
          conferenceAnswerInProgress = false;
          log(`📴 Lead desligou — ${CLASSIFICATION_GRACE_SECONDS}s para classificar`);
          _startClassificationGrace();
      }
      updateCampaignLog(data);
      return;
    }

    // Novo lead chegou durante grace period: cancela grace e deixa popup atualizar
    if (_graceActive) {
        _graceActive = false;
        if (_graceTimer) { clearInterval(_graceTimer); _graceTimer = null; }
        window.dispatchEvent(new CustomEvent('nexdial:classification_grace', { detail: { seconds: 0 } }));
    }

    // 2. Verificação de Popup (show_popup = true ou status crítico)
    if (data.show_popup || data.status === 'answered_waiting_agent') {
      const conferenceName = data.conference_name;
      const leadData = data.lead || {};

      // DEBUG: Logar dados recebidos
      console.log('[POPUP-DEBUG] show_popup:', data.show_popup, 'status:', data.status, 'lead:', leadData.name, 'conf:', conferenceName);

      const currentCallId = data?.call_id || data?.db_call_id;
      if (currentCallId && dismissedConferences.has(`call_${currentCallId}`)) {
        console.log('[POPUP-DEBUG] Chamada', currentCallId, 'foi dispensada anteriormente — ignorando');
        return;
      }

      // Operador fechou popup durante chamada ativa: não reabre enquanto for a mesma chamada
      if (currentCallId && currentCallId === _dismissedLeadId) {
        return;
      }
      // Nova chamada chegou: limpa o flag de dispensado
      if (currentCallId && currentCallId !== _dismissedLeadId) {
        _dismissedLeadId = null;
      }

      const isNewForPopup = currentPopupConferenceName !== conferenceName;
      const statusChanged = pendingConferenceData?.status !== data.status;
      
      // Normalização para manter compatibilidade com outras partes do sistema
      pendingConferenceData = {
          ...data,
          lead_id: leadData.id || data.lead_id,
          lead_name: leadData.name,
          phone_number: leadData.phone,
          campaign_id: data.campaign_id || leadData.campaign_id
      };

      // 🔥 DISPARO CRÍTICO: Se mudou para answered_waiting_agent, forçamos o popup!
      if (isNewForPopup || !popupOpen || (statusChanged && data.status === 'answered_waiting_agent')) {
        log(`🔥 [POPUP] Disparando popup para o lead: ${leadData.name || 'Lead'} (Status: ${data.status})`);
        showPendingConferencePopup(pendingConferenceData);
        
        // Persistent Bridge: áudio está na sala — apenas desbloqueia o áudio
        // NÃO tenta reconectar se já houver bridge (conexão via TwiML)
        if (data.audio_bridged) {
          log("🔊 audio_bridged=true — desbloqueando áudio...");
          resumeTwilioAudioPipeline();
        }

        if (!data.amd_uncertain && (isNewForPopup || !popupOpen)) {
          playNotificationBeep();
        }
      } else if (statusChanged && popupOpen) {
          // Se o status mudou mas o popup já está aberto, apenas atualizamos os dados na UI
          log(`ℹ️ [POPUP] Atualizando status na UI: ${data.status}`);
          dispatchIncomingCallEvent(pendingConferenceData);
      }
    } else {
      // has_call=true mas show_popup=false (ainda ringando ou awaiting AMD)
      // Se o popup estava aberto e o backend diz para não mostrar mais (show_popup=false), fechamos para evitar fantasmas.
      if (popupOpen && !conferenceAnswerInProgress) {
          log("📴 Fechamento de segurança: show_popup=false detectado no poller.");
          hidePendingConferencePopup(true);
      }
      pendingConferenceData = data;
    }

    // ── MANUTENÇÃO CONTÍNUA DO ÁUDIO DA PONTE PERSISTENTE ────────────────────
    if (data.has_call && data.audio_bridged && activeCall) {
        resumeTwilioAudioPipeline();
    }

    updateCampaignLog(data);

  } catch (error) {
    console.error("Erro no polling:", error);
    log(`Erro ao consultar pending conference: ${error.message || error}`);
  }
}

function startPollers() {
  if (!operatorStatePoller) {
    operatorStatePoller = setInterval(async () => {
      await pollOperatorState();
    }, 3000);
  }

  if (!pendingConferencePoller) {
    // FIX 2: Tempo reduzido de 2000ms para 800ms para conexão mais rápida
    pendingConferencePoller = setInterval(async () => {
      await pollPendingConference();
    }, 800);
  }
}

window.loadToken = loadToken;
window.startWebphone = startWebphone;
window.setOperatorStatus = setOperatorStatus;
window.loadWorkspace = loadWorkspace;
window.pressKey = pressKey;
window.backspaceNumber = backspaceNumber;
window.clearNumber = clearNumber;
window.makeCall = makeCall;
window.hangupCall = hangupCall;
window.toggleMute = toggleMute;
window.copyLeadPrimaryPhone = copyLeadPrimaryPhone;
window.saveCRM = saveCRM;
window.scheduleAndSave = scheduleAndSave;
window.answerPendingConference = answerPendingConference;
window.joinConferenceFromUserClick = joinConferenceFromUserClick;
window.dismissPendingConference = dismissPendingConference;
window.resumeTwilioAudioPipeline = resumeTwilioAudioPipeline;
window.startPersistentBridge = startPersistentBridge;
window.skipToNextPhone = skipToNextPhone;

// ==============================
// PREMIUM CRM INTEGRATION
// ==============================

window.savePremiumCRM = async function() {
    const qualification = document.getElementById('premiumQualification')?.value;
    const notes = document.getElementById('premiumNotes')?.value || '';
    const stageId = document.getElementById('premiumStageId')?.value || null;

    // Get IDs from pending data OR current workspace
    const leadId = pendingConferenceData?.lead_id || (currentWorkspace?.current_lead ? currentWorkspace.current_lead.id : null);
    const callId = pendingConferenceData?.call_id || (currentWorkspace?.current_call ? currentWorkspace.current_call.id : null);
    // agent_id: prioriza DOM > pendingConferenceData > localStorage
    const agentId = getAgentId()
        || pendingConferenceData?.agent_id
        || parseInt(localStorage.getItem('agent_id') || '0', 10)
        || null;

    if (!leadId) {
        log("❌ Erro: Não foi possível identificar o lead para salvar o CRM.");
        return;
    }
    // agent_id é opcional agora (backend resolve pelo JWT)

    try {
        log(`💾 Salvando atendimento para o lead #${leadId}...`);

        const payload = {
            agent_id:      agentId,
            lead_id:       leadId,
            call_id:       callId,
            disposition:   qualification,
            notes:         notes,
        };
        if (stageId) payload.stage_id = parseInt(stageId, 10);

        const response = await fetch('/api/operator/workspace/save_crm', {
            method: 'POST',
            headers: _authHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload)
        });

        const data = await safeJson(response);
        if (!response.ok) throw new Error(data.error || "Falha ao salvar CRM");

        log("✅ CRM salvo com sucesso!" + (data.deal_moved ? ` Deal movido para: ${data.deal_moved.stage}` : ''));

        // Reset fields
        if (document.getElementById('premiumQualification')) document.getElementById('premiumQualification').value = "";
        if (document.getElementById('premiumNotes')) document.getElementById('premiumNotes').value = "";
        if (document.getElementById('premiumStageId')) document.getElementById('premiumStageId').value = "";

        // NOVO COMPORTAMENTO: Desligar e Próximo
        // 1. Encerrar a ligação
        try {
            const confName = pendingConferenceData?.conference_name || (typeof currentPopupConferenceName !== 'undefined' ? currentPopupConferenceName : null);
            if (confName) {
                await fetch('/api/dialer/hangup-lead', {
                    method: 'POST',
                    headers: _authHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify({ conference_name: confName, agent_id: agentId })
                });
            }
        } catch (e) {
            console.error("Erro ao desligar chamada no Desligar e Próximo:", e);
        }

        // 2. Fechar o popup
        if (typeof window.dismissPendingConference === 'function') {
            window.dismissPendingConference();
        }

        // 3. Avançar automaticamente
        const advanceAction = data?.advance_action;
        
        if (advanceAction === "next_phone") {
            // Cx Postal / Não Atendeu / Inválido → próximo NÚMERO do mesmo lead
            log("📱 Avançando para próximo número do mesmo lead...");
            if (typeof window.skipToNextPhone === 'function') {
                await window.skipToNextPhone();
            } else if (typeof window.dialerOverlaySkipPhone === 'function') {
                await window.dialerOverlaySkipPhone();
            }
        } else {
            // Avançar para o próximo lead
            log("🚀 Avançando para o próximo lead da lista...");
            if (typeof window.dialerOverlayNext === 'function') {
                await window.dialerOverlayNext();
            } else {
                log("⚠️ Função dialerOverlayNext não encontrada para avançar.");
            }
        }

    } catch (err) {
        log(`❌ Erro no CRM: ${err.message}`);
        alert("Erro ao salvar: " + err.message);
    }
};

window.addEventListener("load", async () => {
  log("Tela de operação carregada.");
  setDeviceStatus("não iniciado");
  setCallStatus("ocioso");
  setOperatorStatusBox("offline");

  try {
    await loadWorkspace();
    await loadToken();
    log("Token carregado. Clique em 'Iniciar webphone' para registrar o device.");
  } catch (e) {
    console.error(e);
    log(`Erro na inicialização da operação: ${e.message}`);
  }

  startPollers();
});

// Desbloqueio global de áudio ao clicar em qualquer lugar da tela
document.addEventListener("mousedown", () => {
    if (typeof resumeTwilioAudioPipeline === 'function') {
        void resumeTwilioAudioPipeline();
    }
}, { once: false });

async function testBrowserAudio() {
    log("🔊 Iniciando teste de áudio local...");
    try {
        await resumeTwilioAudioPipeline();
        
        // Toca um bipe de 440Hz por 500ms usando WebAudio
        const ctx = window.__nexdialAudioCtx || new (window.AudioContext || window.webkitAudioContext)();
        if (ctx.state === 'suspended') await ctx.resume();
        
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        
        osc.frequency.value = 440;
        gain.gain.value = 0.1;
        
        osc.start();
        setTimeout(() => {
            osc.stop();
            log("✅ Teste de áudio concluído. Se você ouviu o bipe, o som do navegador está OK.");
        }, 500);
    } catch (e) {
        log(`❌ Falha no teste de áudio: ${e.message}`);
    }
}

// ── Encerramento intencional da ponte quando o operador fecha o browser ──────
// sendBeacon garante que o request seja enviado mesmo durante beforeunload.
window.addEventListener("beforeunload", () => {
  const agentId = getAgentId();
  if (agentId && webphoneInitialized) {
    navigator.sendBeacon(`/api/twilio/end-bridge/${agentId}`);
  }
});

// Exportações para o Dashboard
window.getAgentId = getAgentId;
window.connectToPersistentBridge = connectToPersistentBridge;
window.endPersistentBridge = endPersistentBridge;