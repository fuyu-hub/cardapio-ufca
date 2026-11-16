/**
 * Web Push sem dependências, só com WebCrypto (roda no Cloudflare Workers e no Node).
 *
 *  - Criptografia do conteúdo: RFC 8291 (aes128gcm)
 *  - Autenticação do remetente: RFC 8292 (VAPID, JWT ES256)
 */

const enc = new TextEncoder();

export function b64urlParaBytes(s) {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4);
  const bin = atob(b64);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

export function bytesParaB64url(bytes) {
  let bin = "";
  for (const b of new Uint8Array(bytes)) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function concatenar(...partes) {
  const total = partes.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(total);
  let i = 0;
  for (const p of partes) { out.set(p, i); i += p.length; }
  return out;
}

async function hkdf(salt, ikm, info, bytes) {
  const chave = await crypto.subtle.importKey("raw", ikm, "HKDF", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "HKDF", hash: "SHA-256", salt, info }, chave, bytes * 8);
  return new Uint8Array(bits);
}

/**
 * Criptografa `payload` para a inscrição (RFC 8291).
 * `fixo` (opcional, só para teste) = { salt, asPrivado: JWK, asPublico: bytes }.
 */
export async function criptografar(payload, p256dh, auth, fixo) {
  const uaPublico = b64urlParaBytes(p256dh);
  const segredo = b64urlParaBytes(auth);
  const salt = fixo?.salt ?? crypto.getRandomValues(new Uint8Array(16));

  let asPrivado, asPublico;
  if (fixo) {
    asPrivado = await crypto.subtle.importKey("jwk", fixo.asPrivado, { name: "ECDH", namedCurve: "P-256" }, false, ["deriveBits"]);
    asPublico = fixo.asPublico;
  } else {
    const par = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
    asPrivado = par.privateKey;
    asPublico = new Uint8Array(await crypto.subtle.exportKey("raw", par.publicKey));
  }

  const uaChave = await crypto.subtle.importKey("raw", uaPublico, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const compartilhado = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: uaChave }, asPrivado, 256));

  const ikm = await hkdf(segredo, compartilhado, concatenar(enc.encode("WebPush: info\0"), uaPublico, asPublico), 32);
  const cek = await hkdf(salt, ikm, enc.encode("Content-Encoding: aes128gcm\0"), 16);
  const nonce = await hkdf(salt, ikm, enc.encode("Content-Encoding: nonce\0"), 12);

  const texto = concatenar(typeof payload === "string" ? enc.encode(payload) : payload, new Uint8Array([2]));
  const chaveAes = await crypto.subtle.importKey("raw", cek, "AES-GCM", false, ["encrypt"]);
  const cifrado = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, chaveAes, texto));

  const rs = new Uint8Array([0, 0, 0x10, 0]); // 4096
  return concatenar(salt, rs, new Uint8Array([asPublico.length]), asPublico, cifrado);
}

/** Cabeçalho Authorization do VAPID para o serviço de push do `endpoint`. */
export async function cabecalhoVapid(endpoint, vapidPublico, vapidPrivadoD, assunto) {
  const pub = b64urlParaBytes(vapidPublico);
  const jwk = {
    kty: "EC", crv: "P-256", d: vapidPrivadoD,
    x: bytesParaB64url(pub.slice(1, 33)), y: bytesParaB64url(pub.slice(33, 65)), ext: true,
  };
  const chave = await crypto.subtle.importKey("jwk", jwk, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const cab = bytesParaB64url(enc.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const corpo = bytesParaB64url(enc.encode(JSON.stringify({
    aud: new URL(endpoint).origin,
    exp: Math.floor(Date.now() / 1000) + 12 * 3600,
    sub: assunto,
  })));
  const assinatura = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, chave, enc.encode(`${cab}.${corpo}`));
  return `vapid t=${cab}.${corpo}.${bytesParaB64url(assinatura)}, k=${vapidPublico}`;
}

/**
 * Envia uma notificação. Retorna o status HTTP do serviço de push
 * (201 = entregue à fila; 404/410 = inscrição não existe mais).
 */
export async function enviarPush(inscricao, payload, { vapidPublico, vapidPrivado, assunto, ttl = 3600 }) {
  const corpo = await criptografar(payload, inscricao.keys.p256dh, inscricao.keys.auth);
  const resp = await fetch(inscricao.endpoint, {
    method: "POST",
    headers: {
      Authorization: await cabecalhoVapid(inscricao.endpoint, vapidPublico, vapidPrivado, assunto),
      "Content-Encoding": "aes128gcm",
      "Content-Type": "application/octet-stream",
      TTL: String(ttl),
      Urgency: "normal",
    },
    body: corpo,
  });
  return resp.status;
}
