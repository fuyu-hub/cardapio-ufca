/**
 * Vigia do cardápio — Cloudflare Worker.
 *
 * 1) Vigia (cron a cada 10 min): baixa só a página de cardápios da UFCA, pega o ID
 *    do PDF mais recente e, se mudou, dispara o workflow do GitHub (uma vez por PDF).
 *
 * 2) Lembretes (cron às 10:30 e 16:30 de Brasília, seg–sex): lê o cardápio do dia no
 *    site e envia uma notificação do navegador (Web Push) a quem se inscreveu,
 *    com a proteína do dia (ou a opção vegetariana em destaque, se a pessoa pediu).
 *
 * Rotas HTTP (chamadas pelo site):
 *   GET  /            status do vigia
 *   POST /inscrever   salva ou atualiza uma inscrição e manda uma notificação de confirmação
 *   POST /cancelar    remove uma inscrição
 *   POST /lote        uso interno: envia um lote de notificações (divide o trabalho)
 */

import { enviarPush, b64urlParaBytes } from "./webpush.js";

const URL_CARDAPIOS = "https://www.ufca.edu.br/assuntos-estudantis/refeitorio-universitario/cardapios/";
const WORKFLOW = "main.yml";
const CHAVE_KV = "ultimo_pdf";

const CRON_VIGIA = "*/10 * * * *";
const CRON_ALMOCO = "30 13 * * 1-5"; // 10:30 em Brasília
const CRON_JANTAR = "30 19 * * 1-5"; // 16:30 em Brasília

const REFEICOES = {
  almoco: { nome: "Almoço", abre: "11:00" },
  jantar: { nome: "Jantar", abre: "17:00" },
};

// Quantas notificações cada execução envia. Acima disso o trabalho é dividido em
// lotes, cada um numa execução própria. Medido: ~0,85 ms de CPU por notificação;
// o plano gratuito permite 10 ms de CPU por execução, então 8 deixa margem.
const TAMANHO_LOTE = 8;

// Serviços de push aceitos (Chrome/Android, Firefox, Edge/Windows, Safari/iPhone)
const SERVICOS_PUSH = [
  /^fcm\.googleapis\.com$/,
  /\.push\.services\.mozilla\.com$/,
  /\.notify\.windows\.com$/,
  /^web\.push\.apple\.com$/,
  /\.push\.apple\.com$/,
];

/* ══════════════════════════════ Vigia ══════════════════════════════ */

/** IDs (p=NNNN) dos links "Baixar documento" da página. */
export function idsDosPdfs(html) {
  const ids = [];
  const links = /<a\b[^>]*\bhref\s*=\s*["']([^"']*)["'][^>]*>([\s\S]*?)<\/a>/gi;
  for (const [, href, conteudo] of html.matchAll(links)) {
    const texto = conteudo.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().toLowerCase();
    if (!texto.includes("baixar documento")) continue;
    const m = href.match(/[?&;]p=(\d+)/);
    if (m) ids.push(Number(m[1]));
  }
  return ids;
}

async function ultimoIdNoSite() {
  const resp = await fetch(URL_CARDAPIOS, {
    headers: { "User-Agent": "Mozilla/5.0 (compatible; cardapio-ufca-vigia)" },
    signal: AbortSignal.timeout(20000),
  });
  if (!resp.ok) throw new Error(`Página de cardápios respondeu ${resp.status}`);
  const ids = idsDosPdfs(await resp.text());
  if (!ids.length) throw new Error("Nenhum link 'Baixar documento' encontrado (o site mudou?)");
  return String(Math.max(...ids));
}

async function dispararWorkflow(env, motivo) {
  const resp = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cardapio-ufca-vigia",
      },
      body: JSON.stringify({ ref: env.GITHUB_BRANCH || "main" }),
    },
  );
  if (resp.status !== 204) {
    throw new Error(`GitHub recusou o disparo (${resp.status}): ${await resp.text()}`);
  }
  console.log(`Workflow disparado: ${motivo}`);
}

async function verificar(env) {
  const atual = await ultimoIdNoSite();
  const anterior = await env.ESTADO.get(CHAVE_KV);
  if (atual === anterior) return { novo: false, id: atual };

  await dispararWorkflow(env, `PDF ${anterior ?? "(nenhum)"} → ${atual}`);
  // Só grava depois do disparo dar certo: se falhar, tenta de novo em 10 min
  await env.ESTADO.put(CHAVE_KV, atual);
  return { novo: true, id: atual };
}

/* ═════════════════════════════ Lembretes ═════════════════════════════ */

/** Data de hoje em Brasília (UTC−3, sem horário de verão). */
function hojeBrasilia(env) {
  if (env.HOJE_TESTE) return new Date(`${env.HOJE_TESTE}T12:00:00Z`);
  return new Date(Date.now() - 3 * 3600 * 1000);
}

function isoData(d) {
  return d.toISOString().slice(0, 10);
}

const limpar = (s) => String(s).replace(/\*+$/, "").trim();

/** Monta as duas versões da mensagem do dia (normal e com o vegetariano em destaque). */
export function montarMensagens(semanas, tipo, hoje) {
  const diaSemana = hoje.getUTCDay(); // 1 = segunda … 5 = sexta
  if (diaSemana < 1 || diaSemana > 5) return null;

  const segunda = new Date(hoje.getTime() - (diaSemana - 1) * 86400000);
  const refeicao = semanas[isoData(segunda)]?.[String(diaSemana - 1)]?.[tipo];
  const proteinas = (refeicao?.["Proteína"] || []).map(limpar).filter(Boolean);
  const vegetariano = (refeicao?.["Vegetariano"] || []).map(limpar).filter(Boolean);
  if (!proteinas.length && !vegetariano.length) return null; // sem cardápio: não avisa

  const { nome, abre } = REFEICOES[tipo];
  const titulo = `${nome} abre às ${abre}`;
  const prot = proteinas.join(" ou ");
  const veg = vegetariano.join(" ou ");

  const normal = [prot, veg && `Vegetariano: ${veg}`].filter(Boolean).join(" · ");
  const comVeg = veg ? [`Vegetariano: ${veg}`, prot && `Também: ${prot}`].filter(Boolean).join(" · ") : normal;
  return { titulo, normal, comVeg };
}

async function lerCardapio(env) {
  const resp = await fetch(`${env.SITE_URL}/cardapio.json`, { cf: { cacheTtl: 0 } });
  if (!resp.ok) throw new Error(`cardapio.json respondeu ${resp.status}`);
  return resp.json();
}

/** Envia para as chaves dadas; apaga inscrições que o serviço de push diz não existirem mais. */
async function enviarLote(env, chaves, tipo, msgs) {
  let entregues = 0, removidas = 0, falhas = 0;
  for (const chave of chaves) {
    const salvo = await env.ESTADO.get(chave, "json");
    if (!salvo) continue;
    const corpo = salvo.prefs?.vegetariano ? msgs.comVeg : msgs.normal;
    const payload = JSON.stringify({ title: msgs.titulo, body: corpo, url: `${env.SITE_URL}/#${tipo}`, tag: tipo });
    try {
      const status = await enviarPush(salvo.inscricao, payload, opcoesPush(env, 1800));
      if (status === 404 || status === 410) { await env.ESTADO.delete(chave); removidas++; }
      else if (status >= 200 && status < 300) entregues++;
      else { falhas++; console.error(`Push ${status} para ${chave}`); }
    } catch (e) {
      falhas++;
      console.error(`Falha no push para ${chave}: ${e.message}`);
    }
  }
  return { entregues, removidas, falhas };
}

function opcoesPush(env, ttl) {
  return { vapidPublico: env.VAPID_PUBLIC, vapidPrivado: env.VAPID_PRIVATE, assunto: env.SITE_URL, ttl };
}

async function lembrar(env, tipo) {
  const msgs = montarMensagens(await lerCardapio(env), tipo, hojeBrasilia(env));
  if (!msgs) {
    console.log(`Lembrete de ${tipo}: sem cardápio para hoje, nada enviado.`);
    return { enviado: false };
  }

  // Quem quer este lembrete (a preferência fica nos metadados da chave: não precisa ler cada valor)
  const chaves = [];
  let cursor;
  do {
    const pagina = await env.ESTADO.list({ prefix: "sub:", cursor });
    for (const k of pagina.keys) if (k.metadata?.[tipo]) chaves.push(k.name);
    cursor = pagina.list_complete ? undefined : pagina.cursor;
  } while (cursor);

  console.log(`Lembrete de ${tipo}: ${chaves.length} inscrito(s). "${msgs.titulo}: ${msgs.normal}"`);
  if (chaves.length <= TAMANHO_LOTE || !env.SELF || !env.LOTE_TOKEN) {
    return enviarLote(env, chaves, tipo, msgs);
  }

  // Muitos inscritos: cada lote roda numa execução própria do Worker
  const lotes = [];
  for (let i = 0; i < chaves.length; i += TAMANHO_LOTE) lotes.push(chaves.slice(i, i + TAMANHO_LOTE));
  await Promise.all(lotes.map((lote) => env.SELF.fetch("https://interno/lote", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Lote-Token": env.LOTE_TOKEN },
    body: JSON.stringify({ chaves: lote, tipo, msgs }),
  })));
  return { lotes: lotes.length };
}

/* ═══════════════════════════ Inscrições (HTTP) ═══════════════════════════ */

function cors(env, req) {
  const origem = req.headers.get("Origin") || "";
  const permitidas = [env.SITE_URL, ...(env.ORIGENS_TESTE || "").split(",").filter(Boolean)];
  return {
    "Access-Control-Allow-Origin": permitidas.includes(origem) ? origem : env.SITE_URL,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function json(dados, status, cabecalhos) {
  return new Response(JSON.stringify(dados), {
    status, headers: { "Content-Type": "application/json", ...cabecalhos },
  });
}

async function chaveDaInscricao(endpoint) {
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(endpoint));
  return "sub:" + [...new Uint8Array(hash)].slice(0, 16).map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Confere se a inscrição tem o formato certo e aponta para um serviço de push conhecido. */
export function validarInscricao(inscricao, env = {}) {
  if (!inscricao || typeof inscricao.endpoint !== "string" || inscricao.endpoint.length > 1000) return "endpoint inválido";
  let url;
  try { url = new URL(inscricao.endpoint); } catch { return "endpoint inválido"; }
  const teste = env.PERMITIR_PUSH_LOCAL && url.protocol === "http:" && url.hostname === "127.0.0.1";
  if (!teste && (url.protocol !== "https:" || !SERVICOS_PUSH.some((re) => re.test(url.hostname)))) {
    return "serviço de push não reconhecido";
  }
  try {
    if (b64urlParaBytes(inscricao.keys?.p256dh || "").length !== 65) return "chave p256dh inválida";
    if (b64urlParaBytes(inscricao.keys?.auth || "").length !== 16) return "chave auth inválida";
  } catch { return "chaves inválidas"; }
  return null;
}

async function inscrever(req, env, cab) {
  let dados;
  try { dados = await req.json(); } catch { return json({ erro: "JSON inválido" }, 400, cab); }
  const { endpoint, keys } = dados.inscricao || {};
  const inscricao = { endpoint, keys: { p256dh: keys?.p256dh, auth: keys?.auth } };
  const erro = validarInscricao(inscricao, env);
  if (erro) return json({ erro }, 400, cab);

  const prefs = {
    almoco: !!dados.prefs?.almoco,
    jantar: !!dados.prefs?.jantar,
    vegetariano: !!dados.prefs?.vegetariano,
  };
  const chave = await chaveDaInscricao(inscricao.endpoint);
  if (!prefs.almoco && !prefs.jantar) {
    await env.ESTADO.delete(chave);
    return json({ ok: true, removida: true }, 200, cab);
  }
  await env.ESTADO.put(chave, JSON.stringify({ inscricao, prefs, em: new Date().toISOString() }), { metadata: prefs });

  // Confirmação imediata: também serve de teste de ponta a ponta
  const quais = [prefs.almoco && "almoço (10:30)", prefs.jantar && "jantar (16:30)"].filter(Boolean).join(" e ");
  const payload = JSON.stringify({
    title: "Lembretes ativados",
    body: `Você vai receber o cardápio do ${quais}, de segunda a sexta.`,
    url: `${env.SITE_URL}/`, tag: "confirmacao",
  });
  let status;
  try { status = await enviarPush(inscricao, payload, opcoesPush(env, 600)); }
  catch (e) { status = 0; console.error(`Confirmação falhou: ${e.message}`); }
  return json({ ok: true, push: status }, 200, cab);
}

async function cancelar(req, env, cab) {
  let dados;
  try { dados = await req.json(); } catch { return json({ erro: "JSON inválido" }, 400, cab); }
  if (typeof dados.endpoint !== "string") return json({ erro: "endpoint inválido" }, 400, cab);
  await env.ESTADO.delete(await chaveDaInscricao(dados.endpoint));
  return json({ ok: true }, 200, cab);
}

/* ═══════════════════════════════ Entrada ═══════════════════════════════ */

export default {
  async scheduled(evento, env, ctx) {
    const tarefa =
      evento.cron === CRON_ALMOCO ? lembrar(env, "almoco") :
      evento.cron === CRON_JANTAR ? lembrar(env, "jantar") :
      verificar(env);
    ctx.waitUntil(
      tarefa.catch((e) => {
        // Fica no log do Worker; não dispara nada, então não gera e-mail
        console.error(`Falha (${evento.cron}): ${e.message}`);
      }),
    );
  },

  async fetch(req, env) {
    const url = new URL(req.url);
    const cab = cors(env, req);

    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cab });

    if (req.method === "POST" && url.pathname === "/inscrever") return inscrever(req, env, cab);
    if (req.method === "POST" && url.pathname === "/cancelar") return cancelar(req, env, cab);

    if (req.method === "POST" && url.pathname === "/lote") {
      if (!env.LOTE_TOKEN || req.headers.get("X-Lote-Token") !== env.LOTE_TOKEN) {
        return new Response("Proibido", { status: 403 });
      }
      const { chaves, tipo, msgs } = await req.json();
      return json(await enviarLote(env, chaves, tipo, msgs), 200, {});
    }

    if (req.method === "GET" && url.pathname === "/") {
      // Consulta (somente leitura) do último PDF visto, para conferir se o vigia está vivo
      return json({ ultimo_pdf: await env.ESTADO.get(CHAVE_KV) }, 200, cab);
    }
    return new Response("Não encontrado", { status: 404, headers: cab });
  },
};
