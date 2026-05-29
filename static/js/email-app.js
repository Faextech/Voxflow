/* VoxFlow Email — Resend integrado, configuração simples */
(function () {
  'use strict';

  const TOKEN = localStorage.getItem('voxflow_token') || localStorage.getItem('nexdial_token') || localStorage.getItem('token') || '';
  if (!TOKEN) { location.href = '/login'; return; }

  const CATEGORIES = ['comercial', 'pos_venda', 'cobranca', 'followup', 'marketing', 'proposta', 'recuperacao'];
  const TRIGGERS = [
    { id: 'call_ended', label: 'Ligação encerrada' },
    { id: 'lead_idle', label: 'Lead parado há X dias' },
    { id: 'proposal_sent', label: 'Proposta enviada' },
    { id: 'invoice_due', label: 'Boleto venceu' },
    { id: 'whatsapp_no_reply', label: 'WhatsApp sem resposta' },
  ];
  const BLOCK_TYPES = [
    { type: 'text', label: 'Texto', icon: 'T' },
    { type: 'image', label: 'Imagem', icon: '🖼' },
    { type: 'button', label: 'Botão', icon: '▶' },
    { type: 'banner', label: 'Banner', icon: '🎨' },
    { type: 'divider', label: 'Divisor', icon: '—' },
    { type: 'footer', label: 'Rodapé', icon: '⬇' },
    { type: 'html', label: 'HTML', icon: '<>' },
  ];

  let currentPage = 'dashboard';
  let editorBlocks = [];
  let selectedBlockIdx = -1;
  let flowSteps = [];
  let pollTimer = null;
  let campPollTimer = null;

  async function api(path, opts = {}) {
    const r = await fetch('/api/email' + path, {
      ...opts,
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + TOKEN, ...(opts.headers || {}) },
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || 'Erro na requisição');
    return d;
  }

  async function apiCrm(path) {
    const r = await fetch('/api' + path, { headers: { Authorization: 'Bearer ' + TOKEN } });
    return r.json();
  }

  function toast(msg, type = 'success') {
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  function badge(status) {
    const map = {
      connected: 'badge-green', sent: 'badge-green', active: 'badge-green',
      error: 'badge-red', failed: 'badge-red', bounced: 'badge-red',
      pending: 'badge-yellow', scheduled: 'badge-yellow', sending: 'badge-blue', draft: 'badge-gray',
      queued: 'badge-blue', processing: 'badge-blue',
    };
    return `<span class="badge ${map[status] || 'badge-gray'}">${status}</span>`;
  }

  function campaignProgress(c) {
    const total = c.total_count || 0;
    const sent = c.sent_count || 0;
    const pct = c.progress_percent != null ? c.progress_percent : (total ? Math.round(sent / total * 100) : 0);
    const label = c.progress_label || `${sent}/${total}`;
    const active = c.status === 'sending' || c.status === 'scheduled';
    return `<div class="campaign-progress${active ? ' active' : ''}">
      <div class="campaign-progress-bar"><div class="campaign-progress-fill" style="width:${pct}%"></div></div>
      <span class="campaign-progress-label">${label} (${pct}%)</span>
    </div>`;
  }

  function campaignRow(c) {
    return `<tr data-camp-id="${c.id}">
      <td>${c.name}</td>
      <td>${badge(c.status)}</td>
      <td>${campaignProgress(c)}</td>
      <td>${c.opened_count || 0}</td>
    </tr>`;
  }

  function navigate(page) {
    currentPage = page;
    document.querySelectorAll('.nav-link').forEach(l => l.classList.toggle('active', l.dataset.page === page));
    renderPage();
    if (page === 'outbox') startPolling();
    else stopPolling();
    if (page === 'campaigns') startCampaignPolling();
    else stopCampaignPolling();
  }

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(() => { if (currentPage === 'outbox') loadOutbox(); }, 5000);
  }
  function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

  function startCampaignPolling() {
    stopCampaignPolling();
    campPollTimer = setInterval(() => { if (currentPage === 'campaigns') refreshCampaignsTable(); }, 3000);
  }
  function stopCampaignPolling() { if (campPollTimer) { clearInterval(campPollTimer); campPollTimer = null; } }

  async function refreshCampaignsTable() {
    const tbody = document.querySelector('#campaignsTable tbody');
    if (!tbody) return;
    try {
      const campaigns = await api('/campaigns');
      tbody.innerHTML = campaigns.map(campaignRow).join('')
        || '<tr><td colspan="4"><div class="empty-state">Nenhuma campanha ainda</div></td></tr>';
      const hasActive = campaigns.some(c => c.status === 'sending' || c.status === 'scheduled');
      if (!hasActive) stopCampaignPolling();
    } catch (_) { /* ignore poll errors */ }
  }

  async function updateStatus() {
    try {
      const st = await api('/status');
      const dot = document.getElementById('statusDot');
      const txt = document.getElementById('statusText');
      if (st.configured) {
        dot.className = 'status-dot connected';
        txt.textContent = st.from_preview || 'Resend ativo';
      } else {
        dot.className = 'status-dot pending';
        txt.textContent = 'Aguardando ativação';
      }
    } catch (e) {}
  }

  async function renderPage() {
    const container = document.getElementById('pageContainer');
    if (!container) return;
    container.innerHTML = '<div class="page-loading"><div class="loader"></div></div>';
    const pages = {
      dashboard: renderDashboard,
      setup: renderSetup,
      campaigns: renderCampaigns,
      templates: renderTemplates,
      automations: renderAutomations,
      outbox: renderOutbox,
      history: renderHistory,
      contacts: renderContacts,
    };
    try {
      if (pages[currentPage]) await pages[currentPage](container);
    } catch (err) {
      container.innerHTML = `
        <div class="page-header"><div><h2>Erro ao carregar</h2><p>${esc(err.message)}</p></div></div>
        <div class="page-content"><div class="alert alert-warn">${esc(err.message)}</div></div>`;
    }
  }

  function configBanner(steps) {
    const allDone = steps.platform_ready && steps.profile_saved && steps.domain_verified && steps.has_templates;
    if (allDone) return '';
    let pending = 0;
    if (!steps.platform_ready) pending++;
    if (!steps.profile_saved) pending++;
    if (!steps.domain_verified) pending++;
    if (!steps.has_templates) pending++;
    if (!pending) return '';
    const label = pending === 1 ? '1 etapa pendente' : `${pending} etapas pendentes`;
    return `<div class="config-banner" id="emailConfigBanner" role="alert">
      <span class="config-banner-icon" aria-hidden="true"><i class="fas fa-exclamation-triangle"></i></span>
      <span class="config-banner-text">Configuração incompleta — ${label}</span>
      <a href="#" class="config-banner-link" onclick="EmailApp.navigate('setup'); return false;">Concluir →</a>
    </div>`;
  }

  function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
  }

  function copyText(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
      const old = btn.textContent;
      btn.textContent = 'Copiado!';
      setTimeout(() => { btn.textContent = old; }, 1500);
    });
  }

  function renderDnsWizard(p) {
    const records = p.dns_records || [];
    const guide = p.dns_guide || [];

    if (p.domain_status === 'verified') {
      const dom = p.domain || (p.using_platform ? 'send.voxflow.tech' : 'seu domínio');
      const msg = p.using_platform
        ? `Email da plataforma ativo — enviando como <strong>${esc(p.from_preview || '')}</strong>. DNS de <strong>${esc(dom)}</strong> já configurado.`
        : `Domínio <strong>${esc(dom)}</strong> verificado! Pode enviar campanhas e automações.`;
      return `<div class="panel panel-success"><div class="panel-body">
        <div class="alert alert-success"><i class="fas fa-check-circle"></i> ${msg}</div>
      </div></div>`;
    }

    const domainLabel = p.domain || 'seu-dominio.com.br';
    const fromPreview = p.from_preview || 'Sua Empresa <contato@suaempresa.com.br>';
    const needsSave = !p.profile_complete;

    return `
    <div class="panel panel-warn" id="dnsWizard">
      <div class="panel-header">
        <h3><i class="fas fa-globe"></i> Passo 2 — Configure o DNS de <strong>${esc(domainLabel)}</strong></h3>
        ${domainBadge(p.domain_status || 'pending')}
      </div>
      <div class="panel-body">
        ${needsSave ? `<div class="alert alert-warn">
          <i class="fas fa-arrow-up"></i>
          <strong>Salve o formulário acima</strong> com seu email (ex: contato@faextech.com.br). Os registros DNS aparecerão aqui automaticamente.
        </div>` : ''}
        <div class="alert alert-info">
          <i class="fas fa-info-circle"></i>
          Para enviar como <strong>${esc(fromPreview)}</strong>, adicione estes registros no painel DNS do seu domínio (Hostinger, Registro.br, GoDaddy, Cloudflare, etc.).
        </div>

        <div class="dns-wizard-steps">
          ${guide.map(g => `
            <div class="dns-step-card">
              <div class="dns-step-num">${g.step}</div>
              <h4>${esc(g.title)}</h4>
              <p>${esc(g.body)}</p>
            </div>`).join('')}
        </div>

        <h4 class="dns-records-title">Registros para copiar</h4>
        <div class="dns-table-wrap">
          <table class="dns-table">
            <thead><tr><th>Tipo</th><th>Nome / Host</th><th>Valor</th><th>Finalidade</th></tr></thead>
            <tbody>
              ${records.length ? records.map((r, i) => `
                <tr>
                  <td><span class="badge badge-blue">${esc(r.type)}</span>${r.priority ? '<br><small>Pri: '+esc(String(r.priority))+'</small>' : ''}</td>
                  <td>
                    <span class="dns-value">${esc(r.name)}</span>
                    <button type="button" class="btn-copy" onclick="EmailApp.copyVal('name-${i}', this)">Copiar</button>
                    <span id="name-${i}" style="display:none">${esc(r.name)}</span>
                  </td>
                  <td>
                    <span class="dns-value">${esc(r.value)}</span>
                    <button type="button" class="btn-copy" onclick="EmailApp.copyVal('val-${i}', this)">Copiar</button>
                    <span id="val-${i}" style="display:none">${esc(r.value)}</span>
                  </td>
                  <td class="dns-purpose">${esc(r.purpose || '—')}</td>
                </tr>`).join('') : `
                <tr><td colspan="4" class="empty-state">Salve o email remetente acima e clique em <strong>Atualizar registros DNS</strong></td></tr>`}
            </tbody>
          </table>
        </div>

        <div class="dns-actions">
          <button type="button" class="btn" onclick="EmailApp.verifyDomain()" ${needsSave ? 'disabled' : ''}><i class="fas fa-check-circle"></i> Verificar domínio</button>
          <button type="button" class="btn btn-secondary" onclick="EmailApp.refreshDns()" ${needsSave ? 'disabled' : ''}><i class="fas fa-sync"></i> Atualizar registros DNS</button>
        </div>
        <p class="dns-hint">Após adicionar no DNS, aguarde ~15–30 min e clique em Verificar. Propagação máxima: 48h.</p>
      </div>
    </div>`;
  }

  function bindPreview() {
    const form = document.getElementById('profileForm');
    const preview = document.getElementById('livePreview');
    if (!form || !preview) return;
    const update = () => {
      const name = form.from_name.value.trim() || 'Sua Empresa';
      const email = form.from_email.value.trim() || 'contato@suaempresa.com.br';
      preview.textContent = name + ' <' + email + '>';
    };
    form.from_name.oninput = update;
    form.from_email.oninput = update;
  }
  function domainBadge(status) {
    const map = {
      verified: ['badge-green', '✓ Verificado'],
      pending: ['badge-yellow', '⏳ DNS pendente'],
      failed: ['badge-red', '✗ Erro DNS'],
      platform: ['badge-blue', 'Padrão'],
    };
    const [cls, label] = map[status] || ['badge-gray', status];
    return `<span class="badge ${cls}">${label}</span>`;
  }

  // ── Dashboard ──
  async function renderDashboard(el) {
    const [d, setup] = await Promise.all([api('/dashboard'), api('/setup')]);
    const s = setup.steps_done;
    el.innerHTML = `
      <div class="page-header">
        <div><h2>Email Marketing</h2><p>Campanhas, templates e automações com Resend</p></div>
        <button class="btn btn-primary" onclick="EmailApp.navigate('campaigns')"><i class="fas fa-plus"></i> Nova campanha</button>
      </div>
      <div class="page-content">
      ${configBanner(s)}
      <div class="metrics-grid">
        <div class="metric-card"><small>Enviados 7d</small><h3>${d.sent_week}</h3></div>
        <div class="metric-card"><small>Taxa de abertura</small><h3>${d.open_rate}%</h3></div>
        <div class="metric-card"><small>Fila pendente</small><h3>${d.queue_pending}</h3></div>
        <div class="metric-card"><small>Campanhas ativas</small><h3>${d.active_campaigns}</h3></div>
      </div>
      </div>`;
  }

  // ── Guia & Configuração ──
  async function renderSetup(el) {
    const data = await api('/setup');
    const p = data.profile;
    const platformEmail = 'contato@send.voxflow.tech';
    const savedEmail = p.from_email && p.from_email !== platformEmail ? p.from_email : '';

    el.innerHTML = `
      <div class="page-header">
        <div><h2>Guia & Configuração</h2><p>Passo 1: identidade · Passo 2: DNS · Passo 3: enviar</p></div>
      </div>
      <div class="page-content">

      <div class="panel">
        <div class="panel-header"><h3>Passo 1 — Identidade de envio</h3>${domainBadge(p.domain_status)}</div>
        <div class="panel-body">
          <form id="profileForm">
            <div class="form-grid">
              <div class="form-group">
                <label>Nome da empresa</label>
                <input name="from_name" value="${esc(p.from_name)}" placeholder="Faex Tech" required>
              </div>
              <div class="form-group">
                <label>Email remetente (seu domínio)</label>
                <input name="from_email" type="email" value="${esc(savedEmail)}" placeholder="contato@faextech.com.br" required>
              </div>
              <div class="form-group full">
                <label>Reply-To (opcional)</label>
                <input name="reply_to" type="email" value="${esc(p.reply_to)}" placeholder="contato@faextech.com.br">
              </div>
            </div>
            <div class="preview-box">Prévia: <strong id="livePreview">${esc(p.from_preview || 'Faex Tech <contato@faextech.com.br>')}</strong></div>
            <div style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap;">
              <button type="submit" class="btn"><i class="fas fa-save"></i> Salvar</button>
              <button type="button" class="btn btn-secondary" id="btnTestEmail" ${!p.can_send ? 'disabled' : ''}><i class="fas fa-paper-plane"></i> Enviar teste</button>
            </div>
          </form>
        </div>
      </div>

      ${renderDnsWizard(p)}

      <div class="panel">
        <div class="panel-header"><h3>Passo 3 — Como funciona</h3></div>
        <div class="panel-body how-it-works">
          <div class="how-step"><span class="how-num">1</span><div><strong>Resend envia por você</strong><p>A plataforma usa o Resend — você não precisa de API key nem SMTP.</p></div></div>
          <div class="how-step"><span class="how-num">2</span><div><strong>Use o email da sua empresa</strong><p>Adicione 2–3 registros DNS no painel do domínio (Passo 2 acima) para liberar o envio.</p></div></div>
          <div class="how-step"><span class="how-num">3</span><div><strong>Crie templates</strong><p>Editor visual com blocos — textos, imagens, botões e variáveis do CRM.</p></div></div>
          <div class="how-step"><span class="how-num">4</span><div><strong>Dispare campanhas e automações</strong><p>Envie em massa ou configure gatilhos (ligação encerrada, lead parado, etc.).</p></div></div>
        </div>
      </div>
      </div>`;

    document.getElementById('profileForm').onsubmit = saveProfile;
    const testBtn = document.getElementById('btnTestEmail');
    if (testBtn && !testBtn.disabled) testBtn.onclick = sendTestEmail;
    bindPreview();
  }

  async function verifyDomain() {
    try {
      const r = await api('/setup/verify-domain', { method: 'POST' });
      toast(r.message || (r.ok ? 'Domínio verificado!' : 'DNS pendente'), r.ok ? 'success' : 'error');
      updateStatus();
      renderPage();
    } catch (err) { toast(err.message, 'error'); }
  }

  async function refreshDns() {
    try {
      await api('/setup/refresh-dns', { method: 'POST' });
      toast('Registros DNS atualizados');
      renderPage();
    } catch (err) { toast(err.message, 'error'); }
  }

  function copyVal(id, btn) {
    const el = document.getElementById(id);
    if (el) copyText(el.textContent, btn);
  }

  async function saveProfile(e) {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api('/setup', {
        method: 'PUT',
        body: JSON.stringify({
          from_name: fd.get('from_name'),
          from_email: fd.get('from_email'),
          reply_to: fd.get('reply_to'),
        }),
      });
      toast('Salvo! Role até o Passo 2 e configure o DNS.');
      updateStatus();
      await renderPage();
      const wiz = document.getElementById('dnsWizard');
      if (wiz) wiz.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) { toast(err.message, 'error'); }
  }

  async function sendTestEmail() {
    const email = prompt('Enviar teste para qual email?', '');
    if (!email) return;
    try {
      await api('/test', {
        method: 'POST',
        body: JSON.stringify({
          to: email,
          subject: 'Teste VoxFlow — email funcionando!',
          body_html: '<p>Se você recebeu este email, o módulo de email está <strong>funcionando</strong> corretamente.</p>',
        }),
      });
      toast('Email de teste enviado!');
    } catch (err) { toast(err.message, 'error'); }
  }

  // ── Templates ──
  async function renderTemplates(el) {
    const templates = await api('/templates');
    el.innerHTML = `
      <div class="page-header"><div><h2>Templates</h2><p>Monte emails com blocos visuais</p></div>
        <button class="btn" onclick="EmailApp.newTemplate()"><i class="fas fa-plus"></i> Novo template</button></div>
      <div class="page-content">
        <div id="templateEditor" style="display:none;" class="card">
          <div class="form-grid">
            <div class="form-group"><label>Nome</label><input id="tplName"></div>
            <div class="form-group"><label>Categoria</label><select id="tplCategory">${CATEGORIES.map(c => `<option value="${c}">${c}</option>`).join('')}</select></div>
            <div class="form-group full"><label>Assunto</label><input id="tplSubject" placeholder="Olá {{lead_name}}, ..."></div>
          </div>
          <div class="editor-layout">
            <div class="block-palette"><h4>Blocos</h4>${BLOCK_TYPES.map(b => `
              <button class="block-btn" onclick="EmailApp.addBlock('${b.type}')">${b.icon} ${b.label}</button>`).join('')}</div>
            <div class="editor-canvas" id="editorCanvas"></div>
            <div class="editor-props" id="editorProps"></div>
          </div>
          <div style="margin-top:16px;display:flex;gap:10px;">
            <button class="btn" onclick="EmailApp.saveTemplate()">Salvar template</button>
            <button class="btn btn-secondary" onclick="EmailApp.cancelTemplate()">Cancelar</button>
          </div>
        </div>
        <div class="data-table-wrap"><table class="data-table"><thead><tr><th>Nome</th><th>Categoria</th><th>Assunto</th><th></th></tr></thead>
        <tbody>${templates.length ? templates.map(t => `<tr>
          <td>${t.name}</td><td>${t.category || '—'}</td><td>${t.subject}</td>
          <td><button class="btn btn-sm btn-danger" onclick="EmailApp.deleteTemplate(${t.id})">Excluir</button></td>
        </tr>`).join('') : '<tr><td colspan="4"><div class="empty-state"><div class="empty-icon">📄</div><p>Nenhum template — crie o primeiro!</p></div></td></tr>'}
        </tbody></table></div>
      </div>`;
  }

  function newTemplate() {
    editorBlocks = [];
    selectedBlockIdx = -1;
    document.getElementById('templateEditor').style.display = 'block';
    renderCanvas();
  }
  function cancelTemplate() { document.getElementById('templateEditor').style.display = 'none'; }

  function addBlock(type) {
    const defaults = {
      text: 'Olá {{lead_name}},\n\nEscreva sua mensagem aqui...',
      image: 'https://via.placeholder.com/600x200', button: 'Saiba mais', banner: 'Oferta especial',
      divider: '', footer: '© Sua Empresa · Cancelar inscrição', html: '<p>HTML customizado</p>',
    };
    editorBlocks.push({ type, content: defaults[type] || '', url: '' });
    selectedBlockIdx = editorBlocks.length - 1;
    renderCanvas();
  }

  function renderCanvas() {
    const canvas = document.getElementById('editorCanvas');
    if (!canvas) return;
    if (!editorBlocks.length) {
      canvas.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:40px;">Clique nos blocos à esquerda</p>';
      return;
    }
    canvas.innerHTML = editorBlocks.map((b, i) => `
      <div class="canvas-block ${i === selectedBlockIdx ? 'selected' : ''}" onclick="EmailApp.selectBlock(${i})">
        <button class="block-remove" onclick="event.stopPropagation();EmailApp.removeBlock(${i})">×</button>
        <small style="color:var(--text-muted);">${b.type}</small>
        <div style="margin-top:4px;font-size:13px;">${b.type === 'image' ? `<img src="${b.url || b.content}" style="max-width:100%;border-radius:6px;">` : esc((b.content || '').substring(0, 120))}</div>
      </div>`).join('');
    renderBlockProps();
  }

  function selectBlock(i) { selectedBlockIdx = i; renderCanvas(); }
  function removeBlock(i) { editorBlocks.splice(i, 1); selectedBlockIdx = -1; renderCanvas(); }

  function renderBlockProps() {
    const props = document.getElementById('editorProps');
    if (!props || selectedBlockIdx < 0 || !editorBlocks[selectedBlockIdx]) {
      if (props) props.innerHTML = '<p style="color:var(--text-muted);font-size:12px;">Selecione um bloco</p>';
      return;
    }
    const b = editorBlocks[selectedBlockIdx];
    props.innerHTML = `<h4 style="font-size:12px;margin-bottom:12px;">Editar: ${b.type}</h4>
      <div class="form-group"><label>Conteúdo</label><textarea id="blockContent" rows="5">${esc(b.content || '')}</textarea></div>
      ${b.type === 'button' || b.type === 'image' ? `<div class="form-group"><label>URL</label><input id="blockUrl" value="${esc(b.url || '')}"></div>` : ''}`;
    document.getElementById('blockContent').oninput = e => { b.content = e.target.value; renderCanvas(); };
    const urlEl = document.getElementById('blockUrl');
    if (urlEl) urlEl.oninput = e => { b.url = e.target.value; renderCanvas(); };
  }

  async function saveTemplate() {
    const name = document.getElementById('tplName').value.trim();
    const subject = document.getElementById('tplSubject').value.trim();
    if (!name || !subject || !editorBlocks.length) { toast('Preencha nome, assunto e blocos', 'error'); return; }
    try {
      await api('/templates', { method: 'POST', body: JSON.stringify({
        name, subject, category: document.getElementById('tplCategory').value, blocks: editorBlocks,
      })});
      toast('Template salvo!');
      cancelTemplate();
      renderPage();
    } catch (err) { toast(err.message, 'error'); }
  }

  async function deleteTemplate(id) {
    if (!confirm('Excluir template?')) return;
    await api('/templates/' + id, { method: 'DELETE' });
    renderPage();
  }

  // ── Campanhas ──
  async function renderCampaigns(el) {
    const [campaigns, templates, crmCamps] = await Promise.all([
      api('/campaigns'), api('/templates'), apiCrm('/campaigns').catch(() => []),
    ]);
    el.innerHTML = `
      <div class="page-header"><div><h2>Campanhas</h2><p>Disparo em massa para leads com email</p></div></div>
      <div class="page-content">
        <div class="card">
          <div class="card-title">Nova campanha</div>
          <div class="form-grid">
            <div class="form-group"><label>Nome</label><input id="campName"></div>
            <div class="form-group"><label>Template</label><select id="campTpl"><option value="">Escrever manualmente</option>${templates.map(t => `<option value="${t.id}">${t.name}</option>`).join('')}</select></div>
            <div class="form-group"><label>Leads da campanha CRM</label><select id="campCrm">${(crmCamps || []).map(c => `<option value="${c.id}">${c.name}</option>`).join('')}</select></div>
            <div class="form-group full"><label>Assunto</label><input id="campSubject"></div>
            <div class="form-group full"><label>Corpo HTML</label><textarea id="campBody" rows="4"></textarea></div>
          </div>
          <button class="btn" onclick="EmailApp.createCamp()">Criar e enviar</button>
        </div>
        <div class="data-table-wrap"><table id="campaignsTable" class="data-table"><thead><tr><th>Campanha</th><th>Status</th><th>Progresso</th><th>Aberturas</th></tr></thead>
        <tbody>${campaigns.map(campaignRow).join('')
          || '<tr><td colspan="4"><div class="empty-state">Nenhuma campanha ainda</div></td></tr>'}
        </tbody></table></div>
      </div>`;
    const hasActive = campaigns.some(c => c.status === 'sending' || c.status === 'scheduled');
    if (hasActive) startCampaignPolling();
  }

  async function createCamp() {
    try {
      const tplId = document.getElementById('campTpl').value;
      const body = {
        name: document.getElementById('campName').value,
        crm_campaign_id: parseInt(document.getElementById('campCrm').value),
        subject: document.getElementById('campSubject').value,
        body_html: document.getElementById('campBody').value,
      };
      if (tplId) body.template_id = parseInt(tplId);
      const camp = await api('/campaigns', { method: 'POST', body: JSON.stringify(body) });
      await api('/campaigns/' + camp.id + '/send', { method: 'POST', body: '{}' });
      toast('Campanha agendada!');
      renderPage();
    } catch (err) { toast(err.message, 'error'); }
  }

  // ── Automações ──
  async function renderAutomations(el) {
    const autos = await api('/automations');
    el.innerHTML = `
      <div class="page-header"><div><h2>Automações</h2><p>Follow-up automático por email</p></div>
        <button class="btn" onclick="EmailApp.newAutomation()"><i class="fas fa-plus"></i> Nova</button></div>
      <div class="page-content">
        <div id="autoEditor" style="display:none;" class="card">
          <div class="form-grid">
            <div class="form-group"><label>Nome</label><input id="autoName"></div>
            <div class="form-group"><label>Quando (gatilho)</label><select id="autoTrigger">${TRIGGERS.map(t => `<option value="${t.id}">${t.label}</option>`).join('')}</select></div>
          </div>
          <div class="flow-builder" id="flowBuilder"></div>
          <button class="btn" onclick="EmailApp.saveAutomation()">Salvar</button>
          <button class="btn btn-secondary" onclick="EmailApp.cancelAutomation()">Cancelar</button>
        </div>
        <div class="data-table-wrap"><table class="data-table"><thead><tr><th>Nome</th><th>Gatilho</th><th>Status</th><th></th></tr></thead>
        <tbody>${autos.map(a => `<tr><td>${a.name}</td><td>${a.trigger_type}</td><td>${badge(a.status)}</td>
          <td><button class="btn btn-sm btn-secondary" onclick="EmailApp.toggleAuto(${a.id},'${a.status}')">${a.status === 'active' ? 'Pausar' : 'Ativar'}</button></td></tr>`).join('')
          || '<tr><td colspan="4"><div class="empty-state">Nenhuma automação</div></td></tr>'}
        </tbody></table></div>
      </div>`;
  }

  function newAutomation() {
    flowSteps = [{ type: 'trigger', label: 'Quando: evento ocorre' }];
    document.getElementById('autoEditor').style.display = 'block';
    renderFlow();
  }
  function cancelAutomation() { document.getElementById('autoEditor').style.display = 'none'; }
  function renderFlow() {
    const fb = document.getElementById('flowBuilder');
    if (!fb) return;
    fb.innerHTML = flowSteps.map((s, i) => `${i ? '<div class="flow-connector"></div>' : ''}<div class="flow-node ${s.type}">${s.label}</div>`).join('') +
      '<div class="flow-connector"></div><button class="flow-add-btn" onclick="EmailApp.addFlowStep()">+ Adicionar ação</button>';
  }
  function addFlowStep() {
    const actions = ['Enviar email', 'Criar tarefa no CRM', 'Notificar operador'];
    const pick = prompt('Ação:\n' + actions.map((a,i) => (i+1)+'. '+a).join('\n'));
    const idx = parseInt(pick) - 1;
    if (idx >= 0) { flowSteps.push({ type: 'action', label: 'Então: ' + actions[idx] }); renderFlow(); }
  }
  async function saveAutomation() {
    const name = document.getElementById('autoName').value.trim();
    if (!name) { toast('Nome obrigatório', 'error'); return; }
    await api('/automations', { method: 'POST', body: JSON.stringify({
      name, trigger_type: document.getElementById('autoTrigger').value, flow: flowSteps, status: 'active',
    })});
    toast('Automação criada!');
    cancelAutomation();
    renderPage();
  }
  async function toggleAuto(id, status) {
    await api('/automations/' + id, { method: 'PUT', body: JSON.stringify({ status: status === 'active' ? 'paused' : 'active' }) });
    renderPage();
  }

  // ── Outbox / History / Contacts ──
  async function renderOutbox(el) { await loadOutboxContent(el); }
  async function loadOutbox() {
    const el = document.getElementById('pageContainer');
    if (el && currentPage === 'outbox') await loadOutboxContent(el);
  }
  async function loadOutboxContent(el) {
    const items = await api('/queue');
    el.innerHTML = `<div class="page-header"><div><h2>Caixa de Saída</h2><p>Fila de envio (atualiza a cada 5s)</p></div></div>
      <div class="page-content"><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Para</th><th>Assunto</th><th>Status</th></tr></thead>
      <tbody>${items.map(r => `<tr><td>${r.to_email}</td><td>${r.subject}</td><td>${badge(r.status)}</td></tr>`).join('')
        || '<tr><td colspan="3"><div class="empty-state">Fila vazia — tudo enviado!</div></td></tr>'}
      </tbody></table></div></div>`;
  }

  async function renderHistory(el) {
    const sends = await api('/sends?limit=100');
    el.innerHTML = `<div class="page-header"><div><h2>Histórico</h2></div></div>
      <div class="page-content"><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Para</th><th>Assunto</th><th>Status</th><th>Aberto</th><th>Data</th></tr></thead>
      <tbody>${sends.map(r => `<tr><td>${r.to_email}</td><td>${r.subject}</td><td>${badge(r.status)}</td><td>${r.opened_at ? '✓' : '—'}</td><td>${new Date(r.sent_at).toLocaleString('pt-BR')}</td></tr>`).join('')}
      </tbody></table></div></div>`;
  }

  async function renderContacts(el) {
    const contacts = await api('/contacts');
    el.innerHTML = `<div class="page-header"><div><h2>Contatos</h2><p>Leads com email cadastrado</p></div></div>
      <div class="page-content"><div class="data-table-wrap"><table class="data-table"><thead><tr><th>Nome</th><th>Email</th><th>Opt-out</th></tr></thead>
      <tbody>${contacts.map(c => `<tr><td>${c.name || '—'}</td><td>${c.email}</td><td>${c.unsubscribed ? 'Sim' : 'Não'}</td></tr>`).join('')}
      </tbody></table></div></div>`;
  }

  document.querySelectorAll('.nav-link').forEach(l => l.addEventListener('click', () => navigate(l.dataset.page)));

  window.EmailApp = {
    navigate, renderPage, verifyDomain, refreshDns, copyVal,
    newTemplate, addBlock, selectBlock, removeBlock, saveTemplate, cancelTemplate, deleteTemplate,
    createCamp, newAutomation, addFlowStep, saveAutomation, cancelAutomation, toggleAuto,
  };

  updateStatus();
  renderPage();
})();
