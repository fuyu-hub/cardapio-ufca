/**
 * Vigia do cardápio — Cloudflare Worker com Cron Trigger.
 *
 * A cada 10 minutos baixa só a página de cardápios da UFCA (alguns KB),
 * pega o ID do PDF mais recente e compara com o último visto (guardado no KV).
 * Se mudou, dispara o workflow do GitHub, que roda o scraper e publica o site.
 *
 * Assim o GitHub Actions só roda quando há PDF novo, e cada PDF dispara
 * no máximo uma execução (sem enxurrada de e-mails se algo falhar).
 */

const URL_CARDAPIOS = "https://www.ufca.edu.br/assuntos-estudantis/refeitorio-universitario/cardapios/";
const WORKFLOW = "main.yml";
const CHAVE_KV = "ultimo_pdf";

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

export default {
  async scheduled(_evento, env, ctx) {
    ctx.waitUntil(
      verificar(env).catch((e) => {
        // Fica no log do Worker; não dispara nada, então não gera e-mail
        console.error(`Falha na verificação: ${e.message}`);
      }),
    );
  },

  // Consulta (somente leitura) do último PDF visto, para conferir se o vigia está vivo
  async fetch(_req, env) {
    const id = await env.ESTADO.get(CHAVE_KV);
    return Response.json({ ultimo_pdf: id });
  },
};
