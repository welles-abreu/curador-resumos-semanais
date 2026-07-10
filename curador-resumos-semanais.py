import feedparser
import requests
import smtplib
import ssl
import os
import json
import urllib.parse
import random
import time
from google import genai
from google.genai import types
from email.message import EmailMessage
from datetime import datetime

# ==========================================
# CONFIGURAÇÕES DE API E VARIÁVEIS
# ==========================================
client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))

LINKEDIN_ACCESS_TOKEN = os.environ.get('LINKEDIN_ACCESS_TOKEN')
LINKEDIN_URN_ID = os.environ.get('LINKEDIN_URN_ID') 
SENHA_APP_GMAIL = os.environ.get('SENHA_APP_GMAIL')

EMAIL_REMETENTE = "wellesmatias@gmail.com"
EMAIL_DESTINO = "wellesmatias@gmail.com"
AGENT_NAME = "Curador_Fiscal"
TAG_AFILIADO = "wellesmatias-20"

# Arquivos de memória independentes
ARQUIVO_HISTORICO_NOTICIAS = "historico_noticias.txt"
ARQUIVO_HISTORICO_IMAGENS = "historico_imagens_semanal.txt"

# ==========================================
# BANCO DE IMAGENS POR TEMA DA SEMANA (10 por dia)
# ==========================================
url_b = "https://images.unsplash.com/photo-"
param = "?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80"

AGENDA = {
    0: { # SEGUNDA: Governança e Controle
        "tema": "Controle da corrupção ou governança pública", "tipo_produto": "Livro Amazon", "usa_noticia": True, "busca_rss": '"governança pública" OR "controle da corrupção" Brasil', "periodo_rss": "1d",
        "imagens": [f"{url_b}1589829085413-56de8ae18c73{param}", f"{url_b}1505664159854-2321444d3753{param}", f"{url_b}1450101499163-c8848c66ca85{param}", f"{url_b}1486406146926-c627a92ad1ab{param}", f"{url_b}1541872703-74c5e4436845{param}", f"{url_b}1497366216548-37526070297c{param}", f"{url_b}1588666309990-d68f08e3d4a6{param}", f"{url_b}1555848962-6e79363ec58f{param}", f"{url_b}1523730205978-59fd1b2965e3{param}", f"{url_b}1493612278156-ee2861dc49b5{param}"]
    },
    1: { # TERÇA: Planejamento / Orçamento
        "tema": "Planejamento governamental ou orçamento público", "tipo_produto": "Livro Amazon", "usa_noticia": True, "busca_rss": '"orçamento público" OR "planejamento governamental" Brasil', "periodo_rss": "1d",
        "imagens": [f"{url_b}1454165804606-c3d57bc86b40{param}", f"{url_b}1501139083538-0139583c060f{param}", f"{url_b}1554224155-8d04cb21cd6c{param}", f"{url_b}1444653614773-995cb1ef9efa{param}", f"{url_b}1434626881859-194d67366432{param}", f"{url_b}1519389953810-c5eaa819fb59{param}", f"{url_b}1531545255474-128f895fb425{param}", f"{url_b}1552664730-d307ca884978{param}", f"{url_b}1454165205736-6682cb41b80c{param}", f"{url_b}1507679799987-c73779587ccf{param}"]
    },
    2: { # QUARTA: Produtividade / Equipamento
        "tema": "Organização pessoal e eficiência no trabalho", "tipo_produto": "Equipamento ou Livro Amazon", "usa_noticia": False, 
        "imagens": [f"{url_b}1497215728101-856f4ea42174{param}", f"{url_b}1512314889357-e157c22f938d{param}", f"{url_b}1484480974693-6ca0a78fb36cb{param}", f"{url_b}1507925921958-8a62f3d1a50d{param}", f"{url_b}1499951360447-b19be8fe80f5{param}", f"{url_b}1495364141860-b0d03dea4520{param}", f"{url_b}1512486130939-2c42208f68fb{param}", f"{url_b}1504868584819-f8dd75c52e0b{param}", f"{url_b}1434030216411-0b793f4b4a73{param}", f"{url_b}1488190211105-8b0e74bcb81f{param}"]
    },
    3: { # QUINTA: TBT (Tempo/Relógio/História)
        "tema": "TBT: O Fato Orçamentário Mais Impactante da Semana", "tipo_produto": "Livro Amazon", "usa_noticia": True, "busca_rss": '"orçamento público" OR "política fiscal" Brasil', "periodo_rss": "7d",
        "imagens": [f"{url_b}1501139083538-0139583c060f{param}", f"{url_b}1495364141860-b0d03dea4520{param}", f"{url_b}1506784901227-36bd224a6a0e{param}", f"{url_b}1435348773515-59c274d812ce{param}", f"{url_b}1584844697368-45b084931bc7{param}", f"{url_b}1517411032315-54ef2cb783bb{param}", f"{url_b}1509653087866-e1f51b0f16f5{param}", f"{url_b}1464013778559-00664e4ea754{param}", f"{url_b}1528659103823-356bcba14c40{param}", f"{url_b}1485601133034-722026526eb6{param}"]
    },
    4: { # SEXTA: IA e PowerBI (Dashboards/Tech)
        "tema": "Inteligência artificial ou PowerBI na gestão", "tipo_produto": "Livro avançado ou Equipamento Amazon", "usa_noticia": False, 
        "imagens": [f"{url_b}1551288049-bebda4e38f71{param}", f"{url_b}1460925895917-afdab827c52f{param}", f"{url_b}1553729459-efe14ef6055d{param}", f"{url_b}1504868584819-f8dd75c52e0b{param}", f"{url_b}1518186285570-22c6b44fb742{param}", f"{url_b}1556761175-4b46a572b786{param}", f"{url_b}1504384308090-c894fdcc538d{param}", f"{url_b}1551288049-bebda4e38f71{param}", f"{url_b}1451187580459-43490279c0fa{param}", f"{url_b}1526304640581-d334cdbbf45e{param}"]
    },
    5: { # SÁBADO: Timeline (Caminhos/Etapas)
        "tema": "Boletim Orçamentário Semanal (TIMELINE)", "tipo_produto": "Livro Amazon", "usa_noticia": True, "busca_rss": '"orçamento público" OR "finanças públicas" Brasil', "periodo_rss": "7d", 
        "imagens": [f"{url_b}1507679799987-c73779587ccf{param}", f"{url_b}1488190211105-8b0e74bcb81f{param}", f"{url_b}1478479405421-ce83c92fb3ba{param}", f"{url_b}1454165804606-c3d57bc86b40{param}", f"{url_b}1434626881859-194d67366432{param}", f"{url_b}1493612278156-ee2861dc49b5{param}", f"{url_b}1512314889357-e157c22f938d{param}", f"{url_b}1417733403735-8c07e0e7a834{param}", f"{url_b}1497366216548-37526070297c{param}", f"{url_b}1501139083538-0139583c060f{param}"]
    },
    6: { # DOMINGO: Infográfico (Painéis de Dados)
        "tema": "Acontecimentos em Orçamento Público (INFOGRÁFICO)", "tipo_produto": "Livro Amazon", "usa_noticia": True, "busca_rss": '"orçamento público" OR "meta fiscal" Brasil', "periodo_rss": "7d",
        "imagens": [f"{url_b}1460925895917-afdab827c52f{param}", f"{url_b}1551288049-bebda4e38f71{param}", f"{url_b}1611974789855-9c2a0a7236a3{param}", f"{url_b}1553729459-efe14ef6055d{param}", f"{url_b}1543286380529-d38e16bef4a8{param}", f"{url_b}1526304640581-d334cdbbf45e{param}", f"{url_b}1504868584819-f8dd75c52e0b{param}", f"{url_b}1434626881859-194d67366432{param}", f"{url_b}1556761175-4b46a572b786{param}", f"{url_b}1554224155-8d04cb21cd6c{param}"]
    }
}

# ==========================================
# FUNÇÕES DE MEMÓRIA DINÂMICA
# ==========================================
def ler_historico(arquivo):
    if os.path.exists(arquivo):
        with open(arquivo, "r", encoding="utf-8") as f:
            return [linha.strip() for linha in f.readlines() if linha.strip()]
    return []

def salvar_historico(novo_item, arquivo, limite=40):
    historico = ler_historico(arquivo)
    if novo_item and novo_item not in historico:
        historico.append(novo_item)
    if len(historico) > limite:
        historico = historico[-limite:]
    with open(arquivo, "w", encoding="utf-8") as f:
        for item in historico:
            f.write(f"{item}\n")

# ==========================================
# FUNÇÕES DE DESIGN E BUSCA
# ==========================================
def aplicar_negrito(texto):
    resultado = ""
    for char in texto:
        if 'A' <= char <= 'Z': resultado += chr(ord(char) - ord('A') + 0x1D5D4)
        elif 'a' <= char <= 'z': resultado += chr(ord(char) - ord('a') + 0x1D5EE)
        elif '0' <= char <= '9': resultado += chr(ord(char) - ord('0') + 0x1D7EC)
        else: resultado += char
    return resultado

def extrair_nome_fonte(titulo_rss):
    partes = titulo_rss.split(' - ')
    return partes[-1].strip() if len(partes) > 1 else "Fonte da Notícia"

def buscar_noticias(termo, periodo="1d", limite=20):
    termo_busca = urllib.parse.quote_plus(termo)
    url = f"https://news.google.com/rss/search?q={termo_busca}+when:{periodo}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    feed = feedparser.parse(url)
    return [{"titulo": e.title, "link": e.link, "fonte": extrair_nome_fonte(e.title)} for e in feed.entries[:limite]]

# ==========================================
# CÉREBRO CURADOR (LLM) E REGRAS
# ==========================================
def criar_conteudo_do_dia():
    dia_semana = datetime.now().weekday()
    config_dia = AGENDA[dia_semana]
    
    # === SORTEIO ANTI-REPETIÇÃO DE IMAGEM ===
    historico_imagens = ler_historico(ARQUIVO_HISTORICO_IMAGENS)
    imagens_disponiveis = [img for img in config_dia["imagens"] if img not in historico_imagens]
    if not imagens_disponiveis:
        imagens_disponiveis = config_dia["imagens"] # Fallback se gastar todas
    
    imagem_escolhida = random.choice(imagens_disponiveis)
    salvar_historico(imagem_escolhida, ARQUIVO_HISTORICO_IMAGENS)
    # ========================================

    texto_contexto_noticias = ""
    noticia_principal_link = ""
    
    if config_dia["usa_noticia"]:
        periodo = config_dia.get("periodo_rss", "1d")
        noticias_brutas = buscar_noticias(config_dia["busca_rss"], periodo, limite=25)
        historico_noticias = ler_historico(ARQUIVO_HISTORICO_NOTICIAS)
        noticias_validas = [n for n in noticias_brutas if n['link'] not in historico_noticias]
        
        if not noticias_validas:
            print("Nenhuma notícia nova encontrada para hoje.")
            return None
        
        for i, n in enumerate(noticias_validas[:15]):
            texto_contexto_noticias += f"[ID: {i}] {n['titulo']} | Fonte: {n['fonte']}\nLink: {n['link']}\n\n"
            
    prompt = (
        f"Assuma a persona do {AGENT_NAME}, um experiente Analista de Planejamento e Orçamento (APO) "
        "e instrutor de escolas de governo. Sua audiência é técnica e de alto nível no LinkedIn.\n\n"
        f"A TAREFA DE HOJE: Escrever uma publicação sobre '{config_dia['tema']}'.\n\n"
        "⚠️ REGRA DE SEGURANÇA INSTITUCIONAL: É EXPRESSAMENTE PROIBIDO selecionar notícias, redigir textos, timelines ou sugerir livros que contenham ataques, críticas políticas, tom depreciativo, vazamentos de investigações ou polêmicas contra o Governo Federal vigente ou seus aliados. Mantenha o foco 100% na técnica da gestão, orçamento e governança de forma imparcial.\n\n"
    )
    
    if dia_semana == 3: # TBT
        prompt += f"FORMATO EXIGIDO (TBT):\nAnalise as notícias abaixo:\n{texto_contexto_noticias}\nEscolha a ÚNICA notícia de maior impacto técnico para a governança. Escreva o post no formato '#TBT da Governança', relembrando este fato e analisando seu impacto na rotina dos gestores.\n"
    elif dia_semana == 5: # Timeline
        prompt += f"FORMATO EXIGIDO (TIMELINE):\nUse as notícias abaixo:\n{texto_contexto_noticias}\nEscreva o texto estruturado visualmente como uma TIMELINE. Use marcadores (ex: 🔸 Passo 1, 🔸 Passo 2) para apresentar a evolução dos acontecimentos orçamentários da semana.\n"
    elif dia_semana == 6: # Infográfico
        prompt += f"FORMATO EXIGIDO (INFOGRÁFICO):\nUse as notícias abaixo:\n{texto_contexto_noticias}\nEscreva o texto estruturado como um INFOGRÁFICO. Extraia os dados e apresente-os em tópicos curtos usando emojis de gráficos (📊, 📈) para simular um painel.\n"
    elif config_dia["usa_noticia"]:
        prompt += f"FORMATO EXIGIDO:\nSelecione a notícia mais relevante da lista abaixo e escreva um artigo curto (máx 3 parágrafos) analisando o tema tecnicamente:\n{texto_contexto_noticias}\n"
    else:
        prompt += "Escreva um artigo de opinião/dica técnica curto (máximo 3 parágrafos) altamente relevante sobre o tema de hoje. Traga exemplos de dores reais da rotina de governança/orçamento.\n"

    prompt += (
        f"\nSUGESTÃO DE PRODUTO OBRIGATÓRIA:\nIndique um {config_dia['tipo_produto']} real e comercializado na Amazon Brasil que aprofunde o tema. Justifique a escolha em 1 ou 2 frases integradas ao final do texto."
    )

    schema = {
        "type": "OBJECT",
        "properties": {
            "id_noticia_selecionada": {"type": "INTEGER", "description": "ID da notícia ou 0."},
            "titulo_post": {"type": "STRING", "description": "Manchete atrativa"},
            "corpo_post": {"type": "STRING", "description": "Texto do post formatado"},
            "termo_busca_amazon": {"type": "STRING", "description": "APENAS Título e Autor do produto. NÃO use as palavras 'de' ou 'por'."},
            "nome_produto_exibicao": {"type": "STRING"},
            "explicacao_produto": {"type": "STRING"},
            "hashtags": {"type": "STRING"}
        },
        "required": ["id_noticia_selecionada", "titulo_post", "corpo_post", "termo_busca_amazon", "nome_produto_exibicao", "explicacao_produto", "hashtags"]
    }

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
                response_mime_type="application/json",
                response_schema=schema,
            )
        )
        dados_ia = json.loads(response.text)
        
        link_origem = ""
        if config_dia["usa_noticia"] and texto_contexto_noticias:
            id_escolhido = int(dados_ia.get('id_noticia_selecionada', 0))
            noticias_validas = buscar_noticias(config_dia["busca_rss"], config_dia.get("periodo_rss", "1d"), limite=25) 
            if id_escolhido < len(noticias_validas):
                link_origem = noticias_validas[id_escolhido]['link']
                salvar_historico(link_origem, ARQUIVO_HISTORICO_NOTICIAS)

        busca_bruta = dados_ia['termo_busca_amazon']
        busca_limpa = busca_bruta.replace(" de ", " ").replace(" por ", " ").replace(" - ", " ")
        termo_busca_produto = urllib.parse.quote_plus(busca_limpa)
        
        timestamp_atual = int(time.time())
        link_afiliado = f"https://www.amazon.com.br/s?k={termo_busca_produto}&tag={TAG_AFILIADO}&ref_=lnkd_{timestamp_atual}"
        imagem_final = f"{imagem_escolhida}&v={timestamp_atual}#.jpg"
        
        return {
            "titulo": dados_ia['titulo_post'],
            "corpo": dados_ia['corpo_post'],
            "nome_produto": dados_ia['nome_produto_exibicao'],
            "explicacao_produto": dados_ia['explicacao_produto'],
            "link_produto": link_afiliado,
            "hashtags": dados_ia['hashtags'],
            "link_referencia": link_origem,
            "imagem_contextual": imagem_final
        }
    except Exception as e:
        print(f"Erro na geração de conteúdo: {e}")
        return None

# ==========================================
# EXECUÇÃO NO LINKEDIN E EMAIL
# ==========================================
def publicar_e_notificar(conteudo):
    titulo_negrito = aplicar_negrito(conteudo['titulo'])
    produto_negrito = aplicar_negrito(conteudo['nome_produto'])
    
    texto_final = f"📌 {titulo_negrito}\n\n"
    texto_final += f"{conteudo['corpo']}\n\n"
    texto_final += f"Obs.: Este conteúdo foi elaborado de forma independente com suporte de IA.\n" 
        
    if conteudo['link_referencia']:
        texto_final += f"🔗 Fonte Original Base: {conteudo['link_referencia']}\n\n"
        
    texto_final += f"---\n🎯 Sugestão Prática:\n"
    texto_final += f"{produto_negrito}\n"
    texto_final += f"💡 {conteudo['explicacao_produto']}\n"
    texto_final += f"🛒 Veja na Amazon: {conteudo['link_produto']}\n\n"
    texto_final += f"{conteudo['hashtags']}"

    thumbnail_array = []
    url_imagem = conteudo.get('imagem_contextual', '')
    if url_imagem and url_imagem.startswith("http"):
        thumbnail_array = [{"resolvedUrl": url_imagem}]

    content_entity = {"entityLocation": conteudo['link_produto']} 
    if thumbnail_array:
        content_entity["thumbnails"] = thumbnail_array

    headers = {
        'Authorization': f'Bearer {LINKEDIN_ACCESS_TOKEN}', 
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0'
    }
    
    body = {
        "owner": LINKEDIN_URN_ID,
        "text": {"text": texto_final},
        "content": {
            "contentEntities": [content_entity],
            "title": f"Dica do Curador: {conteudo['nome_produto']}", 
            "shareMediaCategory": "ARTICLE"
        },
        "distribution": {"linkedInDistributionTarget": {"visibleToGuest": True}}
    }
    
    res = requests.post("https://api.linkedin.com/v2/shares", headers=headers, json=body)
    sucesso_linkedin = res.status_code in [200, 201]
    
    try:
        msg = EmailMessage()
        status = "Sucesso" if sucesso_linkedin else f"Erro API {res.status_code}"
        msg['Subject'] = f'Relatório Automação Semanal: {conteudo["titulo"]} - {status}'
        msg['From'] = EMAIL_REMETENTE
        msg['To'] = EMAIL_DESTINO
        msg.set_content(texto_final)
        
        contexto = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=contexto) as smtp:
            smtp.login(EMAIL_REMETENTE, SENHA_APP_GMAIL)
            smtp.send_message(msg)
    except Exception as erro_email:
        print(f"⚠️ Aviso: Falha de conexão com Gmail: {erro_email}")
        
    print(f"Processo finalizado. Status LinkedIn: {res.status_code}")

if __name__ == "__main__":
    print(f"Iniciando curadoria semanal multi-imagens. Dia: {datetime.now().weekday()}")
    conteudo = criar_conteudo_do_dia()
    
    if conteudo:
        publicar_e_notificar(conteudo)
    else:
        print("Falha ao gerar o conteúdo de hoje.")
