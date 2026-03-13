import requests
from bs4 import BeautifulSoup
import pdfplumber
import pandas as pd
import io

def atualizar_cardapio():
    url = "https://www.ufca.edu.br/assuntos-estudantis/refeitorio-universitario/cardapios/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    # 1. Acessar a página da UFCA
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    # 2. Encontrar o link do PDF mais recente
    # Procuramos links que geralmente estão nos botões de download
    pdf_url = None
    for link in soup.find_all('a', href=True):
        if 'wp-content/uploads' in link['href'] and '.pdf' in link['href']:
            pdf_url = link['href']
            break # Pega o primeiro (que costuma ser o mais recente no topo)
            
    if not pdf_url:
        print("Link do cardápio em PDF não encontrado.")
        return

    # 3. Baixar o PDF em memória
    print(f"Baixando cardápio de: {pdf_url}")
    pdf_response = requests.get(pdf_url, headers=headers)
    
    # 4. Extrair a tabela do PDF
    with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
        pagina = pdf.pages[0] # O cardápio geralmente fica na primeira página
        tabela_extraida = pagina.extract_table()
        
    if tabela_extraida:
        # 5. Converter para DataFrame (Pandas)
        # Assumindo que a primeira linha do PDF seja o cabeçalho (Dias da semana)
        df = pd.DataFrame(tabela_extraida[1:], columns=tabela_extraida[0])
        
        # 6. Transformar os dados em uma tabela HTML bonita (usando classes do Bootstrap)
        tabela_html = df.to_html(index=False, classes='table table-striped table-hover table-bordered text-center', na_rep='-')
        
        # 7. Gerar o arquivo final do site (index.html)
        html_completo = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Cardápio da Semana - RU UFCA</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body {{ background-color: #f8f9fa; padding: 20px; }}
                .container {{ background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                thead {{ background-color: #005b96; color: white; }}
            </style>
        </head>
        <body>
            <div class="container mt-4">
                <h2 class="mb-4 text-center">Cardápio da Semana - RU UFCA</h2>
                <div class="table-responsive">
                    {tabela_html}
                </div>
                <p class="text-muted text-center mt-3"><small>Atualizado automaticamente do site oficial da UFCA.</small></p>
            </div>
        </body>
        </html>
        """
        
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html_completo)
        print("Site (index.html) atualizado com sucesso!")
    else:
        print("Não foi possível identificar a tabela no PDF.")

if __name__ == '__main__':
    atualizar_cardapio()