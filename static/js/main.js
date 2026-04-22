/**
 * NexDial - Main JavaScript
 * Funções globais, utilidades e inicialização
 */

// ========== CONFIGURAÇÃO GLOBAL ==========
const API_BASE_URL = '/api';
const AUTH_BASE_URL = '/auth';

// ========== INICIALIZAÇÃO ==========
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 NexDial iniciado');
    
    // Verificar autenticação
    checkAuthentication();
    
    // Inicializar tooltips
    initializeTooltips();
    
    // Inicializar popovers
    initializePopovers();
});

// ========== AUTENTICAÇÃO ==========

/**
 * Verifica se o usuário está autenticado
 */
function checkAuthentication() {
    const token = localStorage.getItem('token');
    const userId = localStorage.getItem('user_id');
    
    if (!token || !userId) {
        // Redirecionar para login se em página protegida
        if (!window.location.pathname.includes('login') && 
            !window.location.pathname.includes('register') &&
            window.location.pathname !== '/') {
            window.location.href = '/login';
        }
    }
}

/**
 * Obtém o token JWT
 */
function getToken() {
    return localStorage.getItem('token');
}

/**
 * Faz logout
 */
function logout() {
    const token = getToken();
    
    if (!token) {
        window.location.href = '/login';
        return;
    }
    
    fetch(`${AUTH_BASE_URL}/logout`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        // Limpar localStorage
        localStorage.clear();
        
        // Redirecionar
        window.location.href = '/login';
    })
    .catch(error => {
        console.error('Erro ao fazer logout:', error);
        localStorage.clear();
        window.location.href = '/login';
    });
}

// ========== REQUISIÇÕES API ==========

/**
 * Faz uma requisição GET à API
 */
async function apiGet(endpoint, params = {}) {
    const token = getToken();
    
    let url = `${API_BASE_URL}${endpoint}`;
    
    // Adicionar parâmetros à URL
    if (Object.keys(params).length > 0) {
        const queryString = new URLSearchParams(params).toString();
        url += `?${queryString}`;
    }
    
    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        return await handleApiResponse(response);
    } catch (error) {
        console.error('Erro na requisição GET:', error);
        throw error;
    }
}

/**
 * Faz uma requisição POST à API
 */
async function apiPost(endpoint, data = {}) {
    const token = getToken();
    
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        return await handleApiResponse(response);
    } catch (error) {
        console.error('Erro na requisição POST:', error);
        throw error;
    }
}

/**
 * Faz uma requisição PUT à API
 */
async function apiPut(endpoint, data = {}) {
    const token = getToken();
    
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        return await handleApiResponse(response);
    } catch (error) {
        console.error('Erro na requisição PUT:', error);
        throw error;
    }
}

/**
 * Faz uma requisição DELETE à API
 */
async function apiDelete(endpoint) {
    const token = getToken();
    
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        return await handleApiResponse(response);
    } catch (error) {
        console.error('Erro na requisição DELETE:', error);
        throw error;
    }
}

/**
 * Trata a resposta da API
 */
async function handleApiResponse(response) {
    const data = await response.json();
    
    if (!response.ok) {
        // Se token expirou ou inválido
        if (response.status === 401) {
            localStorage.clear();
            window.location.href = '/login';
            throw new Error('Sessão expirada. Faça login novamente.');
        }
        
        throw new Error(data.error || 'Erro na requisição');
    }
    
    return data;
}

// ========== UTILITÁRIOS ==========

/**
 * Formata um valor para moeda brasileira
 */
function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(value);
}

/**
 * Formata uma data
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('pt-BR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
}

/**
 * Formata apenas a data (sem hora)
 */
function formatDateOnly(dateString) {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('pt-BR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    }).format(date);
}

/**
 * Copia texto para a área de transferência
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copiado para a área de transferência!', 'success');
    }).catch(error => {
        console.error('Erro ao copiar:', error);
        showNotification('Erro ao copiar texto', 'danger');
    });
}

/**
 * Formata um número de telefone
 */
function formatPhone(phone) {
    const cleaned = phone.replace(/\D/g, '');
    
    if (cleaned.length === 10) {
        return cleaned.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2-$3');
    } else if (cleaned.length === 11) {
        return cleaned.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
    }
    
    return phone;
}

/**
 * Valida um email
 */
function validateEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
}

/**
 * Valida um CNPJ
 */
function validateCNPJ(cnpj) {
    const regex = /^\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}$/;
    return regex.test(cnpj);
}

/**
 * Gera um ID único
 */
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

/**
 * Debounce - aguarda tempo antes de executar função
 */
function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func(...args), delay);
    };
}

/**
 * Throttle - executa função em intervalo
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func(...args);
            inThrottle = true;
            setTimeout(() => {
                inThrottle = false;
            }, limit);
        }
    };
}

// ========== NOTIFICAÇÕES ==========

/**
 * Mostra uma notificação toast
 */
function showNotification(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    
    if (!toastContainer) {
        const container = document.createElement('div');
        container.id = 'toastContainer';
        container.style.position = 'fixed';
        container.style.top = '20px';
        container.style.right = '20px';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }
    
    const toastId = `toast-${generateUUID()}`;
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `alert alert-${type} alert-dismissible fade show`;
    toast.style.marginBottom = '10px';
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.getElementById('toastContainer').appendChild(toast);
    
    // Auto-remover após 5 segundos
    setTimeout(() => {
        const element = document.getElementById(toastId);
        if (element) {
            element.remove();
        }
    }, 5000);
}

/**
 * Mostra um alerta customizado
 */
function showAlert(message, type = 'info', duration = 5000) {
    showNotification(message, type);
}

/**
 * Mostra um diálogo de confirmação
 */
function showConfirmDialog(title, message, onConfirm, onCancel) {
    const modalId = `confirm-modal-${generateUUID()}`;
    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal fade';
    modal.tabIndex = -1;
    modal.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header bg-warning">
                    <h5 class="modal-title text-white">
                        <i class="fas fa-exclamation-triangle"></i> ${title}
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    ${message}
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                    <button type="button" class="btn btn-warning" id="confirmBtn">Confirmar</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    const bsModal = new bootstrap.Modal(modal);
    
    document.getElementById('confirmBtn').addEventListener('click', () => {
        bsModal.hide();
        if (onConfirm) onConfirm();
        modal.remove();
    });
    
    modal.addEventListener('hidden.bs.modal', () => {
        if (onCancel) onCancel();
        modal.remove();
    });
    
    bsModal.show();
}

// ========== TOOLTIPS E POPOVERS ==========

/**
 * Inicializa tooltips do Bootstrap
 */
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Inicializa popovers do Bootstrap
 */
function initializePopovers() {
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
}

// ========== STORAGE ==========

/**
 * Salva dados no localStorage
 */
function saveToLocalStorage(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
        console.error('Erro ao salvar no localStorage:', error);
    }
}

/**
 * Obtém dados do localStorage
 */
function getFromLocalStorage(key) {
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : null;
    } catch (error) {
        console.error('Erro ao obter do localStorage:', error);
        return null;
    }
}

/**
 * Remove dados do localStorage
 */
function removeFromLocalStorage(key) {
    try {
        localStorage.removeItem(key);
    } catch (error) {
        console.error('Erro ao remover do localStorage:', error);
    }
}

// ========== TABELAS DINÂMICAS ==========

/**
 * Renderiza tabela com dados
 */
function renderTable(containerId, columns, data) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    let html = '<table class="table table-hover"><thead class="table-light"><tr>';
    
    // Cabeçalho
    columns.forEach(col => {
        html += `<th>${col}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    // Linhas
    if (data.length === 0) {
        html += '<tr><td colspan="' + columns.length + '" class="text-center text-muted py-4">Nenhum dado encontrado</td></tr>';
    } else {
        data.forEach(row => {
            html += '<tr>';
            columns.forEach(col => {
                html += `<td>${row[col.toLowerCase()] || '-'}</td>`;
            });
            html += '</tr>';
        });
    }
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

// ========== DARK MODE (Futuro) ==========

/**
 * Alterna tema escuro/claro
 */
function toggleDarkMode() {
    const isDarkMode = localStorage.getItem('darkMode') === 'true';
    localStorage.setItem('darkMode', !isDarkMode);
    
    if (!isDarkMode) {
        document.body.classList.add('dark-mode');
    } else {
        document.body.classList.remove('dark-mode');
    }
}

/**
 * Inicializa tema salvo
 */
function initializeDarkMode() {
    const isDarkMode = localStorage.getItem('darkMode') === 'true';
    if (isDarkMode) {
        document.body.classList.add('dark-mode');
    }
}

// ========== EXPORTAÇÕES ==========
console.log('✅ NexDial JavaScript loaded successfully');