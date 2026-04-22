import os

file_path = r"c:\Users\Allan\nexdial\app\templates\dashboard.html"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

find1 = """            <div style="margin-top:16px; text-align:center;">
                <button onclick="dialerOverlayDeleteCampaign()" style="background:none; border:none; color:#ef4444; font-size:12px; cursor:pointer; text-decoration:underline;">Excluir campanha</button>
            </div>"""

replace1 = """            <div style="margin-top:16px; text-align:center;">
                <button onclick="dialerOverlayClearLeads()" style="background:none; border:none; color:#ef4444; font-size:12px; cursor:pointer; text-decoration:underline; margin-right: 15px;">Apagar leads da campanha</button>
                <button onclick="dialerOverlayDeleteCampaign()" style="background:none; border:none; color:#ef4444; font-size:12px; cursor:pointer; text-decoration:underline;">Excluir campanha</button>
            </div>"""

find2 = """    async function dialerOverlayDeleteCampaign() {
        if (!_dialerCampaignId) return;
        const nameEl = document.getElementById('do-campaign-name');
        const name   = nameEl ? nameEl.textContent : String(_dialerCampaignId);
        await confirmDeleteCampaign(_dialerCampaignId, name);
        dialerOverlayClose();
    }"""

replace2 = """    async function dialerOverlayDeleteCampaign() {
        if (!_dialerCampaignId) return;
        const nameEl = document.getElementById('do-campaign-name');
        const name   = nameEl ? nameEl.textContent : String(_dialerCampaignId);
        await confirmDeleteCampaign(_dialerCampaignId, name);
        dialerOverlayClose();
    }

    window.dialerOverlayClearLeads = async function() {
        if (!_dialerCampaignId) return;
        const nameEl = document.getElementById('do-campaign-name');
        const name   = nameEl ? nameEl.textContent : String(_dialerCampaignId);
        if (!confirm(`Tem certeza que deseja apagar TODOS OS LEADS vinculados a campanha "${name}"?\\nA campanha em si não será apagada.`)) return;
        try {
            const resp = await authFetch(`/api/campaign/${_dialerCampaignId}/clear-leads`, { method: 'POST' });
            if (!resp.error) {
                showToast(`Todos os leads da campanha foram excluídos.`);
                dialerOverlayClose();
                loadDashboardData();
            } else {
                showToast(resp.error || "Erro ao esvaziar a campanha.", "error");
            }
        } catch (err) {
            console.error(err);
            showToast("Erro de rede ao esvaziar a campanha.", "error");
        }
    };"""

find3 = """                        <button class="btn btn-primary" onclick="exportLeadsCSV()" style="white-space:nowrap;">
                            Exportar CSV
                        </button>"""

replace3 = """                        <button class="btn btn-primary" onclick="exportLeadsCSV()" style="white-space:nowrap; margin-right: 8px;">
                            Exportar CSV
                        </button>
                        <button class="btn btn-danger" onclick="clearAllLeads()" style="background:#ef4444; color:white; border:none; padding:10px 16px; border-radius:6px; cursor:pointer; font-weight:600; white-space:nowrap;">
                            Apagar todos os leads
                        </button>"""

find4 = """        window.exportLeadsCSV = function() {"""

replace4 = """        window.clearAllLeads = async function() {
            if (!confirm('ATENÇÃO: Você tem certeza que deseja apagar ABSOLUTAMENTE TODOS OS LEADS da sua conta?\\nIsso é irreversível e afetará todas as campanhas.')) return;
            try {
                const resp = await authFetch(`/api/clear-all-leads`, { method: 'POST' });
                if (!resp.error) {
                    showToast("Todos os leads da empresa foram excluídos.");
                    if (window.fetchLeads) window.fetchLeads(); // Recarregar tabela se na aba
                    loadDashboardData(); // Recarregar contadores gerais
                } else {
                    showToast(resp.error || "Erro ao esvaziar leads.", "error");
                }
            } catch (err) {
                showToast("Erro de rede ao excluir todos os leads.", "error");
            }
        };

        window.exportLeadsCSV = function() {"""


text = text.replace(find1, replace1)
text = text.replace(find2, replace2)
text = text.replace(find3, replace3)
text = text.replace(find4, replace4)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(text)

print("HTML and JS patched.")
