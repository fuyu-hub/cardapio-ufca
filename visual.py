"""
visual.py
─────────
Gera o index.html como SPA responsivo com Hash Routing.
"""

import json

# MUDANÇA AQUI: "Proteína" no lugar de "Principal"
ORDEM_CATEGORIAS = [
    "Proteína", "Vegetariano", "Sopas", "Guarnição",
    "Acompanhamentos", "Saladas", "Suco", "Sobremesa",
]

def gerar_html(dados: dict, caminho: str = "index.html") -> None:
    json_data = json.dumps(dados, ensure_ascii=False)

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(_montar_html(json_data))

    print(f"✅ '{caminho}' gerado com sucesso!")

# ─────────────────────────────────────────────────────────────────────────────

def _montar_html(json_data: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Cardápio RU — UFCA</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800;900&family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet">
    <style>{_css()}</style>
</head>
<body>

<div class="router">

    <div class="screen" id="screen-home">
        <div class="detail-header home-header">
            <div class="home-title">Cardápio da Semana</div>
            <div class="home-sub">RU UFCA</div>
        </div>
        
        <div class="home-wrap-scroll">
            <div class="home-pills">
                <button class="pill almoco-pill" onclick="goTo('almoco')">
                    <div class="pill-icon-wrapper">
                        <img src="img/sol.svg" alt="Sol" class="pill-icon-img">
                    </div>
                    <div class="pill-info almoco-info">
                        <div class="pill-name">Almoço</div>
                        <div class="pill-time">
                            {_clock_svg('rgba(0,0,0,0.8)')}
                            11:00 às 14:00
                        </div>
                    </div>
                </button>

                <button class="pill jantar-pill" onclick="goTo('jantar')">
                    <div class="pill-info jantar-info">
                        <div class="pill-name">Jantar</div>
                        <div class="pill-time jantar-time">
                            {_clock_svg('rgba(255,255,255,0.9)')}
                            17:00 às 19:40
                        </div>
                    </div>
                    <div class="pill-icon-wrapper">
                        <img src="img/lua.svg" alt="Lua" class="pill-icon-img">
                    </div>
                </button>
            </div>
            
            <div class="home-footer">
                O cardápio pode sofrer alterações
            </div>
        </div>
    </div><div class="screen screen-detail" id="screen-almoco">
        <div class="detail-header almoco-header">
            <div class="header-top-container">
                <div class="header-top">
                    <button class="back-btn" onclick="goBack()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
                    </button>
                    <div class="header-meal-info">
                        <img src="img/sol.svg" alt="Sol" class="header-svg-icon">
                        <div>
                            <div class="header-meal-name">Almoço</div>
                            <div class="header-meal-sub">RU UFCA • 11:00 às 14:00</div>
                        </div>
                    </div>
                </div>
                <div class="day-scroller" id="days-almoco"></div>
            </div>
        </div>
        <div class="detail-body-container">
            <div class="detail-body" id="body-almoco"></div>
        </div>
    </div><div class="screen screen-detail" id="screen-jantar">
        <div class="detail-header jantar-header">
            <div class="header-top-container">
                <div class="header-top">
                    <button class="back-btn jantar-back" onclick="goBack()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
                    </button>
                    <div class="header-meal-info">
                        <img src="img/lua.svg" alt="Lua" class="header-svg-icon">
                        <div>
                            <div class="header-meal-name">Jantar</div>
                            <div class="header-meal-sub">RU UFCA • 17:00 às 19:40</div>
                        </div>
                    </div>
                </div>
                <div class="day-scroller" id="days-jantar"></div>
            </div>
        </div>
        <div class="detail-body-container">
            <div class="detail-body" id="body-jantar"></div>
        </div>
    </div></div><script>{_js(json_data)}</script>
</body>
</html>"""

def _clock_svg(color: str) -> str:
    return (
        f'<svg class="icon-clock" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        f'<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
    )

def _css() -> str:
    return """
/* ── Reset ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
    --bg:        #121216;
    --surface:   #1c1c24;
    --surface2:  #252530;
    --border:    rgba(255,255,255,0.06);
    --text:      #f0f0f5;
    --muted:     #9e9ea7;
    --font-ui:   'Nunito', system-ui, sans-serif;
    --font-main: 'Montserrat', sans-serif;
    --orange: #f97902;
    --orange-light: #ffc700;
    --blue: #2464D2;
    --blue-light: #4BA1FF;
    --dur:       350ms;
    --ease:      cubic-bezier(0.4, 0, 0.2, 1);
}

html, body {
    height: 100%;
    overflow: hidden;
    background: var(--bg);
    font-family: var(--font-ui);
    color: var(--text);
    -webkit-tap-highlight-color: transparent;
}

.router { position: relative; width: 100%; height: 100dvh; overflow: hidden; }

.screen {
    position: absolute; inset: 0; width: 100%; height: 100%; overflow: hidden;
    transform: translateX(100%);
    transition: transform var(--dur) var(--ease), opacity var(--dur) var(--ease);
    opacity: 0; pointer-events: none;
    display: flex; flex-direction: column;
}
.screen.active { transform: translateX(0); opacity: 1; pointer-events: auto; }
.screen.exit-left { transform: translateX(-30%); opacity: 0; pointer-events: none; }

/* ══════════════════════════════════════
   TELA HOME
   ══════════════════════════════════════ */
#screen-home { background: var(--bg); }

/* ── HEADER HOME ── */
.home-header {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    width: 100%; height: clamp(100px, 12vh, 140px);
    font-family: var(--font-main);
}

.home-title {
    font-size: clamp(22px, 5vw, 30px);
    font-weight: 800; color: #ffffff; line-height: 1.2; text-align: center;
}

.home-sub {
    font-size: clamp(16px, 4vw, 22px);
    font-weight: 700; color: #cccccc; margin-top: 4px;
}

.home-wrap-scroll {
    flex: 1; overflow-y: auto; display: flex; flex-direction: column; align-items: center;
    padding: clamp(30px, 5vh, 50px) 20px 40px;
}

/* ── CARDS (PILLS) ── */
.home-pills {
    display: flex; flex-direction: column; align-items: center;
    gap: 30px; width: 100%; max-width: 600px;
}

.pill {
    display: flex; flex-direction: row; align-items: center;
    width: 100%; max-width: 600px;
    aspect-ratio: 3 / 1; 
    border: none; border-radius: clamp(20px, 4vw, 32px);
    padding: 0; cursor: pointer;
    font-family: var(--font-main);
    transition: transform 0.15s, filter 0.15s; outline: none;
}
.pill:hover  { transform: translateY(-3px); filter: brightness(1.05); }
.pill:active { transform: scale(0.97); }

.almoco-pill {
    background: linear-gradient(135deg, var(--orange), var(--orange-light));
    box-shadow: 0 10px 30px rgba(249, 121, 2, 0.3); 
}

.jantar-pill {
    background: linear-gradient(135deg, var(--blue), var(--blue-light));
    box-shadow: 0 10px 30px rgba(36, 100, 210, 0.3);
}

/* Card Branco lateral */
.pill-icon-wrapper {
    width: 41.66%;
    height: 100%;
    background: #ffffff;
    border-radius: clamp(20px, 4vw, 32px);
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}

.pill-icon-img {
    width: clamp(60px, 20vw, 150px);
    height: clamp(60px, 20vw, 150px);
    object-fit: contain;
}

.pill-info {
    flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center;
}

.pill-name { font-size: clamp(28px, 6vw, 46px); font-weight: 900; line-height: 1; }
.pill-time {
    font-size: clamp(14px, 3vw, 19px); font-weight: 700; margin-top: 8px;
    display: flex; align-items: center; gap: 8px;
}
.icon-clock { width: clamp(14px, 3vw, 19px); height: clamp(14px, 3vw, 19px); }

.almoco-info { color: #000000; }
.jantar-info { color: #ffffff; }

.home-footer {
    font-family: var(--font-ui);
    font-size: clamp(14px, 3.5vw, 18px);
    color: #ffffff;
    font-weight: 600;
    margin-top: 30px; 
    margin-bottom: 20px;
    opacity: 0.8;
}

/* ══════════════════════════════════════
   TELA DETALHE (Almoço / Jantar)
   ══════════════════════════════════════ */
.screen-detail { background: var(--bg); }

.detail-header {
    flex-shrink: 0; background: var(--surface);
    border-bottom: 1px solid var(--border);
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    z-index: 10;
}

.header-top-container { width: 100%; max-width: 800px; margin: 0 auto; }

.header-top { display: flex; align-items: center; gap: 20px; padding: 24px 24px 16px; }

.back-btn {
    width: 46px; height: 46px; border-radius: 14px;
    border: 1px solid var(--border); background: var(--surface2); color: var(--text);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; flex-shrink: 0; transition: background 0.15s;
}
.back-btn:active { transform: scale(0.92); }
.back-btn svg { width: 22px; height: 22px; }

.header-meal-info { display: flex; align-items: center; gap: 16px; }
.header-svg-icon { width: 42px; height: 42px; object-fit: contain; }

.header-meal-name { font-family: var(--font-main); font-size: 1.6rem; font-weight: 900; line-height: 1.1; }
.header-meal-sub { font-size: 0.85rem; font-weight: 600; color: var(--muted); margin-top: 2px; }

.almoco-header .header-meal-name { color: var(--orange-light); }
.jantar-header  .header-meal-name { color: var(--blue-light); }

.day-scroller {
    display: flex; justify-content: space-between; gap: 6px; padding: 10px 24px 20px;
}

.day-chip {
    flex: 1; min-width: 0;
    background: var(--surface2); border: 2px solid transparent;
    border-radius: 12px; color: var(--muted); font-family: var(--font-ui);
    padding: 10px 2px; cursor: pointer; display: flex; flex-direction: column;
    align-items: center; gap: 2px; transition: all 0.2s ease;
}
.day-chip .chip-day  { font-size: clamp(0.6rem, 2.5vw, 0.75rem); letter-spacing: 0px; font-weight: 800; }
.day-chip .chip-date { font-size: clamp(0.7rem, 3vw, 0.95rem); font-weight: 900; }

.almoco-header .day-chip.active {
    background: linear-gradient(135deg, var(--orange), var(--orange-light));
    color: #000; box-shadow: 0 4px 12px rgba(249, 121, 2, 0.3);
}
.jantar-header .day-chip.active {
    background: linear-gradient(135deg, var(--blue), var(--blue-light));
    color: #fff; box-shadow: 0 4px 12px rgba(36, 100, 210, 0.3);
}

/* Corpo e Cards das Categorias */
.detail-body-container { flex: 1; overflow-y: auto; }

/* Aumentado o padding-top para compensar a remoção do day-label */
.detail-body { width: 100%; max-width: 800px; margin: 0 auto; padding: 24px 0 60px; }

.cat-block {
    background: var(--surface);
    border-radius: 20px;
    padding: 20px 24px;
    margin: 0 20px 20px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.25);
    border: 1px solid rgba(255,255,255,0.03);
}

.cat-title {
    font-family: var(--font-main);
    font-size: 0.85rem; font-weight: 800; letter-spacing: 1.5px;
    text-transform: uppercase; margin-bottom: 14px;
    display: flex; align-items: center;
}
.almoco-body .cat-title { color: var(--orange-light); }
.jantar-body .cat-title  { color: var(--blue-light); }

.food-item {
    display: block; font-size: 1.1rem; font-weight: 600; color: #E2E2EA;
    line-height: 1.5; padding: 10px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}
.food-item:last-child { border-bottom: none; padding-bottom: 0; }
.food-item:first-of-type { padding-top: 0; }

.empty { text-align: center; padding: 60px 30px; color: var(--muted); font-size: 1.1rem; font-style: italic; }

/* ══════════════════════════════════════
   DESKTOP RESPONSIVE (> 900px)
   ══════════════════════════════════════ */
@media (min-width: 900px) {
    .home-wrap-scroll { justify-content: center; padding: 40px; }
    .home-header { height: 160px; }
    .home-pills { flex-direction: row; justify-content: center; max-width: 1000px; gap: 40px; }
    .pill { max-width: 480px; aspect-ratio: 2.5 / 1; }
    .home-footer { margin-top: 50px; font-size: 18px; }
    
    .cat-block { margin: 0 30px 24px; padding: 24px 30px; }
}
"""

def _js(json_data: str) -> str:
    return f"""
const DATA = {json_data};

// MUDANÇA AQUI: "Proteína" no lugar de "Principal"
const ORDEM = [
    "Proteína","Vegetariano","Sopas","Guarnição",
    "Acompanhamentos","Saladas","Suco","Sobremesa"
];
const ABREV = ["SEG","TER","QUA","QUI","SEX"];

const state = {{ almoco: 0, jantar: 0 }};

/* ── Hash Routing para navegação nativa do dispositivo ── */
function handleHashChange() {{
    let hash = window.location.hash.replace('#', '') || 'home';
    if (!['home', 'almoco', 'jantar'].includes(hash)) hash = 'home';
    
    const prevs = document.querySelectorAll('.screen.active');
    const next = document.getElementById('screen-' + hash);
    
    prevs.forEach(prev => {{
        if (prev.id !== 'screen-' + hash) {{
            if (hash === 'home') {{
                prev.classList.remove('active'); 
            }} else {{
                prev.classList.add('exit-left'); 
            }}
        }}
    }});
    
    next.classList.add('active');
    next.classList.remove('exit-left');
    
    if (hash === 'almoco') renderDetail('almoco', state.almoco);
    if (hash === 'jantar') renderDetail('jantar', state.jantar);
}}

window.addEventListener('hashchange', handleHashChange);

function goTo(id) {{
    window.location.hash = id;
}}

function goBack() {{
    window.history.back();
    setTimeout(() => {{
        if (window.location.hash !== '#home' && window.location.hash !== '') {{
            window.location.hash = 'home';
        }}
    }}, 100);
}}

function buildDayChips(tipo) {{
    const container = document.getElementById('days-' + tipo);
    container.innerHTML = '';

    ABREV.forEach((abrev, i) => {{
        const chip = document.createElement('button');
        chip.className = 'day-chip' + (i === state[tipo] ? ' active' : '');
        chip.innerHTML = `<span class="chip-day">${{abrev}}</span><span class="chip-date">${{DATA[i].data}}</span>`;
        chip.onclick = () => selectDay(tipo, i);
        container.appendChild(chip);
    }});
}}

function selectDay(tipo, idx) {{
    state[tipo] = idx;
    document.querySelectorAll('#days-' + tipo + ' .day-chip').forEach((c, i) => {{
        if(i === idx) c.classList.add('active');
        else c.classList.remove('active');
    }});
    renderBody(tipo, idx);
}}

function renderBody(tipo, idx) {{
    const dia   = DATA[idx];
    const dados = dia[tipo];
    const body  = document.getElementById('body-' + tipo);
    const bodyClass = tipo + '-body';

    // MUDANÇA AQUI: Título com nome do dia removido (let html inicia vazio)
    let html = '';

    let temConteudo = false;
    ORDEM.forEach(cat => {{
        if (dados[cat]?.length) {{
            temConteudo = true;
            html += `<div class="cat-block">
                <div class="cat-title">${{cat}}</div>
                ${{dados[cat].map(i => `<span class="food-item">${{i}}</span>`).join('')}}
            </div>`;
        }}
    }});

    if (!temConteudo) {{
        html += '<div class="empty">Nenhum cardápio disponível para este dia.</div>';
    }}

    body.className = 'detail-body ' + bodyClass;
    body.innerHTML = html;
    
    document.querySelector('.detail-body-container').scrollTo({{ top: 0, behavior: 'smooth' }});
}}

function renderDetail(tipo, idx) {{
    buildDayChips(tipo);
    renderBody(tipo, idx);
}}

(function init() {{
    const d = new Date().getDay();
    const hoje = (d === 0 || d === 6) ? 0 : d - 1;
    state.almoco = hoje;
    state.jantar  = hoje;

    if (!window.location.hash) {{
        history.replaceState(null, null, '#home');
    }}
    handleHashChange();
}}());
"""