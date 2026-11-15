import argparse
import io
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

import pdfplumber
import requests
from bs4 import BeautifulSoup

from visual import gerar_html

URL_CARDAPIOS = "https://www.ufca.edu.br/assuntos-estudantis/refeitorio-universitario/cardapios/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMEOUT = 30  # segundos
ARQUIVO_DADOS = "cardapio.json"  # semanas já lidas, por segunda-feira (AAAA-MM-DD)
PDFS_RECENTES = 3  # quantos PDFs do topo da lista verificar (atual + próxima + folga)

# Horário de Brasília (sem horário de verão desde 2019). O runner do Actions roda em UTC.
FUSO_BRASILIA = timezone(timedelta(hours=-3))


class ErroScraper(Exception):
    """Falha que deve deixar o workflow vermelho (site mudou, PDF ilegível...)."""


# ── Função para padronizar o texto do cardápio ───────────────────────────────
def formatar_texto(texto):
    excecoes = {"de", "da", "do", "das", "dos", "com", "ao", "aos", "à", "às", "a", "e", "ou", "em", "no", "na"}

    # Remove tudo que não for letra ou número no INÍCIO da frase (ex: "* ", "- ")
    texto = re.sub(r'^[^a-zA-ZÀ-ÿ0-9]+', '', texto)

    texto = re.sub(r'\s+', ' ', texto).strip()
    palavras = texto.split()
    resultado = []

    for i, p in enumerate(palavras):
        sufixo = ""
        # Preserva um asterisco no final da palavra, se houver (útil para avisos)
        if p.endswith("*"):
            sufixo = "*"
            p = p[:-1]

        p_lower = p.lower()
        if i > 0 and p_lower in excecoes:
            p_formatado = p_lower
        elif len(p_lower) > 0:
            p_formatado = p_lower.capitalize()
        else:
            p_formatado = ""

        resultado.append(p_formatado + sufixo)

    return " ".join(resultado).strip()

# ── Datas e semanas ──────────────────────────────────────────────────────────
MESES_PT = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
            "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def hoje_brasilia():
    return datetime.now(FUSO_BRASILIA).date()


def segunda_de(d):
    return d - timedelta(days=d.weekday())


def interpretar_data(texto, referencia):
    """Converte '9/nov' em date, escolhendo o ano mais próximo da referência
    (o PDF não traz o ano; isso resolve a virada dez→jan)."""
    m = re.fullmatch(r"(\d{1,2})/([a-z]{3})", str(texto).strip().lower())
    if not m or m.group(2) not in MESES_PT:
        return None
    candidatas = []
    for ano in (referencia.year - 1, referencia.year, referencia.year + 1):
        try:
            candidatas.append(date(ano, MESES_PT[m.group(2)], int(m.group(1))))
        except ValueError:
            pass
    return min(candidatas, key=lambda d: abs(d - referencia), default=None)


def segunda_do_cardapio(dados, referencia):
    """Segunda-feira da semana do PDF, a partir da primeira data legível."""
    for i in range(5):
        d = interpretar_data(dados[i]["data"], referencia)
        if d:
            segunda = d - timedelta(days=i)
            return segunda if segunda.weekday() == 0 else None
    return None

# ── Estrutura os dados brutos ────────────────────────────────────────────────
def extrair_dados_estruturados(tabela):
    """Recebe a tabela como lista de linhas (listas de str) e monta a semana."""
    semana = {
        0: {"dia_nome": "Segunda-feira", "data": "", "almoco": {}, "jantar": {}},
        1: {"dia_nome": "Terça-feira",   "data": "", "almoco": {}, "jantar": {}},
        2: {"dia_nome": "Quarta-feira",  "data": "", "almoco": {}, "jantar": {}},
        3: {"dia_nome": "Quinta-feira",  "data": "", "almoco": {}, "jantar": {}},
        4: {"dia_nome": "Sexta-feira",   "data": "", "almoco": {}, "jantar": {}},
    }

    # Procura as datas em todas as linhas para garantir
    for row in tabela:
        for i in range(1, 6):
            if i < len(row):
                cell = row[i].lower()
                match = re.search(r"\b(\d{1,2}/[a-z]{3})\b", cell)
                if match and not semana[i-1]["data"]:
                    semana[i-1]["data"] = match.group(1)

    refeicao_atual  = "almoco"
    categoria_atual = ""

    for row in tabela:
        col0 = row[0].strip().upper()
        col0_clean = re.sub(r'[^A-Z]', '', col0)

        # ASSUME PROTEÍNA COMO PADRÃO: Se a linha for o cabeçalho, qualquer comida solta já será Proteína
        if "ALMOÇO" in col0 or "ALMOCO" in col0:
            refeicao_atual = "almoco"
            categoria_atual = "Proteína"
        elif "JANTAR" in col0:
            refeicao_atual = "jantar"
            categoria_atual = "Proteína"

        cat_detectada = ""
        if col0_clean:
            if   "PRINCIPAL" in col0_clean: cat_detectada = "Proteína"
            elif "PROTE"     in col0_clean: cat_detectada = "Proteína"
            elif "VEGETARI"  in col0_clean: cat_detectada = "Vegetariano"
            elif "SALADA"    in col0_clean: cat_detectada = "Saladas"
            elif "GUARNI"    in col0_clean: cat_detectada = "Guarnição"
            elif "ACOMPANHA" in col0_clean or "COMPANHA" in col0_clean: cat_detectada = "Acompanhamentos"
            elif "SUCO"      in col0_clean: cat_detectada = "Suco"
            elif "SOBREMESA" in col0_clean: cat_detectada = "Sobremesa"
            elif "SOPA"      in col0_clean: cat_detectada = "Sopas"

        if cat_detectada:
            categoria_atual = cat_detectada

        if not categoria_atual:
            continue

        # Evita herdar a categoria em linhas que na verdade contêm datas (como a linha de cabeçalho intermediária)
        is_date_row = False
        for val in row[1:6]:
            if re.search(r"\b(\d{1,2}/[a-z]{3})\b", val.lower()):
                is_date_row = True
                break
        if is_date_row:
            continue

        categorias_longas = ["Proteína", "Vegetariano", "Saladas", "Sopas"]

        for i in range(5):
            if i + 1 < len(row):
                val = row[i + 1].strip()
                if val and val.upper() not in ["NAN", "NONE", ""]:
                    if categoria_atual not in semana[i][refeicao_atual]:
                        semana[i][refeicao_atual][categoria_atual] = []

                    val = val.replace("-<br>", "-")
                    linhas = val.split("<br>")
                    raw_items = []

                    for linha in linhas:
                        # Remove as sujeiras antes para ver se sobrou algo
                        linha = re.sub(r"\b\d{1,2}/([a-z]{3}|\d{1,2})\b", "", linha, flags=re.IGNORECASE)
                        linha = re.sub(r"\b(segunda|terça|quarta|quinta|sexta).*?feira\b", "", linha, flags=re.IGNORECASE)
                        linha = re.sub(r"\b(sábado|domingo)\b", "", linha, flags=re.IGNORECASE)
                        linha = re.sub(r"\b(almoço|almoco|jantar)\b", "", linha, flags=re.IGNORECASE)
                        linha = linha.strip()

                        if not linha or linha.isnumeric():
                            continue

                        # Ignorar observações / avisos / notas de rodapé
                        if re.search(r"\b(obs|observação|observações|alteração|alterações|dependendo|disponibilidade|estoque|produtos|dutos)\b", linha, flags=re.IGNORECASE):
                            continue

                        # Inteligência de agrupamento: se a linha começa com * ou -, é um prato novo
                        if re.match(r"^[\*\-]", linha) or not raw_items:
                            raw_items.append(linha)
                        else:
                            # Se não começar com asterisco, avaliamos se devemos agrupar
                            if categoria_atual in categorias_longas:
                                raw_items[-1] += " " + linha
                            else:
                                # Para arroz, feijão, guarnições (itens curtos), cada linha é tratada como prato independente
                                raw_items.append(linha)

                    for item in raw_items:
                        item_formatado = formatar_texto(item)
                        if item_formatado and (not semana[i][refeicao_atual][categoria_atual] or semana[i][refeicao_atual][categoria_atual][-1] != item_formatado):
                            semana[i][refeicao_atual][categoria_atual].append(item_formatado)

    return semana

# ── Lê o PDF e retorna os dados ──────────────────────────────────────────────
def _limpar_celula(celula):
    if celula is None or celula == "None":
        return ""
    return re.sub(r"[\n\r]+", "<br>", str(celula))


def processar_pdf(arquivo_pdf):
    config = {"vertical_strategy": "lines", "horizontal_strategy": "lines", "intersection_y_tolerance": 15}
    with pdfplumber.open(arquivo_pdf) as pdf:
        tabela = pdf.pages[0].extract_table(config)

    if not tabela:
        return None

    tabela = [[_limpar_celula(c) for c in linha] for linha in tabela if any(c for c in linha)]
    return extrair_dados_estruturados(tabela)

# ── Busca os PDFs mais recentes no site da UFCA ──────────────────────────────
def urls_pdfs_recentes(quantidade=PDFS_RECENTES):
    """Retorna [(id, url)] dos PDFs mais recentes, do mais antigo para o mais novo."""
    print(f"Acessando: {URL_CARDAPIOS}")
    resp = requests.get(URL_CARDAPIOS, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    links = {}
    for a in soup.find_all("a", href=True):
        if "baixar documento" in a.get_text(strip=True).lower():
            href = a["href"]
            full = href if href.startswith("http") else "https://www.ufca.edu.br" + href
            pid  = int(m.group(1)) if (m := re.search(r"p=(\d+)", full)) else 0
            links[pid] = full

    if not links:
        raise ErroScraper("Botão 'Baixar documento' não encontrado. O site da UFCA mudou?")

    return sorted(links.items())[-quantidade:]


def baixar_pdf(url):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return io.BytesIO(resp.content)


# ── Armazenamento das semanas ────────────────────────────────────────────────
def carregar_semanas():
    if not os.path.exists(ARQUIVO_DADOS):
        return {}
    with open(ARQUIVO_DADOS, encoding="utf-8") as f:
        return json.load(f)


def salvar_semanas(semanas):
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(semanas, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


# ── Ponto de entrada ─────────────────────────────────────────────────────────
def atualizar_cardapio(pdfs_locais=None, hoje=None):
    """Lê os PDFs, guarda a semana corrente e a próxima e regera o site.

    O site decide sozinho (pela data do aparelho) qual semana mostrar:
    a corrente até sexta e a próxima a partir de sábado.
    Lança ErroScraper se nenhum PDF puder ser lido.
    """
    hoje = hoje or hoje_brasilia()
    corrente = segunda_de(hoje)
    proxima = corrente + timedelta(days=7)
    aceitas = {corrente, proxima}

    if pdfs_locais:
        fontes = [(caminho, lambda c=caminho: c) for caminho in pdfs_locais]
    else:
        fontes = [(f"PDF {pid}", lambda u=url: baixar_pdf(u)) for pid, url in urls_pdfs_recentes()]

    semanas = carregar_semanas()
    lidos = 0
    # Do mais antigo para o mais novo: se a UFCA republicar uma semana corrigida, a versão nova vence
    for nome, abrir in fontes:
        try:
            dados = processar_pdf(abrir())
        except Exception as e:  # PDF corrompido ou fora do padrão: tenta os outros
            print(f"⚠️ {nome}: não foi possível ler ({e}).")
            continue
        if not dados:
            print(f"⚠️ {nome}: nenhuma tabela legível.")
            continue
        lidos += 1

        segunda = segunda_do_cardapio(dados, hoje)
        datas = ", ".join(dados[i]["data"] or "?" for i in range(5))
        if segunda in aceitas:
            rotulo = "corrente" if segunda == corrente else "próxima"
            print(f"✅ {nome}: semana {rotulo} ({datas}).")
            semanas[segunda.isoformat()] = dados
        else:
            print(f"   {nome}: ignorado ({datas}).")

    if lidos == 0:
        raise ErroScraper("Nenhum PDF pôde ser lido.")

    # Mantém só a semana anterior (para o aviso de atraso), a corrente e a próxima
    limite = (corrente - timedelta(days=7)).isoformat()
    recentes = {k: v for k, v in semanas.items() if k >= limite}
    if not recentes and semanas:
        # Cardápio atrasado há mais de uma semana: mantém ao menos o último publicado
        ultima = max(semanas)
        recentes = {ultima: semanas[ultima]}
    semanas = recentes
    if not semanas:
        raise ErroScraper("Nenhuma semana recente disponível para gerar o site.")

    salvar_semanas(semanas)
    gerar_html(semanas)
    return semanas


def main():
    # Evita erro com emojis/acentos no console do Windows
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Atualiza o cardápio do RU da UFCA.")
    parser.add_argument("--pdf", nargs="+", help="Lê PDFs locais em vez de baixar do site (para testes).")
    parser.add_argument("--hoje", type=date.fromisoformat, help="Simula a data de hoje (AAAA-MM-DD), para testes.")
    args = parser.parse_args()

    try:
        atualizar_cardapio(args.pdf, args.hoje)
    except (ErroScraper, requests.RequestException, OSError) as e:
        # Sai com erro para o GitHub Actions marcar a execução como falha
        print(f"❌ Erro: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
