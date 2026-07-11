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

ARQUIVO_HISTORICO_NOTICIAS = "historico_noticias.txt"
ARQUIVO_HISTORICO_IMAGENS = "historico_imagens_semanal.txt"

# ==========================================
# AGENDA ESTRITA: APENAS QUINTA, SÁBADO E DOMINGO
# ==========================================
url_b = "https://images.unsplash.com/photo-"
param = "?auto=format&fit=crop&w=800&q=80&fm=jpg"

AGENDA = {
    3: { # QUINTA-FEIRA: TBT (Foco visual: Relógios, Tempo, Arquivo)
        "tema": "TBT: Resumo do Fato Orçamentário Mais Impactante da Semana", "tipo_produto": "Livro Amazon", "usa_noticia": True, "busca_rss": '"orçamento público" OR "política fiscal" Brasil', "periodo_rss": "7d",
        "imagens": [f"{url_b}1501139083538-0139583c060f{param}", f"{url_b}1495364141860-b0d03dea4520{param}", f"{url_b}1506784901227-36bd224a6a0e{param}", f"{url_b}1435348773515-59c274d812ce{param}", f"{url_b}1584844697368-45b084931bc7{param}", f"{url_b}1517411032315-54ef2cb783bb{param}", f"{url_b}1509653087866-e1f51b0f16f5{param}", f"{url_b}1464013778559-00664e4ea754{param}", f"{url_b}1528659103823-356bcba14c40{param}", f"{url_b}1485601133034-722026526eb6{param}"]
    },
    5: { # SÁBADO: Boletim TIMELINE (Foco visual: Caminhos, Roadmaps, Escadas)
        "tema": "Boletim Orçamentário Semanal em formato Timeline", "tipo_produto": "Livro Amazon", "usa_noticia": True, "busca_rss": '"orçamento público" OR "finanças públicas" Brasil', "periodo_rss": "7d", 
        "imagens": [f"{url_b}1507679799987-c73779587ccf{param}", f"{url_b}1488190211105-8b0e74bcb81f{param}", f"{url_b}1478479405421-ce83c92fb3ba{param}", f"{url_b}1454165804606-c3d57bc86b40{param}", f"{url_b}1434626881859-194d67366432{param}", f"{url_b}1493612278156-ee2861dc49b5{param}", f"{url_b}1512314889357-e157c22f938d{param}", f"{url_b}1417733403735-8c07e0e7a834{param}", f"{url_b}1497366216548-37526070297c{param}", f"{url_b}1501139083538-0139583c060f{param}"]
    },
    6: { # DOMINGO: Infográfico Orçamentário (Foco visual: Dashboards, Gráficos, Dados)
        "tema": "Acontecimentos em Orçamento Público ilustrados como INFOGRÁFICO", "tipo_produto": "Livro Amazon", "usa_noticia": True, "busca_rss": '"orçamento público" OR "meta fiscal" Brasil', "periodo_rss": "7d",
        "imagens": [f"{url_b}1460925895917-afdab827c52f{param}", f"{url_b}1551288049-bebda4e38f71{param}", f"{url_b}1611974789855-9c2a0a7236a3{param}", f"{url_b}1553729459-efe14ef6055d{param}", f"{url_b}1543286380529-d38e16bef4a8{param}", f"{url_b}1526304640581-d334cdbbf45e{param}", f"{url_b}1504868584819-f8dd75c52e0b{param}", f"{url_b}1434626881859-194d67366432{param}", f"{url_b}1556761175-4b46a572b786{param}", f"{url_b}1554224155-8d04cb21cd6c{param}"]
    }
}

# ==========================================
# FUNÇÕES DE MEMÓRIA E DESIGN
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

def aplicar_negrito(texto):
    resultado = ""
    for char in texto:
        if 'A' <= char <= 'Z': resultado += chr(ord(char) - ord('A') + 0x1D5D4)
        elif 'a' <= char <= 'z': resultado += chr(ord(char) - ord('a') + 0x1D5EE)
        elif '0' <= char <= '9': resultado += chr(ord(char) - ord('0') + 0x1D7EC)
        elif char in ['ç', 'Ç']: resultado += '𝗰̧'
        elif char in ['ã', 'Ã']: resultado += '𝗮̃'
        elif char in ['á', 'Á']: resultado += '𝗮́'
        elif char in ['é', 'É']: resultado += '𝗲́'
        elif char in ['í', 'Í']: resultado += '𝗶́'
        elif char in ['ó', 'Ó']: resultado += '𝗼́'
        elif char in ['ú', 'Ú']: resultado += '𝘂́'
        elif char in ['ê', 'Ê']: resultado += '𝗲̂'
        elif char in ['ô', 'Ô']: resultado += '𝗼̂'
        else: resultado += char
    return resultado

def extrair_nome_fonte(titulo_rss):
    partes = titulo_rss.split(' - ')
    return partes[-1].strip() if len(partes) > 1 else "Fonte da Notícia"

def buscar_noticias(termo, periodo="7d", limite=25):
    termo_busca = urllib.parse.quote_plus(termo)
    url = f"https://news.google.com/rss/search?q={termo_busca}+when:{periodo}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    feed = feedparser.parse(url)
    return [{"titulo": e.title, "link": e.link, "fonte": extrair_nome_fonte(e.title)} for e in feed.entries[:limite]]

# ==========================================
# CÉREBRO CURADOR (LLM) E REGRAS
# ==========================================
def criar_conteudo_do_dia():
    dia_semana = datetime.now().weekday()
    
    # 🔴 TRAVA DE SEGURANÇA: Se não for dia de postar, encerra o script silenciosamente.
    if dia_semana not in AGENDA:
        print(f"Hoje é dia {dia_semana}. Não há postagem programada para hoje.")
        return None

    config_dia = AGENDA[dia_semana]
    texto_contexto_noticias = ""
    noticia_principal_link = ""
    
    # Busca Notícias
    periodo = config_dia.get("periodo_rss", "7d")
    noticias_brutas = buscar_noticias(config_dia["busca_rss"], periodo, limite=30)
    historico_noticias = ler_historico(ARQUIVO_HISTORICO_NOTICIAS)
    noticias_validas = [n for n in noticias_brutas if n['link'] not in historico_noticias]
    
    if not noticias_validas:
        print("Nenhuma notícia nova encontrada para a curadoria semanal.")
        return None
    
    for i, n in enumerate(noticias_validas[:15]):
        texto_contexto_noticias += f"[ID: {i}] {n['titulo']} | Fonte: {n['fonte']}\nLink: {n['link']}\n\n"
            
    prompt = (
        f"Assuma a persona do {AGENT_NAME}, um experiente Analista de Planejamento e Orçamento (APO) "
        "e instrutor de escolas de governo. Sua audiência é técnica e de alto nível no LinkedIn.\n\n"
        f"A TAREFA DE HOJE: Escrever uma publicação sobre '{config_dia['tema']}'.\n\n"
        "⚠️ REGRA DE SEGURANÇA INSTITUCIONAL: É EXPRESSAMENTE PROIBIDO selecionar notícias, redigir textos ou sugerir produtos que contenham ataques, críticas políticas, tom depreciativo ou polêmicas contra o Governo Federal ou seus aliados. Mantenha o foco 100% na técnica da gestão e orçamento.\n\n"
    )
    
    if dia_semana == 3: # Quinta - TBT
        prompt += f"FORMATO EXIGIDO (TBT):\nAnalise as notícias abaixo:\n{texto_contexto_noticias}\nEscolha a ÚNICA notícia de maior impacto técnico dos últimos 7 dias. Escreva o post no formato '#TBT da Governança', relembrando este fato.\n"
    elif dia_semana == 5: # Sábado - Timeline
        prompt += f"FORMATO EXIGIDO (TIMELINE):\nUse as notícias abaixo:\n{texto_contexto_noticias}\nEscreva o texto estruturado VISUALMENTE COMO UMA TIMELINE. Use marcadores ordenados (ex: 🔸 Passo 1, 🔸 Passo 2) para apresentar a evolução dos acontecimentos orçamentários da semana.\n"
    elif dia_semana == 6: # Domingo - Infográfico
        prompt += f"FORMATO EXIGIDO (INFOGRÁFICO):\nUse as notícias abaixo:\n{texto_contexto_noticias}\nEscreva o texto estruturado COMO UM INFOGRÁFICO. Extraia os dados e apresente-os em tópicos curtos usando emojis de gráficos (📊, 📈) simulando um painel de dados.\n"

    prompt += (
        f"\nSUGESTÃO DE PRODUTO OBRIGATÓRIA:\nIndique um {config_dia['tipo_produto']} real e comercializado na Amazon Brasil que aprofunde o tema discutido. Justifique a escolha em 1 ou 2 frases integradas ao final do texto."
    )

    schema = {
        "type": "OBJECT",
        "properties": {
            "id_noticia_selecionada": {"type": "INTEGER", "description": "ID da notícia principal escolhida."},
            "titulo_post": {"type": "STRING", "description": "Manchete atrativa"},
            "corpo_post": {"type": "STRING", "description": "Texto do post formatado estritamente como exigido (Timeline, Infográfico, TBT, etc)"},
            "termo_busca_amazon": {"type": "STRING", "description": "APENAS Título do Livro e Autor. NÃO use as palavras 'de' ou 'por' para não quebrar a busca da Amazon."},
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
        id_escolhido = int(dados_ia.get('id_noticia_selecionada', 0))
        if id_escolhido < len(noticias_validas):
            link_origem = noticias_validas[id_escolhido]['link']
            salvar_historico(link_origem, ARQUIVO_HISTORICO_NOTICIAS)

        busca_bruta = dados_ia['termo_busca_amazon']
        busca_limpa = busca_bruta.replace(" de ", " ").replace(" por ", " ").replace(" - ", " ")
        termo_busca_produto = urllib.parse.quote_plus(busca_limpa)
        
        timestamp_atual = int(time.time())
        link_afiliado = f"https://www.amazon.com.br/s?k={termo_busca_produto}&tag={TAG_AFILIADO}&ref_=lnkd_{timestamp_atual}"
        
        historico_imagens = ler_historico(ARQUIVO_HISTORICO_IMAGENS)
        imagens_disponiveis = [img for img in config_dia["imagens"] if img not in historico_imagens]
        
        if not imagens_disponiveis:
            imagens_disponiveis = config_dia["imagens"] 
            
        imagem_final = random.choice(imagens_disponiveis)
        salvar_historico(imagem_final, ARQUIVO_HISTORICO_IMAGENS)
        
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
    data_formatada = datetime.now().strftime('%d/%m/%Y')
    
    texto_final = f"📅 Resumo Semanal ({data_formatada})\n"
    texto_final += f"📌 {titulo_negrito}\n\n"
    texto_final += f"{conteudo['corpo']}\n\n"
    texto_final += f"Obs.: Este conteúdo foi elaborado com suporte de IA a partir das notícias de maior impacto da semana.\n" 
        
    if conteudo['link_referencia']:
        texto_final += f"🔗 Fonte Original Base: {conteudo['link_referencia']}\n\n"
        
    texto_final += f"---\n🎯 Sugestão Prática de Leitura:\n"
    texto_final += f"{produto_negrito}\n"
    texto_final += f"💡 {conteudo['explicacao_produto']}\n"
    texto_final += f"🛒 Veja os detalhes na Amazon: {conteudo['link_produto']}\n\n"
    texto_final += f"{conteudo['hashtags']}"

    # 🔴 SOLUÇÃO DO ERRO 400: Voltando para a estrutura "ARTICLE"
    thumbnail_array = []
    if conteudo.get('imagem_contextual'):
        thumbnail_array = [{"resolvedUrl": conteudo['imagem_contextual']}]

    content_entity = {"entityLocation": conteudo['link_produto']} 
    if thumbnail_array:
        content_entity["thumbnails"] = thumbnail_array

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
    
    headers = {
        'Authorization': f'Bearer {LINKEDIN_ACCESS_TOKEN}', 
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0'
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
    print(f"Iniciando curadoria semanal multi-imagens e anti-repetição. Dia: {datetime.now().weekday()}")
    conteudo = criar_conteudo_do_dia()
    
    if conteudo:
        publicar_e_notificar(conteudo)
    else:
        print("Execução encerrada.")
