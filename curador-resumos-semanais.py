import feedparser
import requests
import smtplib
import ssl
import os
import json
import urllib.parse
import random
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

# Novo: Variável de ambiente para o seu link de produto principal na Amazon
LINK_AFILIADO_AMAZON = os.environ.get('LINK_AFILIADO_AMAZON', 'https://amzn.to/SEULINK')

EMAIL_REMETENTE = "wellesmatias@gmail.com"
EMAIL_DESTINO = "wellesmatias@gmail.com"
AGENT_NAME = "Curador_Fiscal"

ARQUIVO_HISTORICO_NOTICIAS = "historico_noticias.txt"
ARQUIVO_HISTORICO_IMAGENS = "historico_imagens_semanal.txt"

# ==========================================
# AGENDA ESTRITA: APENAS QUINTA, SÁBADO E DOMINGO
# ==========================================
url_b = "https://images.unsplash.com/photo-"
param = "?auto=format&fit=crop&w=800&q=80&fm=jpg"

AGENDA = {
    3: { # QUINTA-FEIRA: TBT
        "tema": "TBT: Resumo do Fato Orçamentário Mais Impactante da Semana", 
        "tipo_produto": "livro técnico sobre Gestão Fiscal", 
        "usa_noticia": True, "busca_rss": '"orçamento público" OR "política fiscal" Brasil', "periodo_rss": "7d",
        "imagens": [f"{url_b}1501139083538-0139583c060f{param}"] # Reduzido para brevidade
    },
    5: { # SÁBADO: Boletim TIMELINE
        "tema": "Boletim Orçamentário Semanal em formato Timeline", 
        "tipo_produto": "livro sobre Governança de Dados com Python", 
        "usa_noticia": True, "busca_rss": '"orçamento público" OR "finanças públicas" Brasil', "periodo_rss": "7d", 
        "imagens": [f"{url_b}1507679799987-c73779587ccf{param}"]
    },
    6: { # DOMINGO: Infográfico Orçamentário
        "tema": "Acontecimentos em Orçamento Público ilustrados como INFOGRÁFICO", 
        "tipo_produto": "periférico de alta performance para analistas de dados", 
        "usa_noticia": True, "busca_rss": '"orçamento público" OR "meta fiscal" Brasil', "periodo_rss": "7d",
        "imagens": [f"{url_b}1460925895917-afdab827c52f{param}"]
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
    
    if dia_semana not in AGENDA:
        print(f"Hoje é dia {dia_semana}. Não há postagem programada para hoje.")
        return None

    config_dia = AGENDA[dia_semana]
    texto_contexto_noticias = ""
    
    periodo = config_dia.get("periodo_rss", "7d")
    noticias_brutas = buscar_noticias(config_dia["busca_rss"], periodo, limite=30)
    historico_noticias = ler_historico(ARQUIVO_HISTORICO_NOTICIAS)
    noticias_validas = [n for n in noticias_brutas if n['link'] not in historico_noticias]
    
    if not noticias_validas:
        print("Nenhuma notícia nova encontrada.")
        return None
    
    for i, n in enumerate(noticias_validas[:15]):
        texto_contexto_noticias += f"[ID: {i}] {n['titulo']} | Fonte: {n['fonte']}\nLink: {n['link']}\n\n"
            
    prompt = (
        f"Assuma a persona do {AGENT_NAME}, um experiente Analista de Planejamento e Orçamento (APO) "
        "e instrutor de escolas de governo. Sua audiência é técnica e de alto nível no LinkedIn.\n\n"
        f"A TAREFA DE HOJE: Escrever uma publicação sobre '{config_dia['tema']}'.\n\n"
        "⚠️ REGRA DE SEGURANÇA INSTITUCIONAL: Isenção política total. Foco na técnica, eficiência e governança.\n\n"
        "ESTRUTURA DE TEXTO EXIGIDA:\n"
        "1. Gancho (máx. 3 linhas) para reter atenção antes do botão 'Ver mais'.\n"
        "2. Corpo técnico (parágrafos curtos).\n"
    )
    
    if dia_semana == 3:
        prompt += f"FORMATO (TBT):\nAnalise:\n{texto_contexto_noticias}\nEscolha a de maior impacto técnico. Formato '#TBT da Governança'.\n"
    elif dia_semana == 5:
        prompt += f"FORMATO (TIMELINE):\nAnalise:\n{texto_contexto_noticias}\nEscreva como uma TIMELINE visual (ex: 🔸 Passo 1).\n"
    elif dia_semana == 6:
        prompt += f"FORMATO (INFOGRÁFICO):\nAnalise:\n{texto_contexto_noticias}\nEscreva estruturado COMO UM INFOGRÁFICO (tópicos com 📊, 📈).\n"

    # Instrução explícita para monetização
    prompt += (
        f"\nMONETIZAÇÃO DISCRETA (Amazon):\n"
        f"Gere um pequeno texto de recomendação focado em: {config_dia['tipo_produto']}. "
        f"Finalize com '🛒 Confira aqui:' (O link será inserido pelo script)."
    )

    schema = {
        "type": "OBJECT",
        "properties": {
            "id_noticia_selecionada": {"type": "INTEGER"},
            "titulo_post": {"type": "STRING"},
            "corpo_post": {"type": "STRING"},
            "texto_monetizacao": {"type": "STRING", "description": "Recomendação discreta do produto Amazon"},
            "hashtags": {"type": "STRING"}
        },
        "required": ["id_noticia_selecionada", "titulo_post", "corpo_post", "texto_monetizacao", "hashtags"]
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
        
        return {
            "titulo": dados_ia['titulo_post'],
            "corpo": dados_ia['corpo_post'],
            "monetizacao": dados_ia['texto_monetizacao'],
            "hashtags": dados_ia['hashtags'],
            "link_referencia": link_origem
        }
    except Exception as e:
        print(f"Erro na geração de conteúdo: {e}")
        return None

# ==========================================
# EXECUÇÃO NO LINKEDIN E EMAIL
# ==========================================
def publicar_e_notificar(conteudo):
    titulo_negrito = aplicar_negrito(conteudo['titulo'])
    data_formatada = datetime.now().strftime('%d/%m/%Y')
    
    texto_final = f"📅 Resumo Semanal ({data_formatada})\n"
    texto_final += f"📌 {titulo_negrito}\n\n"
    texto_final += f"{conteudo['corpo']}\n\n"
    
    # Inserção da Fonte
    if conteudo['link_referencia']:
        texto_final += f"🔗 Fonte Original da Notícia Base: {conteudo['link_referencia']}\n\n"
    
    # Inserção da Recomendação Amazon (com link estático definido no ambiente)
    texto_final += f"💡 Recomendação de Setup/Leitura:\n{conteudo['monetizacao']} {LINK_AFILIADO_AMAZON}\n\n"
    
    texto_final += f"Obs.: Conteúdo curado via IA para eficiência analítica.\n" 
    texto_final += f"{conteudo['hashtags']}"

    # -------------------------------------------------------------
    # O SEGREDO PARA O CARD DA AMAZON:
    # Definimos o entityLocation EXCLUSIVAMENTE para o link da Amazon.
    # Não passamos "thumbnails". Isso obriga o LinkedIn a fazer o 
    # scraping nativo do Open Graph da página do produto.
    # -------------------------------------------------------------
    content_entity = {"entityLocation": LINK_AFILIADO_AMAZON} 

    body = {
        "owner": LINKEDIN_URN_ID,
        "text": {"text": texto_final},
        "content": {
            "contentEntities": [content_entity],
            "title": conteudo['titulo'], 
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
        msg['Subject'] = f'Relatório Automação: {conteudo["titulo"]} - {status}'
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
    conteudo = criar_conteudo_do_dia()
    if conteudo:
        publicar_e_notificar(conteudo)
    else:
        print("Execução encerrada.")
