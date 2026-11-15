# Vigia do cardápio (Cloudflare Worker)

Verifica a página de cardápios da UFCA a cada 10 minutos e, quando aparece um
PDF novo, dispara o workflow `Atualizar Cardápio Automaticamente` no GitHub.

Custo: cada verificação baixa só o HTML da página (sem PDF, sem Python) e roda
em milissegundos. São ~144 execuções por dia, dentro do plano gratuito do
Cloudflare Workers. O GitHub Actions só roda quando há PDF novo.

## Configuração (uma vez)

1. **Token do GitHub**: em GitHub → Settings → Developer settings →
   *Fine-grained personal access tokens*, crie um token com acesso **só** ao
   repositório `cardapio-ufca` e a permissão **Actions: Read and write**.

2. **Login no Cloudflare** (mesma conta do Cloudflare Pages):

   ```bash
   cd worker
   npx wrangler login
   ```

3. **Criar o KV** que guarda o último PDF visto e colar o `id` em `wrangler.toml`:

   ```bash
   npx wrangler kv namespace create ESTADO
   ```

4. **Guardar o token como segredo** (cole o token quando pedir):

   ```bash
   npx wrangler secret put GITHUB_TOKEN
   ```

5. **Publicar**:

   ```bash
   npx wrangler deploy
   ```

## Conferir se está funcionando

- Abrir a URL do Worker (mostrada no deploy) retorna `{"ultimo_pdf": "…"}`.
- Logs em tempo real: `npx wrangler tail`.
- No primeiro ciclo após o deploy ele dispara o workflow uma vez (ainda não
  tinha nenhum PDF registrado). Depois, só quando o ID do PDF mudar.

Se o GitHub recusar o disparo (token vencido, por exemplo), o ID não é gravado
e ele tenta de novo no ciclo seguinte; o erro aparece no `wrangler tail`.
