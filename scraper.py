import requests
from bs4 import BeautifulSoup
import pdfplumber
import pandas as pd
import io

def atualizar_cardapio():
    url = "https://www.ufca.edu.br/assuntos-estudantis/refeitorio-universitario/cardapios/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    print(f"Acedendo ao site: {url}")
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    pdf_urls = []
    print("A procurar os botões 'Baixar documento'...")
    
    # Procura por todos os links na página
    for link in soup.find_all('a', href=True):
        texto = link.get_text(strip=True).lower()
        href = link['href']
        
        # Se for um botão de descarregar, guarda-o na nossa lista
        if 'baixar documento' in texto:
            if href.startswith('http') or href.startswith('/'):
                url_completa = href
                if url_completa.startswith('/'):
                    url_completa = "https://www.ufca.edu.br" + url_completa
                
                pdf_urls.append(url_completa)
            
    if not pdf_urls:
        print("❌ ERRO: O botão 'Baixar documento' não foi encontrado na página.")
        return

    # --- A CORREÇÃO ESTÁ AQUI ---
    # Em vez de pegar o primeiro, pegamos o último [-1] da lista, que é o mais recente
    pdf_url = pdf_urls[-1]
    print(f"✅ Foram encontrados {len(pdf_urls)} cardápios. O mais recente escolhido foi: {pdf_url}")
    print("A descarregar e a ler o ficheiro...")
    
    try:
        pdf_response = requests.get(pdf_url, headers=headers)
        
        with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
            pagina = pdf.pages[0] 
            tabela_extraida = pagina.extract_table()
            
        if tabela_extraida:
            print("✅ Tabela extraída com sucesso! A iniciar a limpeza dos dados...")
            
            tabela_limpa = [linha for linha in tabela_extraida if any(celula for celula in linha)]
            df = pd.DataFrame(tabela_limpa[1:], columns=tabela_limpa[0])
            
            df = df.astype(str)
            df = df.replace('None', '', regex=False)
            df = df.replace(r'\n', '<br>', regex=True)
            df.columns = [str(col).replace('None', '').replace('\n', '<br>') for col in df.columns]
            
            tabela_html = df.to_html(index=False, escape=False, classes='table table-striped table-hover table-bordered text-center align-middle')
            
            html_completo = f"""
            <!DOCTYPE html>
            <html lang="pt-BR">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Cardápio da Semana - RU UFCA</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
                <style>
                    body {{ background-color: #f8f9fa; padding: 20px; font-size: 14px; }}
                    .container {{ background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 95%; }}
                    thead {{ background-color: #005b96; color: white; vertical-align: middle; }}
                    th, td {{ padding: 12px !important; vertical-align: middle; }}
                </style>
            </head>
            <body>
                <div class="container mt-4">
                    <h2 class="mb-4 text-center" style="color: #005b96;">Cardápio da Semana - RU UFCA</h2>
                    <div class="table-responsive">
                        {tabela_html}
                    </div>
                    <p class="text-muted text-center mt-4"><small>Atualizado automaticamente. Sistema não oficial.</small></p>
                </div>
            </body>
            </html>
            """
            
            with open('index.html', 'w', encoding='utf-8') as f:
                f.write(html_completo)
            print("✅ Site gerado, limpo e formatado com sucesso!")
        else:
            print("❌ ERRO: Nenhuma tabela legível encontrada.")
            
    except Exception as e:
        print(f"❌ ERRO ao tentar descarregar ou ler o ficheiro: {e}")

if __name__ == '__main__':
    atualizar_cardapio()
