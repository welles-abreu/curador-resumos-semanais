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

EMAIL_REMETENTE = "wellesmatias@gmail.com"
EMAIL_DESTINO = "wellesmatias@gmail.com"
AGENT_NAME = "Curador Orçamentário"

ARQUIVO_HISTORICO_NOTICIAS = "historico_noticias.txt"
ARQUIVO_HISTORICO_IMAGENS = "historico_imagens_semanal.txt"

# ==========================================
# AGENDA ESTRITA: APENAS QUINTA-FEIRA
# ==========================================
url_b = "https://images.unsplash.com/photo-"
param = "?auto=format&fit=crop&w=800&q=80&fm=jpg"

# Ajustado para manter apenas a configuração de quinta-feira (3)
AGENDA = {
    3: { # QUINTA-FEIRA: TBT (Foco visual: Relógios, Tempo, Arquivo)
        "tema": "TBT: Resumo do Fato Orçamentário Mais Impactante da Semana", 
        "tipo_produto": "uma imagem que sintetiza o conteúdo em debate", 
        "usa_noticia": True, "busca_rss": '"orçamento público" OR "política fiscal" Brasil', "periodo_rss": "7d",
        "imagens": [f"{url_b}1501139083538-0139583c060f{param}", f"{url_b}1495364141860-b0d03dea4520{param}", f"{url_b}1506784901227-36bd224a6a0e{param}", f"{url_b}1435348773515-59c274d812ce{param}", f"{url_b}1584844697368-45b084931bc7{param}", f"{url_b}1517411032315-54ef2cb783bb{param}", f"{url_b}1509653087866-e1f51b0f16f5{param}", f"{url_b}1464013778559-00664e4ea754{param}", f"{url_b}1528659103823-356bcba14c40{param}", f"{url_b}1485601133034-722026526eb6{param}"]
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
    
    # 🔴 TRAVA DE SEGURANÇA: Se não for dia de postar (quinta=3), encerra o script.
    if dia_semana not in AGENDA:
        print(f"Hoje é dia {dia_semana}. A postagem está configurada apenas para quinta-feira (dia 3).")
        return None

    config_dia = AGENDA[dia_semana]
    texto_contexto_noticias = ""
    
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
            
    # Ajuste: Alterado de APO para Especialista em Governança Orçamentária
    prompt = (
        f"Assuma a persona do {AGENT_NAME}, um experiente Especialista em Governança Orçamentária "
        "e instrutor de escolas de governo. Sua audiência é técnica e de alto nível no LinkedIn, sem posicionamento político e partidário contra ou a favor, clara e objetiva.\n\n"
        f"A TAREFA DE HOJE: Escrever uma publicação sobre '{config_dia['tema']}'.\n\n"
        "⚠️ REGRA DE SEGURANÇA INSTITUCIONAL: É EXPRESSAMENTE PROIBIDO selecionar notícias, redigir textos ou sugerir produtos que contenham ataques, críticas políticas, tom depreciativo ou polêmicas contra o Governo Federal ou seus aliados. Mantenha o foco 100% na técnica da gestão e orçamento.\n\n"
    )
    
    if dia_semana == 3: # Quinta - TBT
        prompt += f"FORMATO EXIGIDO (TBT):\nAnalise as notícias abaixo:\n{texto_contexto_noticias}\nEscolha a ÚNICA notícia de maior impacto técnico dos últimos 7 dias. Escreva o post no formato '#TBT da Governança', relembrando este fato.\n"

    # Ajuste: Reforçando para a IA não inventar tipos de produtos errados (como chamar imagem de infográfico)
    prompt += (
        f"\nPRODUTO VISUAL ACOMPANHANTE:\n"
        f"Esta publicação será acompanhada por {config_dia['tipo_produto']}. "
        f"Conclua o seu texto convidando o leitor de forma amigável a analisar EXATAMENTE ESTE TIPO DE PRODUTO que acompanha a publicação. Não use palavras como 'infográfico' se o produto for uma 'imagem', e vice-versa."
    )

    schema = {
        "type": "OBJECT",
        "properties": {
            "id_noticia_selecionada": {"type": "INTEGER", "description": "ID da notícia principal escolhida."},
            "titulo_post": {"type": "STRING", "description": "Manchete atrativa"},
            "corpo_post": {"type": "STRING", "description": "Texto do post formatado estritamente como exigido. Certifique-se de referenciar corretamente a imagem/produto visual ao final."},
            "hashtags": {"type": "STRING"}
        },
        "required": ["id_noticia_selecionada", "titulo_post", "corpo_post", "hashtags"]
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

        historico_imagens = ler_historico(ARQUIVO_HISTORICO_IMAGENS)
        imagens_disponiveis = [img for img in config_dia["imagens"] if img not in historico_imagens]
        
        if not imagens_disponiveis:
            imagens_disponiveis = config_dia["imagens"] 
            
        imagem_final = random.choice(imagens_disponiveis)
        salvar_historico(imagem_final, ARQUIVO_HISTORICO_IMAGENS)
        
        return {
            "titulo": dados_ia['titulo_post'],
            "corpo": dados_ia['corpo_post'],
            "hashtags": dados_ia['hashtags'],
            "link_referencia": link_origem,
            "imagem_contextual": imagem_final,
            "tipo_produto": config_dia['tipo_produto']
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
    
    texto_final = f"📅 Resumo da Semana ({data_formatada}) sobre o tema:\n"
    texto_final += f"📌 {titulo_negrito}\n"
    texto_final += f"{conteudo['corpo']}\n"
    texto_final += f"Obs.: Este conteúdo foi elaborado a partir das notícias de maior impacto da semana com foco estritamente técnico.\n" 
        
    if conteudo['link_referencia']:
        texto_final += f"🔗 Fonte Original Base: {conteudo['link_referencia']}\n"
        
    texto_final += f"\n{conteudo['hashtags']}"

    # Nota sobre a imagem no LinkedIn:
    # A API 'shares' com shareMediaCategory: "ARTICLE" tenta extrair a imagem do link de destino.
    # Se o link_referencia (notícia) tiver sua própria imagem (og:image), o LinkedIn pode priorizá-la
    # ignorando o thumbnail_array fornecido via código.
    thumbnail_array = []
    if conteudo.get('imagem_contextual'):
        thumbnail_array = [{"resolvedUrl": conteudo['imagem_contextual']}]

    link_destino = conteudo['link_referencia'] if conteudo.get('link_referencia') else conteudo['imagem_contextual']

    content_entity = {"entityLocation": link_destino} 
    if thumbnail_array:
        content_entity["thumbnails"] = thumbnail_array

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
    
    # Descomente a linha abaixo para realmente postar no LinkedIn
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
    print(f"Iniciando curadoria de TBT. Dia da semana: {datetime.now().weekday()} (0=Seg, 3=Qui)")
    conteudo = criar_conteudo_do_dia()
    
    if conteudo:
        publicar_e_notificar(conteudo)
    else:
        print("Execução encerrada sem novas publicações.")
