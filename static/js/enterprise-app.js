/* VoxFlow Enterprise Hub — consome API v1 */
(function () {
  'use strict';

  const TOKEN = localStorage.getItem('voxflow_token') || localStorage.getItem('nexdial_token') || localStorage.getItem('token') || '';
  if (!TOKEN) { location.href = '/login'; return; }

  const WEBHOOK_EVENTS = [
    'lead.created', 'lead.updated', 'deal.created', 'deal.stage_changed',
    'call.completed', 'whatsapp.message.received', 'whatsapp.message.sent',
  ];

  let currentPage = 'overview';
  let me = null;
  let inboxPoll = null;
  let selectedConvId = null;

  async function v1(path, opts = {}) {
    const r = await fetch('/api/v1' + path, {
      ...opts,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + TOKEN,
        ...(opts.headers || {}),
      },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
    if (r.status === 401) { location.href = '/login'; throw new Error('Sessão expirada'); }
    if (r.status === 204) return null;
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.message || d.error || 'Erro na requisição');
    return d;
  }

  async function legacy(path, opts = {}) {
    const r = await fetch(path, {
      ...opts,
      credentials: 'include',
      headers: { Authorization: 'Bearer ' + TOKEN, ...(opts.headers || {}) },
    });
    if (r.status === 401) { location.href = '/login'; throw new Error('Sessão expirada'); }
    return r.json();
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

  async function renderOverview() {
    const el = document.getElementById('pageContainer');
    el.innerHTML = pageHeader('Dashboard Enterprise', 'Recursos da API v1 no seu tenant') +
      '<div class="ent-grid-3" id="overviewStats"><div class="stat-card"><div class="label">Carregando...</div></div></div>' +
      '<div class="ent-grid-2" style="margin-top:16px;" id="overviewCards"></div>';

    const stats = [
      { label: 'Conversas WhatsApp', path: '/whatsapp/conversations', key: null, len: true },
      { label: 'Contas CRM', path: '/accounts?limit=1', key: 'items' },
      { label: 'Contatos CRM', path: '/contacts?limit=1', key: 'items' },
      { label: 'Integrações', path: '/integrations/connections', key: null, len: true },
      { label: 'Tags', path: '/tags', key: null, len: true },
      { label: 'Webhooks', path: '/webhooks-outbound', key: null, len: true },
    ];

    const values = await Promise.all(stats.map(async (s) => {
      try {
        const d = await v1(s.path);
        if (s.len) return Array.isArray(d) ? d.length : 0;
        return (d[s.key] || []).length || (d.items || []).length || 0;
      } catch { return '—'; }
    }));

    document.getElementById('overviewStats').innerHTML = stats.map((s, i) =>
      `<div class="stat-card"><div class="label">${s.label}</div><div class="value">${values[i]}</div></div>`
    ).join('');

    document.getElementById('overviewCards').innerHTML = `
      <div class="stat-card">
        <div class="label">Inbox WhatsApp</div>
        <p style="margin:12px 0;font-size:13px;color:var(--text-secondary);">Central de conversas Meta Cloud API. Configure integração Meta WhatsApp primeiro.</p>
        <button class="btn btn-primary btn-sm" onclick="window.__entNav('inbox')">Abrir Inbox →</button>
      </div>
      <div class="stat-card">
        <div class="label">Integrações</div>
        <p style="margin:12px 0;font-size:13px;color:var(--text-secondary);">OAuth Gmail, Meta WhatsApp, Stripe e outros providers.</p>
        <button class="btn btn-primary btn-sm" onclick="window.__entNav('integrations')">Conectar →</button>
      </div>`;
  }

  async function renderInbox() {
    stopInboxPoll();
    const el = document.getElementById('pageContainer');
    el.innerHTML = pageHeader('Inbox WhatsApp', 'Conversas omnichannel via Meta Cloud API') +
      `<div class="inbox-layout" id="inboxLayout">
        <div class="inbox-list">
          <div class="inbox-list-header">Conversas</div>
          <div class="inbox-conversations" id="convList"><div class="empty-state"><i class="fab fa-whatsapp"></i><p>Carregando...</p></div></div>
        </div>
        <div class="inbox-chat" id="chatPanel">
          <div class="chat-empty"><p>Selecione uma conversa</p></div>
        </div>
      </div>`;

    await loadConversations();
    inboxPoll = setInterval(loadConversations, 12000);
  }

  function stopInboxPoll() {
    if (inboxPoll) { clearInterval(inboxPoll); inboxPoll = null; }
  }

  async function loadConversations() {
    const list = document.getElementById('convList');
    if (!list) return;
    try {
      const convs = await v1('/whatsapp/conversations');
      if (!convs.length) {
        list.innerHTML = `<div class="empty-state"><i class="fab fa-whatsapp"></i>
          <p>Nenhuma conversa ainda.</p>
          <p style="font-size:12px;margin-top:8px;">Configure Meta WhatsApp em Integrações e aguarde mensagens inbound.</p>
          <button class="btn btn-primary btn-sm" style="margin-top:12px;" onclick="window.__entNav('integrations')">Integrações</button></div>`;
        return;
      }
      list.innerHTML = convs.map(c => `
        <div class="conv-item ${selectedConvId === c.id ? 'active' : ''}" data-id="${c.id}" onclick="window.__entOpenChat(${c.id})">
          <div class="name">${esc(c.contact_name || c.contact_phone)}</div>
          <div class="preview">${esc(c.last_message_text || 'Sem mensagens')}</div>
          <div class="meta">
            <span>${fmtDate(c.last_message_at)}</span>
            ${c.unread_count ? `<span class="conv-unread">${c.unread_count}</span>` : ''}
          </div>
        </div>`).join('');
      if (selectedConvId) await openChat(selectedConvId, true);
    } catch (e) {
      list.innerHTML = `<div class="empty-state"><p>${esc(e.message)}</p>
        <button class="btn btn-primary btn-sm" style="margin-top:12px;" onclick="window.__entNav('integrations')">Configurar WhatsApp</button></div>`;
    }
  }

  async function openChat(id, silent) {
    selectedConvId = id;
    document.querySelectorAll('.conv-item').forEach(el => {
      el.classList.toggle('active', parseInt(el.dataset.id, 10) === id);
    });
    const panel = document.getElementById('chatPanel');
    if (!panel) return;
    try {
      const conv = await v1('/whatsapp/conversations/' + id);
      const msgs = (conv.messages || []).map(m => `
        <div class="msg ${m.direction === 'outbound' ? 'outbound' : 'inbound'}">
          ${esc(m.content || '')}
          <div class="time">${fmtDate(m.created_at)} · ${esc(m.status || '')}</div>
        </div>`).join('') || '<div class="chat-empty"><p>Nenhuma mensagem</p></div>';

      panel.innerHTML = `
        <div class="chat-header">${esc(conv.contact_name || conv.contact_phone)} · ${badge(conv.status)}</div>
        <div class="chat-messages" id="chatMsgs">${msgs}</div>
        <div class="chat-compose">
          <input type="text" id="chatInput" placeholder="Digite uma mensagem..." onkeydown="if(event.key==='Enter')window.__entSendMsg()">
          <button class="btn btn-primary" onclick="window.__entSendMsg()"><i class="fas fa-paper-plane"></i></button>
        </div>`;
      const msgsEl = document.getElementById('chatMsgs');
      if (msgsEl) msgsEl.scrollTop = msgsEl.scrollHeight;
      document.getElementById('inboxLayout')?.classList.add('chat-open');
    } catch (e) {
      if (!silent) toast(e.message, 'error');
    }
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

  async function renderIntegrations() {
    const el = document.getElementById('pageContainer');
    el.innerHTML = pageHeader('Integrações', 'Conecte canais e apps externos',
      isAdmin() ? '<button class="btn btn-primary btn-sm" onclick="window.__entNewConnection()">+ Nova conexão</button>' : '') +
      '<div id="intProviders" style="margin-bottom:16px;"></div><div id="intConnections"></div>';

    const [providers, connections] = await Promise.all([
      v1('/integrations/providers'),
      v1('/integrations/connections'),
    ]);

    document.getElementById('intProviders').innerHTML = `
      <div class="stat-card">
        <div class="label" style="margin-bottom:10px;">Providers disponíveis</div>
        <div class="chip-list">${providers.map(p =>
          `<span class="chip">${esc(p.name)} <small style="opacity:.6">${esc(p.slug)}</small></span>`
        ).join('') || '<span style="color:var(--text-muted)">Nenhum provider cadastrado</span>'}</div>
      </div>`;

    if (!connections.length) {
      document.getElementById('intConnections').innerHTML = tableWrap(
        '<div class="empty-state"><i class="fas fa-plug"></i><p>Nenhuma conexão configurada.</p></div>'
      );
      return;
    }

    document.getElementById('intConnections').innerHTML = tableWrap(`<table class="data-table">
      <thead><tr><th>Nome</th><th>Provider</th><th>Status</th><th>Ações</th></tr></thead>
      <tbody>${connections.map(c => `<tr>
        <td>${esc(c.display_name)}</td>
        <td>${esc(c.provider_slug || c.provider_id)}</td>
        <td>${badge(c.status)} ${c.health_status ? badge(c.health_status) : ''}</td>
        <td>
          ${isAdmin() ? `<button class="btn btn-outline btn-sm" data-oauth="${c.id}" data-slug="${esc(c.provider_slug || 'meta_whatsapp')}">OAuth</button>` : ''}
          ${(c.provider_slug === 'meta_whatsapp' || !c.provider_slug) && isAdmin() ? `<button class="btn btn-outline btn-sm" data-wa="${c.id}">WhatsApp</button>` : ''}
        </td>
      </tr>`).join('')}</tbody></table>`);

    document.querySelectorAll('[data-oauth]').forEach(btn => {
      btn.onclick = () => oauthConnect(parseInt(btn.dataset.oauth, 10), btn.dataset.slug);
    });
    document.querySelectorAll('[data-wa]').forEach(btn => {
      btn.onclick = () => waConfig(parseInt(btn.dataset.wa, 10));
    });
  }

  function newConnection() {
    if (!isAdmin()) return toast('Apenas admin', 'error');
    v1('/integrations/providers').then(providers => {
      const opts = providers.map(p => `<option value="${esc(p.slug)}">${esc(p.name)}</option>`).join('');
      showModal('Nova conexão', `
        <div class="form-row"><label>Provider</label><select id="ncProvider">${opts}</select></div>
        <div class="form-row"><label>Nome exibido</label><input id="ncName" placeholder="WhatsApp Comercial"></div>
      `, async () => {
        const slug = document.getElementById('ncProvider').value;
        const name = document.getElementById('ncName').value.trim();
        if (!name) throw new Error('Nome obrigatório');
        const conn = await v1('/integrations/connections', { method: 'POST', body: { provider_slug: slug, display_name: name } });
        toast('Conexão criada');
        await renderIntegrations();
        if (slug === 'meta_whatsapp') oauthConnect(conn.id, slug);
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
    const el = document.getElementById('pageContainer');
    el.innerHTML = pageHeader(title, sub,
      `<button class="btn btn-primary btn-sm" onclick="window.__entCrudCreate('${page}')">+ Novo</button>`) +
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
      await navigate(page);
    });
  }

  async function crudDelete(page, id) {
    const cfg = window.__entCrudForms[page];
    if (!cfg || !confirm('Excluir registro?')) return;
    await v1(cfg.path.replace(/\?.*$/, '') + '/' + id, { method: 'DELETE' });
    toast('Excluído');
    await navigate(page);
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
    const el = document.getElementById('pageContainer');
    el.innerHTML = pageHeader('Tags', 'Etiquetas para leads e deals',
      '<button class="btn btn-primary btn-sm" onclick="window.__entNewTag()">+ Nova tag</button>') +
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
    const el = document.getElementById('pageContainer');
    el.innerHTML = pageHeader('Campos customizados', 'Atributos extras em leads, deals, contatos e contas',
      '<button class="btn btn-primary btn-sm" onclick="window.__entNewField()">+ Novo campo</button>') +
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
    if (!isAdmin()) return toast('Apenas admin', 'error'), navigate('overview');
    const el = document.getElementById('pageContainer');
    el.innerHTML = pageHeader('Webhooks outbound', 'Notificações HTTP com assinatura HMAC',
      '<button class="btn btn-primary btn-sm" onclick="window.__entNewWebhook()">+ Novo webhook</button>') +
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
    if (!isAdmin()) return toast('Apenas admin', 'error'), navigate('overview');
    const el = document.getElementById('pageContainer');
    el.innerHTML = pageHeader('API Key', 'Autenticação programática para integrações') +
      '<div id="apiKeyPanel">Carregando...</div>';

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
    if (!isAdmin()) return toast('Apenas admin', 'error'), navigate('overview');
    const el = document.getElementById('pageContainer');
    el.innerHTML = pageHeader('Convites', 'Convide usuários para sua empresa',
      '<button class="btn btn-primary btn-sm" onclick="window.__entNewInvite()">+ Convidar</button>') +
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
    overview: renderOverview,
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

  async function navigate(page) {
    stopInboxPoll();
    currentPage = page;
    document.querySelectorAll('#sidebarNav .nav-link[data-page]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.page === page);
    });
    const fn = pages[page];
    if (fn) await fn();
    else document.getElementById('pageContainer').innerHTML = '<div class="empty-state"><p>Página não encontrada</p></div>';
  }

  // Global handlers for inline onclick
  window.__entNav = navigate;
  window.__entRefreshInbox = loadConversations;
  window.__entOpenChat = openChat;
  window.__entSendMsg = sendMessage;
  window.__entNewConnection = newConnection;
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

  // Init
  document.querySelectorAll('#sidebarNav .nav-link[data-page]').forEach(btn => {
    btn.addEventListener('click', () => navigate(btn.dataset.page));
  });

  (async function init() {
    try {
      me = await legacy('/api/me');
      if (isAdmin()) {
        document.querySelectorAll('.admin-only-nav').forEach(el => { el.style.display = ''; });
      }
      document.getElementById('statusDot').className = 'status-dot connected';
      document.getElementById('statusText').textContent = me.name || me.email || 'Conectado';
    } catch {
      document.getElementById('statusText').textContent = 'API ok';
    }

    const hash = (location.hash || '').replace('#', '');
    const start = pages[hash] ? hash : 'overview';
    if (hash && pages[hash]) location.hash = hash;
    await navigate(start);
  })();
})();
