import requests
from bs4 import BeautifulSoup
import pdfplumber
import pandas as pd
import io
import re
import os
from datetime import datetime, timedelta

from visual import gerar_html

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

# ── Validação da Semana Atual ────────────────────────────────────────────────
def validar_semana_atual(dados):
    hoje = datetime.now()
    
    if hoje.weekday() >= 5:
        hoje += timedelta(days=7 - hoje.weekday())
        
    segunda = hoje - timedelta(days=hoje.weekday())
    dias_esperados = [(segunda + timedelta(days=i)).strftime("%d") for i in range(5)]
    dias_pdf = [str(dados[i]["data"]) for i in range(5) if dados[i]["data"]]
    
    for dia_esperado in dias_esperados:
        for dia_pdf in dias_pdf:
            if dia_esperado in dia_pdf:
                return True
                
    return False

# ── Estrutura os dados brutos ────────────────────────────────────────────────
def extrair_dados_estruturados(df):
    semana = {
        0: {"dia_nome": "Segunda-feira", "data": "", "almoco": {}, "jantar": {}},
        1: {"dia_nome": "Terça-feira",   "data": "", "almoco": {}, "jantar": {}},
        2: {"dia_nome": "Quarta-feira",  "data": "", "almoco": {}, "jantar": {}},
        3: {"dia_nome": "Quinta-feira",  "data": "", "almoco": {}, "jantar": {}},
        4: {"dia_nome": "Sexta-feira",   "data": "", "almoco": {}, "jantar": {}},
    }

    # Procura as datas nas primeiras 3 linhas para garantir
    for _, row in df.head(3).iterrows():
        for i in range(1, 6):
            if i < len(row):
                cell = str(row.iloc[i]).lower()
                match = re.search(r"\b(\d{1,2}/[a-z]{3})\b", cell)
                if match and not semana[i-1]["data"]:
                    semana[i-1]["data"] = match.group(1)

    refeicao_atual  = "almoco"
    categoria_atual = ""

    for _, row in df.iterrows():
        col0 = str(row.iloc[0]).strip().upper()

        # ASSUME PROTEÍNA COMO PADRÃO: Se a linha for o cabeçalho, qualquer comida solta já será Proteína
        if "ALMOÇO" in col0:
            refeicao_atual = "almoco"
            categoria_atual = "Proteína"
        elif "JANTAR" in col0:
            refeicao_atual = "jantar"
            categoria_atual = "Proteína"

        cat_detectada = ""
        if col0 and col0 not in ["NAN", "NONE", ""]:
            if   "PRINCIPAL"      in col0: cat_detectada = "Proteína"
            elif "PROTE"          in col0: cat_detectada = "Proteína"
            elif "VEGETARIANO"    in col0: cat_detectada = "Vegetariano"
            elif "SALADA"         in col0: cat_detectada = "Saladas"
            elif "GUARNI"         in col0: cat_detectada = "Guarnição"
            elif "ACOMPANHAMEN"   in col0: cat_detectada = "Acompanhamentos"
            elif "SUCO"           in col0: cat_detectada = "Suco"
            elif "SOBREMESA"      in col0: cat_detectada = "Sobremesa"
            elif "SOPA"           in col0: cat_detectada = "Sopas"

        if cat_detectada:
            categoria_atual = cat_detectada

        if not categoria_atual:
            continue

        categorias_longas = ["Proteína", "Vegetariano", "Saladas", "Sopas"]

        for i in range(5):
            if i + 1 < len(row):
                val = str(row.iloc[i + 1]).strip()
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
def processar_pdf(arquivo_pdf):
    config = {"vertical_strategy": "lines", "horizontal_strategy": "lines", "intersection_y_tolerance": 15}
    with pdfplumber.open(arquivo_pdf) as pdf:
        tabela = pdf.pages[0].extract_table(config)

    if not tabela: return None

    tabela = [linha for linha in tabela if any(c for c in linha)]
    df = pd.DataFrame(tabela)
    df = df.astype(str).replace("None", "", regex=False).replace(r"[\n\r]+", "<br>", regex=True)

    return extrair_dados_estruturados(df)

# ── Ponto de entrada ─────────────────────────────────────────────────────────
def atualizar_cardapio():
    USAR_PDF_LOCAL = False
    NOME_PDF_LOCAL = "CARDAPIO-UFCA-6-A-10-ABRIL-2026.pdf"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # Modo Local
    if USAR_PDF_LOCAL:
        print(f"Modo local: lendo '{NOME_PDF_LOCAL}'")
        if not os.path.exists(NOME_PDF_LOCAL): return
        with open(NOME_PDF_LOCAL, "rb") as f:
            dados = processar_pdf(io.BytesIO(f.read()))
            
        if dados and validar_semana_atual(dados):
            gerar_html(dados)
        else:
            print("❌ Arquivo local tem datas incorretas.")
        return

    # Modo Online
    url = "https://www.ufca.edu.br/assuntos-estudantis/refeitorio-universitario/cardapios/"
    print(f"Acessando: {url}")
    try:
        soup = BeautifulSoup(requests.get(url, headers=headers).text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            if "baixar documento" in a.get_text(strip=True).lower():
                href = a["href"]
                full = href if href.startswith("http") else "https://www.ufca.edu.br" + href
                pid  = int(m.group(1)) if (m := re.search(r"p=(\d+)", full)) else 0
                links.append({"url": full, "id": pid})

        if not links:
            print("❌ Botão 'Baixar documento' não encontrado.")
            return

        links.sort(key=lambda x: x["id"], reverse=True)
        pdf_url = links[0]["url"]
        print(f"Baixando PDF mais recente...")

        dados = processar_pdf(io.BytesIO(requests.get(pdf_url, headers=headers).content))
        
        if dados:
            if validar_semana_atual(dados):
                print("✅ O PDF corresponde à semana atual. Atualizando site...")
                gerar_html(dados)
            else:
                print("⚠️ O PDF ainda é o da semana passada. Abortando atualização.")
        else:
            print("❌ Nenhuma tabela legível encontrada.")

    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    atualizar_cardapio()