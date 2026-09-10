/**
 * Granodoc Application Utilities
 * Theme management, Toast notifications, WhatsApp message formatter, and Haptic feedback.
 */

// --- GERENCIAMENTO DE TEMA (DARK / LIGHT MODE) ---
function initTheme() {
    const savedTheme = localStorage.getItem('granodoc_theme');
    const systemPrefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (savedTheme === 'dark' || (!savedTheme && systemPrefersDark)) {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }
}

function toggleTheme() {
    const isDark = document.documentElement.classList.contains('dark');
    if (isDark) {
        document.documentElement.classList.remove('dark');
        localStorage.setItem('granodoc_theme', 'light');
    } else {
        document.documentElement.classList.add('dark');
        localStorage.setItem('granodoc_theme', 'dark');
    }
    // Dispara evento para componentes ouvintes
    window.dispatchEvent(new CustomEvent('theme-changed', { detail: { dark: !isDark } }));
}

// Inicializa tema imediatamente
initTheme();

// --- SISTEMA DE TOAST NOTIFICATIONS ---
function showToast(message, type = 'info', duration = 3500) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full px-4 pointer-events-none';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'pointer-events-auto flex items-center gap-3 p-4 rounded-xl shadow-xl text-sm font-medium border transition-all duration-300 transform translate-y-2 opacity-0';

    let bgClass = 'bg-slate-900 text-white border-slate-800';
    let iconSvg = '<svg class="w-5 h-5 text-sky-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>';

    if (type === 'success') {
        bgClass = 'bg-emerald-900 text-emerald-100 border-emerald-700';
        iconSvg = '<svg class="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>';
    } else if (type === 'error') {
        bgClass = 'bg-rose-900 text-rose-100 border-rose-700';
        iconSvg = '<svg class="w-5 h-5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';
    } else if (type === 'warning') {
        bgClass = 'bg-amber-900 text-amber-100 border-amber-700';
        iconSvg = '<svg class="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>';
    }

    toast.className += ` ${bgClass}`;
    toast.innerHTML = `
        <div class="flex-shrink-0">${iconSvg}</div>
        <div class="flex-1">${message}</div>
    `;

    container.appendChild(toast);

    // Animação de entrada
    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
        toast.classList.add('translate-y-0', 'opacity-100');
    });

    // Remoção após duration
    setTimeout(() => {
        toast.classList.remove('translate-y-0', 'opacity-100');
        toast.classList.add('-translate-y-2', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// --- COPIAR PARA CLIPBOARD COM FEEDBACK (SUPORTE ROBUSTO MOBILE E HTTP) ---
async function copyTextToClipboard(text, successMsg = 'Copiado para a área de transferência!') {
    let copied = false;

    // 1. Tenta API moderna navigator.clipboard se estiver em contexto seguro (HTTPS ou localhost)
    if (navigator.clipboard && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(text);
            copied = true;
        } catch (clipErr) {
            console.warn('Clipboard API rejeitada, acionando fallback execCommand:', clipErr);
        }
    }

    // 2. Fallback com document.execCommand('copy') otimizado para iOS (Safari), Android e conexões HTTP de rede local (192.168.x.x)
    if (!copied) {
        try {
            const textArea = document.createElement('textarea');
            textArea.value = text;
            // Configurações cruciais para Safari iOS e Chrome Mobile:
            // Não usar display:none ou left: -999999px pois o WebKit mobile não seleciona fora da viewport
            textArea.style.position = 'fixed';
            textArea.style.top = '0';
            textArea.style.left = '0';
            textArea.style.width = '2em';
            textArea.style.height = '2em';
            textArea.style.padding = '0';
            textArea.style.border = 'none';
            textArea.style.outline = 'none';
            textArea.style.boxShadow = 'none';
            textArea.style.background = 'transparent';
            textArea.style.opacity = '0.01';
            textArea.style.fontSize = '16px'; // Evita zoom automático da tela no iOS
            textArea.setAttribute('readonly', '');

            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            textArea.setSelectionRange(0, text.length);

            copied = document.execCommand('copy');
            document.body.removeChild(textArea);
        } catch (execErr) {
            console.error('Falha no fallback execCommand:', execErr);
            copied = false;
        }
    }

    if (copied) {
        showToast(successMsg, 'success');
        return true;
    } else {
        console.warn('Cópia automática não autorizada pelo navegador.');
        return false;
    }
}

// --- GERADOR DE MENSAGEM WHATSAPP FORMATADA (MARKDOWN WHATSAPP) ---
function buildWhatsAppConsolidatedText(consolidado) {
    if (!consolidado) return '';

    const dataFormatada = consolidado.data || new Date().toISOString().split('T')[0];
    const partesData = dataFormatada.split('-');
    const dataBR = partesData.length === 3 ? `${partesData[2]}/${partesData[1]}/${partesData[0]}` : dataFormatada;

    const catalogo = consolidado.catalogo || [];
    const avulsos = consolidado.avulsos || [];
    const totalItens = catalogo.length + avulsos.length;

    let lines = [];
    lines.push(`📋 *ORDEM CONSOLIDADA DE COMPRAS - GRANODOC*`);
    lines.push(`📅 Data: ${dataBR}`);
    lines.push(``);

    // 1. Insumos Oficiais de Catálogo
    lines.push(`📦 *INSUMOS OFICIAIS:*`);
    if (catalogo.length > 0) {
        catalogo.forEach(item => {
            const qtd = Number(item.quantidade_total);
            const qtdStr = Number.isInteger(qtd) ? qtd : qtd.toFixed(1);
            lines.push(`• ${item.produto_nome}: ${qtdStr} ${item.unidade_medida}`);
        });
    } else {
        lines.push(`• _Nenhum insumo oficial solicitado._`);
    }

    lines.push(``);

    // 2. Itens Avulsos / Extras
    lines.push(`🛒 *ITENS AVULSOS / EXTRAS:*`);
    if (avulsos.length > 0) {
        avulsos.forEach(av => {
            const qtd = Number(av.quantidade_total);
            const qtdStr = Number.isInteger(qtd) ? qtd : qtd.toFixed(1);
            const praca = av.setores_solicitantes ? av.setores_solicitantes : 'Geral';
            lines.push(`• ${av.descricao_item}: ${qtdStr} ${av.unidade_medida} (${praca})`);
        });
    } else {
        lines.push(`• _Nenhum item avulso solicitado._`);
    }

    lines.push(``);
    lines.push(`Total de itens: ${totalItens}`);

    return lines.join('\n');
}

// --- FEEDBACK HÁPTICO / SONORO SUAVE (OPCIONAL) ---
function playTouchFeedback() {
    try {
        if ('vibrate' in navigator) {
            navigator.vibrate(15);
        }
    } catch (e) {
        // Ignora caso não suportado
    }
}
