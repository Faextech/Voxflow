/* VoxFlow Enterprise — seções embutidas no dashboard /app */
(function () {
  'use strict';

  const WEBHOOK_EVENTS = [
    'lead.created', 'lead.updated', 'deal.created', 'deal.stage_changed',
    'call.completed', 'whatsapp.message.received', 'whatsapp.message.sent',
  ];

  const ENT_SECTIONS = new Set([
    'inbox', 'integrations', 'accounts', 'contacts', 'tags', 'custom-fields',
    'webhooks', 'api-key', 'invitations',
  ]);

  let me = null;
  let inboxPoll = null;
  let selectedConvId = null;
  let currentSection = null;
  let inboxConversations = [];
  let inboxFilter = 'all';
  let inboxSearch = '';
  let inboxDetailsOpen = true;
  let inboxConvCache = {};

  function mountEl(page) {
    return document.getElementById('ent-mount-' + page);
  }

  async function v1(path, opts = {}) {
    const method = (opts.method || 'GET').toUpperCase();
    const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
    const fetchOpts = { method, credentials: 'include', headers };
    if (opts.body !== undefined) fetchOpts.body = JSON.stringify(opts.body);

    let r;
    if (typeof window.authFetch === 'function') {
      r = await window.authFetch('/api/v1' + path, fetchOpts);
    } else {
      const token = localStorage.getItem('voxflow_token') || localStorage.getItem('token') || '';
      fetchOpts.headers.Authorization = 'Bearer ' + token;
      r = await fetch('/api/v1' + path, fetchOpts);
    }
    if (r.status === 401) { window.location.href = '/login'; throw new Error('Sessão expirada'); }
    if (r.status === 204) return null;
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.message || d.error || 'Erro na requisição');
    return d;
  }

  function toast(msg, type = 'success') {
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  function esc(s) {
    if (s == null) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
  }

  function fmtDate(d) {
    if (!d) return '—';
    try { return new Date(d).toLocaleString('pt-BR'); } catch { return d; }
  }

  function fmtRelative(d) {
    if (!d) return '';
    try {
      const dt = new Date(d);
      const diff = Date.now() - dt.getTime();
      const mins = Math.floor(diff / 60000);
      if (mins < 1) return 'agora';
      if (mins < 60) return `${mins}min`;
      const hrs = Math.floor(mins / 60);
      if (hrs < 24) return `${hrs}h`;
      const days = Math.floor(hrs / 24);
      if (days < 7) return `${days}d`;
      return dt.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
    } catch { return ''; }
  }

  function avatarInitials(name, phone) {
    const n = (name || phone || '?').trim();
    if (!n) return '?';
    const parts = n.replace(/[^a-zA-ZÀ-ÿ0-9\s]/g, ' ').split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return n.substring(0, 2).toUpperCase();
  }

  function inboxStatusLabel(status) {
    const s = (status || 'open').toLowerCase();
    if (['resolved', 'closed', 'archived'].includes(s)) return 'Resolvida';
    if (['pending', 'waiting'].includes(s)) return 'Aguardando';
    return 'Aberta';
  }

  function filterInboxList(list) {
    const q = inboxSearch.trim().toLowerCase();
    return list.filter(c => {
      if (inboxFilter === 'unread' && !(c.unread_count > 0)) return false;
      if (inboxFilter === 'waiting') {
        const s = (c.status || '').toLowerCase();
        if (!['open', 'pending', 'waiting', 'active'].includes(s)) return false;
      }
      if (inboxFilter === 'resolved') {
        const s = (c.status || '').toLowerCase();
        if (!['resolved', 'closed', 'archived'].includes(s)) return false;
      }
      if (q) {
        const hay = `${c.contact_name || ''} ${c.contact_phone || ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  function getInboxNotes(id) {
    try { return localStorage.getItem('vox_inbox_notes_' + id) || ''; } catch { return ''; }
  }

  function saveInboxNotes(id, text) {
    try { localStorage.setItem('vox_inbox_notes_' + id, text); } catch { /* ignore */ }
  }

  function badge(status) {
    const map = {
      active: 'badge-green', connected: 'badge-green', ok: 'badge-green',
      pending: 'badge-yellow', draft: 'badge-gray',
      error: 'badge-red', failed: 'badge-red', disconnected: 'badge-red',
    };
    return `<span class="badge ${map[status] || 'badge-gray'}">${esc(status || '—')}</span>`;
  }

  function isAdmin() {
    return me && (me.role === 'admin' || me.role === 'superadmin');
  }

  function pageHeader(title, sub, actionsHtml = '') {
    return `<div class="page-header">
      <div><h2>${esc(title)}</h2><p>${esc(sub || '')}</p></div>
      <div class="page-actions">${actionsHtml}</div>
    </div>`;
  }

  function tableWrap(html) {
    return `<div class="table-card"><div class="table-scroll">${html}</div></div>`;
  }

  function showModal(title, bodyHtml, onConfirm) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `<div class="modal-box">
      <h3>${esc(title)}</h3>
      ${bodyHtml}
      <div class="modal-actions">
        <button class="btn btn-outline" id="modalCancel">Cancelar</button>
        <button class="btn btn-primary" id="modalOk">Salvar</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#modalCancel').onclick = () => overlay.remove();
    overlay.querySelector('#modalOk').onclick = async () => {
      try {
        await onConfirm(overlay);
        overlay.remove();
      } catch (e) { toast(e.message, 'error'); }
    };
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
  }

  // ── Pages ─────────────────────────────────────────────────────────────

  async function renderSection(page) {
    if (!ENT_SECTIONS.has(page)) return;
    stopInboxPoll();
    currentSection = page;
    const fn = pages[page];
    if (fn) await fn();
  }

  async function renderInbox() {
    const el = mountEl('inbox');
    if (!el) return;
    el.innerHTML = `
      <div class="inbox-pro ${inboxDetailsOpen ? '' : 'details-collapsed'}" id="inboxPro">
        <aside class="inbox-pro-col inbox-pro-col-list">
          <div class="inbox-pro-list-head">
            <input type="search" class="inbox-search" id="inboxSearchInput" placeholder="Buscar nome ou número..." value="${esc(inboxSearch)}" oninput="window.__entInboxSearch(this.value)">
            <div class="inbox-filters" id="inboxFilters">
              <button type="button" class="inbox-filter ${inboxFilter === 'all' ? 'active' : ''}" data-f="all" onclick="window.__entInboxFilter('all')">Todas</button>
              <button type="button" class="inbox-filter ${inboxFilter === 'unread' ? 'active' : ''}" data-f="unread" onclick="window.__entInboxFilter('unread')">Não lidas</button>
              <button type="button" class="inbox-filter ${inboxFilter === 'waiting' ? 'active' : ''}" data-f="waiting" onclick="window.__entInboxFilter('waiting')">Aguardando</button>
              <button type="button" class="inbox-filter ${inboxFilter === 'resolved' ? 'active' : ''}" data-f="resolved" onclick="window.__entInboxFilter('resolved')">Resolvidas</button>
            </div>
          </div>
          <div class="inbox-conversations inbox-pro-scroll" id="convList">
            <div class="vf-empty"><div class="vf-empty-icon">💬</div><p>Carregando conversas...</p></div>
          </div>
        </aside>
        <section class="inbox-pro-col inbox-pro-col-chat" id="chatPanel">
          <div class="inbox-chat-placeholder vf-empty">
            <div class="vf-empty-icon">📱</div>
            <h3>Selecione uma conversa</h3>
            <p>Escolha um contato na lista para ver mensagens e detalhes.</p>
          </div>
        </section>
        <aside class="inbox-pro-col inbox-pro-col-details" id="inboxDetailsPanel">
          <div class="inbox-details-inner" id="inboxDetailsInner">
            <p class="inbox-details-hint">Detalhes do contato aparecem ao abrir uma conversa.</p>
          </div>
        </aside>
      </div>`;

    await loadConversations();
    inboxPoll = setInterval(loadConversations, 12000);
  }

  function renderConvListOnly() {
    const list = document.getElementById('convList');
    if (!list) return;
    const filtered = filterInboxList(inboxConversations);
    if (!inboxConversations.length) {
      list.innerHTML = `<div class="vf-empty">
        <div class="vf-empty-icon">💬</div>
        <h3>Nenhuma conversa</h3>
        <p>Configure Meta WhatsApp em Integrações e aguarde mensagens inbound.</p>
        <button class="btn btn-primary btn-sm" onclick="window.__entNav('integrations')">Ir para Integrações</button>
      </div>`;
      return;
    }
    if (!filtered.length) {
      list.innerHTML = `<div class="vf-empty"><div class="vf-empty-icon">🔍</div><h3>Nenhum resultado</h3><p>Tente outro filtro ou termo de busca.</p></div>`;
      return;
    }
    list.innerHTML = filtered.map(c => {
      const active = selectedConvId === c.id ? ' active' : '';
      const name = c.contact_name || c.contact_phone;
      return `<button type="button" class="conv-item${active}" data-id="${c.id}" onclick="window.__entOpenChat(${c.id})">
        <span class="conv-avatar">${esc(avatarInitials(c.contact_name, c.contact_phone))}</span>
        <span class="conv-body">
          <span class="conv-row-top">
            <span class="name">${esc(name)}</span>
            <span class="conv-time">${esc(fmtRelative(c.last_message_at))}</span>
          </span>
          <span class="preview">${esc(c.last_message_text || 'Sem mensagens')}</span>
          <span class="conv-row-bottom">
            <span class="conv-status-pill">${esc(inboxStatusLabel(c.status))}</span>
            ${c.unread_count ? `<span class="conv-unread">${c.unread_count}</span>` : ''}
          </span>
        </span>
      </button>`;
    }).join('');
  }

  async function loadConversations() {
    const list = document.getElementById('convList');
    if (!list) return;
    try {
      inboxConversations = await v1('/whatsapp/conversations');
      renderConvListOnly();
      if (selectedConvId) await openChat(selectedConvId, true);
    } catch (e) {
      list.innerHTML = `<div class="vf-empty"><div class="vf-empty-icon">⚠️</div><h3>WhatsApp não configurado</h3><p>${esc(e.message)}</p>
        <button class="btn btn-primary btn-sm" onclick="window.__entNav('integrations')">Configurar WhatsApp</button></div>`;
    }
  }

  function renderDetailsPanel(conv) {
    const inner = document.getElementById('inboxDetailsInner');
    if (!inner || !conv) return;
    const notes = getInboxNotes(conv.id);
    inner.innerHTML = `
      <div class="inbox-details-head">
        <span class="conv-avatar conv-avatar-lg">${esc(avatarInitials(conv.contact_name, conv.contact_phone))}</span>
        <div>
          <strong>${esc(conv.contact_name || 'Contato')}</strong>
          <div class="inbox-details-phone">${esc(conv.contact_phone || '—')}</div>
        </div>
      </div>
      <div class="inbox-details-block">
        <label>Status</label>
        <div>${badge(conv.status)}</div>
      </div>
      ${conv.lead_id ? `<div class="inbox-details-block"><label>Lead</label><div>#${conv.lead_id}</div></div>` : ''}
      ${conv.contact_id ? `<div class="inbox-details-block"><label>Contato CRM</label><div>#${conv.contact_id}</div></div>` : ''}
      ${conv.deal_id ? `<div class="inbox-details-block"><label>Deal</label><div>#${conv.deal_id}</div></div>` : ''}
      <div class="inbox-details-block">
        <label>Tags</label>
        <div class="chip-list"><span class="chip">WhatsApp</span></div>
      </div>
      <div class="inbox-details-block">
        <label>Notas internas</label>
        <textarea class="inbox-notes" id="inboxNotesArea" placeholder="Anotações visíveis só para a equipe...">${esc(notes)}</textarea>
        <button type="button" class="btn btn-outline btn-sm" style="margin-top:8px;" onclick="window.__entSaveNotes(${conv.id})">Salvar nota</button>
      </div>
      <div class="inbox-details-block">
        <label>Histórico</label>
        <div class="inbox-history-item">Última msg: ${esc(fmtDate(conv.last_message_at))}</div>
      </div>`;
  }

  async function openChat(id, silent) {
    selectedConvId = id;
    document.querySelectorAll('.conv-item').forEach(el => {
      el.classList.toggle('active', parseInt(el.dataset.id, 10) === id);
    });
    const panel = document.getElementById('chatPanel');
    if (!panel) return;
    panel.classList.add('is-loading');
    try {
      const conv = await v1('/whatsapp/conversations/' + id);
      inboxConvCache[id] = conv;
      const msgs = (conv.messages || []).map(m => `
        <div class="msg ${m.direction === 'outbound' ? 'outbound' : 'inbound'}">
          <div class="msg-bubble">${esc(m.content || '')}</div>
          <div class="msg-meta">${esc(fmtRelative(m.created_at) || fmtDate(m.created_at))}${m.status ? ' · ' + esc(m.status) : ''}</div>
        </div>`).join('');

      panel.classList.remove('is-loading');
      panel.innerHTML = `
        <header class="chat-header">
          <div class="chat-header-info">
            <span class="conv-avatar">${esc(avatarInitials(conv.contact_name, conv.contact_phone))}</span>
            <div>
              <div class="chat-title">${esc(conv.contact_name || conv.contact_phone)}</div>
              <div class="chat-sub">${esc(conv.contact_phone || '')} · ${esc(inboxStatusLabel(conv.status))}</div>
            </div>
          </div>
          <div class="chat-header-actions">
            <button type="button" class="icon-btn" title="Transferir" onclick="window.__entInboxAction('transferir')">↗</button>
            <button type="button" class="icon-btn" title="Resolver" onclick="window.__entInboxAction('resolver')">✓</button>
            <button type="button" class="icon-btn" title="Arquivar" onclick="window.__entInboxAction('arquivar')">📁</button>
            <button type="button" class="icon-btn" title="Detalhes" onclick="window.__entToggleDetails()">☰</button>
          </div>
        </header>
        <div class="chat-messages inbox-pro-scroll" id="chatMsgs">${msgs || '<div class="vf-empty vf-empty-inline"><p>Nenhuma mensagem ainda</p></div>'}</div>
        <footer class="chat-compose">
          <button type="button" class="icon-btn" title="Anexo" onclick="window.__entInboxAction('anexo')">📎</button>
          <button type="button" class="icon-btn" title="Emoji" onclick="window.__entInboxAction('emoji')">😊</button>
          <input type="text" id="chatInput" placeholder="Digite uma mensagem..." autocomplete="off" onkeydown="if(event.key==='Enter')window.__entSendMsg()">
          <button type="button" class="btn-send" onclick="window.__entSendMsg()" title="Enviar">➤</button>
        </footer>`;
      renderDetailsPanel(conv);
      const msgsEl = document.getElementById('chatMsgs');
      if (msgsEl) msgsEl.scrollTop = msgsEl.scrollHeight;
    } catch (e) {
      panel.classList.remove('is-loading');
      if (!silent) toast(e.message, 'error');
    }
  }

  function setInboxFilter(f) {
    inboxFilter = f;
    document.querySelectorAll('.inbox-filter').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.f === f);
    });
    renderConvListOnly();
  }

  function setInboxSearch(q) {
    inboxSearch = q;
    renderConvListOnly();
  }

  function toggleInboxDetails() {
    inboxDetailsOpen = !inboxDetailsOpen;
    document.getElementById('inboxPro')?.classList.toggle('details-collapsed', !inboxDetailsOpen);
  }

  function inboxAction(kind) {
    const labels = { transferir: 'Transferência', resolver: 'Resolver', arquivar: 'Arquivar', anexo: 'Anexo', emoji: 'Emoji' };
    toast(`${labels[kind] || kind} — em breve na API`);
  }

  function saveInboxNotesForConv(id) {
    const ta = document.getElementById('inboxNotesArea');
    if (!ta) return;
    saveInboxNotes(id, ta.value);
    toast('Nota salva localmente');
  }

  function stopInboxPoll() {
    if (inboxPoll) { clearInterval(inboxPoll); inboxPoll = null; }
  }

  async function sendMessage() {
    const input = document.getElementById('chatInput');
    const text = (input?.value || '').trim();
    if (!text || !selectedConvId) return;
    try {
      await v1('/whatsapp/conversations/' + selectedConvId + '/messages', { method: 'POST', body: { text } });
      input.value = '';
      await openChat(selectedConvId);
      toast('Mensagem enviada');
    } catch (e) { toast(e.message, 'error'); }
  }

  const NATIVE_INTEGRATION_SLUGS = new Set(['twilio', 'meta_whatsapp', 'stripe']);
  const EXT_INTEGRATION_META = {
    gmail: { category: 'communication', icon: '📧', desc: 'Sincronize Gmail e envie emails pelo CRM.' },
    outlook: { category: 'communication', icon: '📨', desc: 'Conecte Microsoft 365 / Outlook corporativo.' },
    instagram: { category: 'social', icon: '📸', desc: 'Receba mensagens do Instagram Direct.' },
    facebook: { category: 'social', icon: '👥', desc: 'Integre páginas Facebook para leads e mensagens.' },
    resend: { category: 'transactional', icon: '✉️', desc: 'Email transacional e campanhas via Resend.' },
  };
  const INT_CATEGORIES = [
    { id: 'communication', label: 'Comunicação', icon: '💬' },
    { id: 'social', label: 'Redes sociais', icon: '📱' },
    { id: 'transactional', label: 'Email transacional', icon: '📧' },
  ];

  function intStatusBadge(conn) {
    if (!conn) return '<span class="int-badge int-badge-off">Não conectado</span>';
    const st = (conn.status || '').toLowerCase();
    if (st === 'connected' || st === 'active') return '<span class="int-badge int-badge-ok">Conectado</span>';
    if (st === 'error' || st === 'expired') return '<span class="int-badge int-badge-err">Erro</span>';
    return '<span class="int-badge int-badge-off">Não conectado</span>';
  }

  function renderIntegrationCard(provider, connections) {
    const meta = EXT_INTEGRATION_META[provider.slug] || {
      category: 'other', icon: '🔌', desc: 'Integração externa.',
    };
    const conn = connections.find(c => (c.provider_slug || '') === provider.slug);
    const connected = conn && ['connected', 'active'].includes((conn.status || '').toLowerCase());
    const slug = esc(provider.slug);
    const connId = conn ? conn.id : null;

    let actionHtml;
    if (!isAdmin()) {
      actionHtml = '<span class="int-card-hint">Somente administradores configuram integrações.</span>';
    } else if (connected && conn) {
      actionHtml = `<div class="int-card-actions">
        <button type="button" class="btn btn-outline btn-sm" data-oauth="${connId}" data-slug="${slug}">Reconectar</button>
        <button type="button" class="btn btn-outline btn-sm int-btn-muted" onclick="window.__entToastSoon()">Desconectar</button>
      </div>`;
    } else {
      actionHtml = `<button type="button" class="btn btn-primary btn-sm int-connect-btn" data-connect-slug="${slug}" data-connect-name="${esc(provider.name)}">Conectar</button>`;
    }

    return `<article class="int-card ${connected ? 'int-card-connected' : ''}">
      <div class="int-card-icon">${meta.icon}</div>
      <div class="int-card-body">
        <h4>${esc(provider.name)}</h4>
        <p>${esc(meta.desc)}</p>
        <div class="int-card-footer">
          ${intStatusBadge(conn)}
          ${actionHtml}
        </div>
      </div>
    </article>`;
  }

  async function renderIntegrations() {
    const el = mountEl('integrations');
    if (!el) return;
    el.innerHTML = `<div class="int-native-banner">
      <span class="int-native-icon">✓</span>
      <div><strong>Canais nativos ativos</strong><p>WhatsApp (Inbox), Twilio (discador) e Email Marketing já funcionam sem configuração extra aqui.</p></div>
      <div class="int-native-links">
        <button type="button" class="btn btn-outline btn-sm" onclick="window.__entNav('inbox')">Inbox</button>
        <button type="button" class="btn btn-outline btn-sm" onclick="typeof showSection==='function'&&showSection('email')">Email</button>
      </div>
    </div>
    <div id="intGrid"><div class="vf-empty vf-empty-inline"><p>Carregando integrações...</p></div></div>`;

    try {
      const [providers, connections] = await Promise.all([
        v1('/integrations/providers'),
        v1('/integrations/connections'),
      ]);
      const external = providers.filter(p => !NATIVE_INTEGRATION_SLUGS.has(p.slug));
      const grid = document.getElementById('intGrid');
      if (!external.length) {
        grid.innerHTML = `<div class="vf-empty"><div class="vf-empty-icon">🔌</div><h4>Nenhuma integração externa</h4><p>Todos os canais disponíveis já estão embutidos no produto.</p></div>`;
        return;
      }

      const byCat = {};
      external.forEach(p => {
        const cat = (EXT_INTEGRATION_META[p.slug] || {}).category || 'other';
        if (!byCat[cat]) byCat[cat] = [];
        byCat[cat].push(p);
      });

      grid.innerHTML = INT_CATEGORIES.filter(c => byCat[c.id]?.length).map(cat => `
        <section class="int-category">
          <h3 class="int-category-title"><span>${cat.icon}</span> ${cat.label}</h3>
          <div class="int-grid">${byCat[cat.id].map(p => renderIntegrationCard(p, connections)).join('')}</div>
        </section>
      `).join('');

      grid.querySelectorAll('[data-oauth]').forEach(btn => {
        btn.onclick = () => oauthConnect(parseInt(btn.dataset.oauth, 10), btn.dataset.slug);
      });
      grid.querySelectorAll('[data-connect-slug]').forEach(btn => {
        btn.onclick = () => window.__entConnectProvider(btn.dataset.connectSlug, btn.dataset.connectName);
      });
    } catch (e) {
      document.getElementById('intGrid').innerHTML = `<div class="vf-empty"><p>${esc(e.message)}</p></div>`;
    }
  }

  async function connectProvider(slug, name) {
    if (!isAdmin()) return toast('Apenas admin', 'error');
    try {
      const conn = await v1('/integrations/connections', {
        method: 'POST',
        body: { provider_slug: slug, display_name: name },
      });
      toast('Conexão criada — complete a autorização');
      await oauthConnect(conn.id, slug);
      await renderIntegrations();
    } catch (e) { toast(e.message, 'error'); }
  }

  function newConnection() {
    if (!isAdmin()) return toast('Apenas admin', 'error');
    v1('/integrations/providers').then(providers => {
      const external = providers.filter(p => !NATIVE_INTEGRATION_SLUGS.has(p.slug));
      const opts = external.map(p => `<option value="${esc(p.slug)}">${esc(p.name)}</option>`).join('');
      if (!opts) return toast('Nenhuma integração externa disponível', 'error');
      showModal('Nova conexão', `
        <div class="form-row"><label>Integração</label><select id="ncProvider">${opts}</select></div>
        <div class="form-row"><label>Nome exibido</label><input id="ncName" placeholder="Gmail Comercial"></div>
      `, async () => {
        const slug = document.getElementById('ncProvider').value;
        const name = document.getElementById('ncName').value.trim();
        if (!name) throw new Error('Nome obrigatório');
        const conn = await v1('/integrations/connections', { method: 'POST', body: { provider_slug: slug, display_name: name } });
        toast('Conexão criada');
        await renderIntegrations();
        await oauthConnect(conn.id, slug);
      });
    });
  }

  async function oauthConnect(connectionId, providerSlug) {
    try {
      const d = await v1('/integrations/oauth/' + providerSlug + '/authorize?connection_id=' + connectionId);
      if (d.authorize_url) {
        window.open(d.authorize_url, '_blank', 'noopener');
        toast('Complete OAuth na nova aba');
      } else {
        toast(d.message || 'OAuth não configurado — adicione credenciais no .env', 'error');
      }
    } catch (e) { toast(e.message, 'error'); }
  }

  function waConfig(connectionId) {
    showModal('Configurar WhatsApp', `
      <div class="form-row"><label>Phone Number ID (Meta)</label><input id="waPhoneId" placeholder="1234567890"></div>
      <div class="form-row"><label>WABA ID (opcional)</label><input id="waWabaId" placeholder=""></div>
    `, async () => {
      const phone_number_id = document.getElementById('waPhoneId').value.trim();
      if (!phone_number_id) throw new Error('Phone Number ID obrigatório');
      const waba_id = document.getElementById('waWabaId').value.trim() || null;
      await v1('/integrations/connections/' + connectionId + '/whatsapp', {
        method: 'POST', body: { phone_number_id, waba_id },
      });
      toast('WhatsApp configurado');
      await renderIntegrations();
    });
  }

  async function renderCrudList(page, title, sub, path, columns, formFields, createFn) {
    const el = mountEl(page);
    if (!el) return;
    el.innerHTML =
      `<div style="margin-bottom:12px;"><button class="btn btn-primary btn-sm" onclick="window.__entCrudCreate('${page}')">+ Novo</button></div>` +
      '<div id="crudTable">Carregando...</div>';

    try {
      const d = await v1(path);
      const items = d.items || d;
      if (!items.length) {
        document.getElementById('crudTable').innerHTML = tableWrap(
          `<div class="empty-state"><p>Nenhum registro. Clique em + Novo.</p></div>`
        );
        return;
      }
      document.getElementById('crudTable').innerHTML = tableWrap(`<table class="data-table">
        <thead><tr>${columns.map(c => `<th>${c.label}</th>`).join('')}<th></th></tr></thead>
        <tbody>${items.map(row => `<tr>
          ${columns.map(c => `<td>${c.render ? c.render(row) : esc(row[c.key])}</td>`).join('')}
          <td><button class="btn btn-outline btn-sm" onclick="window.__entCrudDelete('${page}',${row.id})">Excluir</button></td>
        </tr>`).join('')}</tbody></table>`);
    } catch (e) {
      document.getElementById('crudTable').innerHTML = `<div class="empty-state"><p>${esc(e.message)}</p></div>`;
    }

    window.__entCrudForms = window.__entCrudForms || {};
    window.__entCrudForms[page] = { formFields, createFn, path };
  }

  async function crudCreate(page) {
    const cfg = window.__entCrudForms[page];
    if (!cfg) return;
    const fields = cfg.formFields.map(f =>
      `<div class="form-row"><label>${esc(f.label)}</label><input id="cf_${f.name}" placeholder="${esc(f.placeholder || '')}" ${f.required ? 'required' : ''}></div>`
    ).join('');
    showModal('Novo registro', fields, async () => {
      const body = {};
      cfg.formFields.forEach(f => {
        const v = document.getElementById('cf_' + f.name).value.trim();
        if (v) body[f.name] = v;
      });
      await v1(cfg.path, { method: 'POST', body });
      toast('Criado com sucesso');
      await renderSection(page);
    });
  }

  async function crudDelete(page, id) {
    const cfg = window.__entCrudForms[page];
    if (!cfg || !confirm('Excluir registro?')) return;
    await v1(cfg.path.replace(/\?.*$/, '') + '/' + id, { method: 'DELETE' });
    toast('Excluído');
    await renderSection(page);
  }

  async function renderAccounts() {
    await renderCrudList('accounts', 'Contas', 'Empresas e organizações B2B', '/accounts',
      [{ key: 'name', label: 'Nome' }, { key: 'email', label: 'Email' }, { key: 'phone', label: 'Telefone' }, { key: 'industry', label: 'Setor' }],
      [{ name: 'name', label: 'Nome *', required: true }, { name: 'email', label: 'Email' }, { name: 'phone', label: 'Telefone' }, { name: 'cnpj', label: 'CNPJ' }, { name: 'industry', label: 'Setor' }],
      null);
  }

  async function renderContacts() {
    await renderCrudList('contacts', 'Contatos', 'Pessoas vinculadas às contas', '/contacts',
      [
        { key: 'first_name', label: 'Nome', render: r => esc((r.first_name || '') + ' ' + (r.last_name || '')) },
        { key: 'email', label: 'Email' },
        { key: 'phone', label: 'Telefone' },
        { key: 'whatsapp', label: 'WhatsApp' },
      ],
      [{ name: 'first_name', label: 'Nome *', required: true }, { name: 'last_name', label: 'Sobrenome' }, { name: 'email', label: 'Email' }, { name: 'phone', label: 'Telefone' }, { name: 'whatsapp', label: 'WhatsApp' }],
      null);
  }

  async function renderTags() {
    const el = mountEl('tags');
    if (!el) return;
    el.innerHTML =
      '<div style="margin-bottom:12px;"><button class="btn btn-primary btn-sm" onclick="window.__entNewTag()">+ Nova tag</button></div>' +
      '<div id="tagsList">Carregando...</div>';
    try {
      const tags = await v1('/tags');
      if (!tags.length) {
        document.getElementById('tagsList').innerHTML = tableWrap('<div class="empty-state"><p>Nenhuma tag.</p></div>');
        return;
      }
      document.getElementById('tagsList').innerHTML = tableWrap(`<table class="data-table">
        <thead><tr><th>Nome</th><th>Cor</th></tr></thead>
        <tbody>${tags.map(t => `<tr>
          <td>${esc(t.name)}</td>
          <td><span class="chip" style="background:${esc(t.color)}22;border-color:${esc(t.color)}">${esc(t.color)}</span></td>
        </tr>`).join('')}</tbody></table>`);
    } catch (e) {
      document.getElementById('tagsList').innerHTML = `<div class="empty-state"><p>${esc(e.message)}</p></div>`;
    }
  }

  function newTag() {
    showModal('Nova tag', `
      <div class="form-row"><label>Nome</label><input id="tagName"></div>
      <div class="form-row"><label>Cor</label><input id="tagColor" type="color" value="#6366f1"></div>
    `, async () => {
      const name = document.getElementById('tagName').value.trim();
      const color = document.getElementById('tagColor').value;
      if (!name) throw new Error('Nome obrigatório');
      await v1('/tags', { method: 'POST', body: { name, color } });
      toast('Tag criada');
      await renderTags();
    });
  }

  async function renderCustomFields() {
    const el = mountEl('custom-fields');
    if (!el) return;
    el.innerHTML =
      '<div style="margin-bottom:12px;"><button class="btn btn-primary btn-sm" onclick="window.__entNewField()">+ Novo campo</button></div>' +
      '<div id="fieldsList">Carregando...</div>';
    try {
      const fields = await v1('/custom-fields');
      if (!fields.length) {
        document.getElementById('fieldsList').innerHTML = tableWrap('<div class="empty-state"><p>Nenhum campo customizado.</p></div>');
        return;
      }
      document.getElementById('fieldsList').innerHTML = tableWrap(`<table class="data-table">
        <thead><tr><th>Entidade</th><th>Nome</th><th>Tipo</th><th>Obrigatório</th></tr></thead>
        <tbody>${fields.map(f => `<tr>
          <td>${esc(f.entity)}</td><td>${esc(f.name)}</td><td>${esc(f.field_type)}</td>
          <td>${f.is_required ? 'Sim' : 'Não'}</td>
        </tr>`).join('')}</tbody></table>`);
    } catch (e) {
      document.getElementById('fieldsList').innerHTML = `<div class="empty-state"><p>${esc(e.message)}</p></div>`;
    }
  }

  function newField() {
    showModal('Novo campo', `
      <div class="form-row"><label>Entidade</label>
        <select id="cfEntity"><option value="lead">Lead</option><option value="deal">Deal</option><option value="contact">Contato</option><option value="account">Conta</option></select></div>
      <div class="form-row"><label>Nome</label><input id="cfName"></div>
      <div class="form-row"><label>Tipo</label>
        <select id="cfType"><option value="text">Texto</option><option value="number">Número</option><option value="date">Data</option><option value="boolean">Sim/Não</option></select></div>
    `, async () => {
      const entity = document.getElementById('cfEntity').value;
      const name = document.getElementById('cfName').value.trim();
      const field_type = document.getElementById('cfType').value;
      if (!name) throw new Error('Nome obrigatório');
      await v1('/custom-fields', { method: 'POST', body: { entity, name, field_type } });
      toast('Campo criado');
      await renderCustomFields();
    });
  }

  async function renderWebhooks() {
    if (!isAdmin()) return toast('Apenas admin', 'error');
    const el = mountEl('webhooks');
    if (!el) return;
    el.innerHTML =
      '<div style="margin-bottom:12px;"><button class="btn btn-primary btn-sm" onclick="window.__entNewWebhook()">+ Novo webhook</button></div>' +
      '<div id="whList">Carregando...</div>';
    try {
      const hooks = await v1('/webhooks-outbound');
      if (!hooks.length) {
        document.getElementById('whList').innerHTML = tableWrap('<div class="empty-state"><p>Nenhum webhook configurado.</p></div>');
        return;
      }
      document.getElementById('whList').innerHTML = tableWrap(`<table class="data-table">
        <thead><tr><th>Nome</th><th>URL</th><th>Eventos</th><th>Ativo</th><th></th></tr></thead>
        <tbody>${hooks.map(h => `<tr>
          <td>${esc(h.name)}</td>
          <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;">${esc(h.url)}</td>
          <td>${(h.events || []).map(e => `<span class="chip">${esc(e)}</span>`).join(' ')}</td>
          <td>${h.is_active ? badge('active') : badge('draft')}</td>
          <td><button class="btn btn-outline btn-sm" onclick="window.__entDelWebhook(${h.id})">Excluir</button></td>
        </tr>`).join('')}</tbody></table>`);
    } catch (e) {
      document.getElementById('whList').innerHTML = `<div class="empty-state"><p>${esc(e.message)}</p></div>`;
    }
  }

  function newWebhook() {
    const evChecks = WEBHOOK_EVENTS.map(e =>
      `<label class="chip"><input type="checkbox" value="${e}"> ${e}</label>`
    ).join('');
    showModal('Novo webhook', `
      <div class="form-row"><label>Nome</label><input id="whName"></div>
      <div class="form-row"><label>URL HTTPS</label><input id="whUrl" placeholder="https://..."></div>
      <div class="form-row"><label>Eventos</label><div class="chip-list">${evChecks}</div></div>
    `, async () => {
      const name = document.getElementById('whName').value.trim();
      const url = document.getElementById('whUrl').value.trim();
      const events = [...document.querySelectorAll('.modal-box input[type=checkbox]:checked')].map(c => c.value);
      if (!name || !url) throw new Error('Nome e URL obrigatórios');
      const res = await v1('/webhooks-outbound', { method: 'POST', body: { name, url, events } });
      toast('Webhook criado' + (res.secret ? ' — guarde o secret!' : ''));
      if (res.secret) alert('Secret HMAC (copie agora):\n\n' + res.secret);
      await renderWebhooks();
    });
  }

  async function delWebhook(id) {
    if (!confirm('Excluir webhook?')) return;
    await v1('/webhooks-outbound/' + id, { method: 'DELETE' });
    toast('Webhook excluído');
    await renderWebhooks();
  }

  async function renderApiKey() {
    if (!isAdmin()) return toast('Apenas admin', 'error');
    const el = mountEl('api-key');
    if (!el) return;
    el.innerHTML = '<div id="apiKeyPanel">Carregando...</div>';

    try {
      const info = await v1('/company/api-key');
      document.getElementById('apiKeyPanel').innerHTML = `
        <div class="stat-card" style="max-width:560px;">
          <div class="label">Status</div>
          <p style="margin:12px 0;">${info.has_api_key
            ? `Chave ativa: <code>${esc(info.api_key_masked)}</code>`
            : 'Nenhuma API key gerada ainda.'}</p>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <button class="btn btn-primary btn-sm" onclick="window.__entEnsureKey()">Gerar API Key</button>
            <button class="btn btn-outline btn-sm" onclick="window.__entRotateKey()">Rotacionar</button>
          </div>
          <p style="font-size:12px;color:var(--text-muted);margin-top:16px;">
            Use header <code>X-API-Key: vxf_...</code> ou <code>Authorization: Bearer vxf_...</code> nas chamadas à API v1.
          </p>
        </div>`;
    } catch (e) {
      document.getElementById('apiKeyPanel').innerHTML = `<div class="empty-state"><p>${esc(e.message)}</p></div>`;
    }
  }

  async function ensureKey() {
    const d = await v1('/company/api-key/ensure', { method: 'POST' });
    alert('API Key (copie agora — não será exibida novamente):\n\n' + d.api_key);
    await renderApiKey();
  }

  async function rotateKey() {
    if (!confirm('Rotacionar invalidará a chave anterior. Continuar?')) return;
    const d = await v1('/company/api-key/rotate', { method: 'POST' });
    alert('Nova API Key:\n\n' + (d.api_key || JSON.stringify(d)));
    await renderApiKey();
  }

  async function renderInvitations() {
    if (!isAdmin()) return toast('Apenas admin', 'error');
    const el = mountEl('invitations');
    if (!el) return;
    el.innerHTML =
      '<div style="margin-bottom:12px;"><button class="btn btn-primary btn-sm" onclick="window.__entNewInvite()">+ Convidar</button></div>' +
      '<div id="invList">Carregando...</div>';
    try {
      const invs = await v1('/invitations');
      if (!invs.length) {
        document.getElementById('invList').innerHTML = tableWrap('<div class="empty-state"><p>Nenhum convite pendente.</p></div>');
        return;
      }
      document.getElementById('invList').innerHTML = tableWrap(`<table class="data-table">
        <thead><tr><th>Email</th><th>Perfil</th><th>Expira</th><th>Status</th><th></th></tr></thead>
        <tbody>${invs.map(i => `<tr>
          <td>${esc(i.email)}</td><td>${esc(i.role)}</td><td>${fmtDate(i.expires_at)}</td>
          <td>${i.accepted_at ? badge('active') : i.is_expired ? badge('error') : badge('pending')}</td>
          <td><button class="btn btn-outline btn-sm" onclick="window.__entRevokeInvite(${i.id})">Revogar</button></td>
        </tr>`).join('')}</tbody></table>`);
    } catch (e) {
      document.getElementById('invList').innerHTML = `<div class="empty-state"><p>${esc(e.message)}</p></div>`;
    }
  }

  function newInvite() {
    showModal('Convidar usuário', `
      <div class="form-row"><label>Email</label><input id="invEmail" type="email"></div>
      <div class="form-row"><label>Perfil</label>
        <select id="invRole"><option value="agent">Agente</option><option value="supervisor">Supervisor</option><option value="admin">Admin</option></select></div>
      <div class="form-row"><label>Válido (dias)</label><input id="invDays" type="number" value="7" min="1" max="30"></div>
    `, async () => {
      const email = document.getElementById('invEmail').value.trim();
      const role = document.getElementById('invRole').value;
      const days_valid = parseInt(document.getElementById('invDays').value, 10) || 7;
      if (!email) throw new Error('Email obrigatório');
      const inv = await v1('/invitations', { method: 'POST', body: { email, role, days_valid } });
      toast('Convite criado');
      if (inv.accept_url || inv.token) {
        const link = inv.accept_url || ('/register?invite=' + inv.token);
        prompt('Link de convite (copie):', location.origin + link);
      }
      await renderInvitations();
    });
  }

  async function revokeInvite(id) {
    if (!confirm('Revogar convite?')) return;
    await v1('/invitations/' + id, { method: 'DELETE' });
    toast('Convite revogado');
    await renderInvitations();
  }

  // ── Navigation ────────────────────────────────────────────────────────

  const pages = {
    inbox: renderInbox,
    integrations: renderIntegrations,
    accounts: renderAccounts,
    contacts: renderContacts,
    tags: renderTags,
    'custom-fields': renderCustomFields,
    webhooks: renderWebhooks,
    'api-key': renderApiKey,
    invitations: renderInvitations,
  };

  window.__entNav = function (page) {
    if (typeof window.showSection === 'function') window.showSection(page);
    else renderSection(page);
  };
  window.__entRefreshInbox = loadConversations;
  window.__entOpenChat = openChat;
  window.__entSendMsg = sendMessage;
  window.__entInboxFilter = setInboxFilter;
  window.__entInboxSearch = setInboxSearch;
  window.__entToggleDetails = toggleInboxDetails;
  window.__entInboxAction = inboxAction;
  window.__entSaveNotes = saveInboxNotesForConv;
  window.__entNewConnection = newConnection;
  window.__entConnectProvider = connectProvider;
  window.__entToastSoon = () => toast('Em breve', 'error');
  window.__entOAuth = oauthConnect;
  window.__entWaConfig = waConfig;
  window.__entCrudCreate = crudCreate;
  window.__entCrudDelete = crudDelete;
  window.__entNewTag = newTag;
  window.__entNewField = newField;
  window.__entNewWebhook = newWebhook;
  window.__entDelWebhook = delWebhook;
  window.__entEnsureKey = ensureKey;
  window.__entRotateKey = rotateKey;
  window.__entNewInvite = newInvite;
  window.__entRevokeInvite = revokeInvite;

  window.VoxEnterprise = {
    SECTIONS: ENT_SECTIONS,
    render: renderSection,
    stopInboxPoll,
    setUser(user) { me = user; },
  };
})();
