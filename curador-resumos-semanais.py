import feedparser
import requests
import smtplib
import ssl
import os
import json
import urllib.parse
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
ARQUIVO_HISTORICO = "historico_noticias.txt"

# ==========================================
# AGENDA SEMANAL DINÂMICA
# 0=Segunda, 1=Terça, 2=Quarta, 3=Quinta, 4=Sexta, 5=Sábado, 6=Domingo
# ==========================================
AGENDA = {
    0: {"tema": "Controle da corrupção ou governança pública", "tipo_produto": "Livro Amazon", "usa_noticia": True, "busca_rss": '"governança pública" OR "controle da corrupção" Brasil', "periodo_rss": "1d",
        "imagem_fallback": "https://images.unsplash.com/photo-1589829085413-56de8ae18c73?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80#.jpg"},
    
    1: {"tema": "Planejamento governamental ou orçamento público", "tipo_produto": "Livro Amazon", "usa_noticia": True, "busca_rss": '"orçamento público" OR "planejamento governamental" Brasil', "periodo_rss": "1d",
        "imagem_fallback": "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80#.jpg"},
    
    2: {"tema": "Organização pessoal e eficiência no trabalho", "tipo_produto": "Equipamento ou Livro Amazon", "usa_noticia": False, 
        "imagem_fallback": "https://images.unsplash.com/photo-1497215728101-856f4ea42174?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80#.jpg"},
    
    3: {"tema": "TBT: O Fato Orçamentário Mais Impactante da Semana", "tipo_produto": "Livro Amazon", "usa_noticia": True, "busca_rss": '"orçamento público" OR "política fiscal" Brasil', "periodo_rss": "7d",
        "imagem_fallback": "https://images.unsplash.com/photo-1501139083538-0139583c060f?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80#.jpg"}, # Imagem de Relógio/Tempo (TBT)
    
    4: {"tema": "Inteligência artificial ou PowerBI na gestão", "tipo_produto": "Livro avançado ou Equipamento Amazon", "usa_noticia": False, 
        "imagem_fallback": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80#.jpg"},
    
    5: {"tema": "Boletim Orçamentário Semanal (TIMELINE)", "tipo_produto": "Livro Amazon", "usa_noticia": True, "busca_rss": '"orçamento público" OR "finanças públicas" Brasil', "periodo_rss": "7d", 
        "imagem_fallback": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80#.jpg"}, # Imagem de Roadmap/Estratégia
    
    6: {"tema": "Acontecimentos em Orçamento Público (INFOGRÁFICO)", "tipo_produto": "Livro Amazon", "usa_noticia": True, "busca_rss": '"orçamento público" OR "meta fiscal" Brasil', "periodo_rss": "7d",
        "imagem_fallback": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?ixlib=rb-4.0.3&auto=format&fit=crop&w=1200&q=80#.jpg"} # Imagem de Gráficos/Dashboard
}

# ==========================================
# FUNÇÕES DE MEMÓRIA
# ==========================================
def ler_historico():
    if os.path.exists(ARQUIVO_HISTORICO):
        with open(ARQUIVO_HISTORICO, "r", encoding="utf-8") as f:
            return [linha.strip() for linha in f.readlines() if linha.strip()]
    return []

def salvar_historico(novo_link, limite=30):
    historico = ler_historico()
    if novo_link and novo_link not in historico:
        historico.append(novo_link)
    if len(historico) > limite:
        historico = historico[-limite:]
    with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
        for link in historico:
            f.write(f"{link}\n")

# ==========================================
# FUNÇÕES DE DESIGN
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
# CÉREBRO CURADOR (LLM) DINÂMICO
# ==========================================
def criar_conteudo_do_dia():
    dia_semana = datetime.now().weekday()
    config_dia = AGENDA[dia_semana]
    
    texto_contexto_noticias = ""
    noticia_principal_link = ""
    
    if config_dia["usa_noticia"]:
        periodo = config_dia.get("periodo_rss", "1d")
        noticias_brutas = buscar_noticias(config_dia["busca_rss"], periodo, limite=25)
        historico = ler_historico()
        noticias_validas = [n for n in noticias_brutas if n['link'] not in historico]
        
        if not noticias_validas:
            print("Nenhuma notícia nova encontrada. O processo será encerrado hoje para evitar repetição.")
            return None
        
        for i, n in enumerate(noticias_validas[:15]):
            texto_contexto_noticias += f"[ID: {i}] {n['titulo']} | Fonte: {n['fonte']}\nLink: {n['link']}\n\n"
        noticia_principal_link = noticias_validas[0]['link'] 
            
    prompt = (
        f"Assuma a persona do {AGENT_NAME}, um experiente Analista de Planejamento e Orçamento (APO) "
        "e instrutor de escolas de governo. Sua audiência é técnica e de alto nível no LinkedIn.\n\n"
        f"A TAREFA DE HOJE: Escrever uma publicação sobre '{config_dia['tema']}'.\n\n"
        "⚠️ REGRA DE SEGURANÇA INSTITUCIONAL: É EXPRESSAMENTE PROIBIDO selecionar notícias, redigir textos, timelines ou sugerir livros que contenham ataques, críticas políticas, tom depreciativo, vazamentos de investigações ou polêmicas contra o Governo Federal vigente ou seus aliados. Mantenha o foco 100% na técnica da gestão, orçamento e governança de forma imparcial.\n\n"
    )
    
    # LÓGICA ESTRUTURAL BASEADA NO DIA DA SEMANA
    if dia_semana == 3: # Quinta-feira (TBT)
        prompt += (
            f"FORMATO EXIGIDO (TBT):\n"
            f"Analise as notícias dos últimos 7 dias abaixo:\n{texto_contexto_noticias}\n"
            "Escolha a ÚNICA notícia de maior impacto técnico para a governança. Escreva o post no formato '#TBT da Governança', relembrando este fato e analisando seu impacto na rotina dos gestores.\n"
        )
    elif dia_semana == 5: # Sábado (Boletim/Timeline)
        prompt += (
            f"FORMATO EXIGIDO (BOLETIM TIMELINE):\n"
            f"Use as notícias abaixo:\n{texto_contexto_noticias}\n"
            "Escreva o texto estruturado visualmente como uma TIMELINE. Use marcadores (ex: 🔸 Passo 1, 🔸 Passo 2, ou divisões temporais lógicas) para apresentar a evolução ou os pontos principais dos acontecimentos orçamentários da semana.\n"
        )
    elif dia_semana == 6: # Domingo (Infográfico)
        prompt += (
            f"FORMATO EXIGIDO (INFOGRÁFICO EM TEXTO):\n"
            f"Use as notícias abaixo:\n{texto_contexto_noticias}\n"
            "Escreva o texto estruturado visualmente como um INFOGRÁFICO. Extraia os dados, percentuais e fatos principais das notícias e apresente-os em tópicos curtos e diretos, usando emojis de gráficos (📊, 📈, 📉) para simular um painel de dados.\n"
        )
    elif config_dia["usa_noticia"]: # Outros dias com notícia
        prompt += (
            f"FORMATO EXIGIDO:\n"
            f"Selecione a notícia mais relevante da lista abaixo e escreva um artigo curto (máx 3 parágrafos) analisando o tema tecnicamente:\n{texto_contexto_noticias}\n"
        )
    else: # Dias conceituais (sem notícia)
        prompt += (
            "Escreva um artigo de opinião/dica técnica curto (máximo 3 parágrafos) altamente relevante sobre o tema de hoje. "
            "Traga exemplos de dores reais da rotina de governança/orçamento.\n"
        )

    prompt += (
        f"\nSUGESTÃO DE PRODUTO OBRIGATÓRIA:\n"
        f"Indique um {config_dia['tipo_produto']} real e comercializado na Amazon Brasil que aprofunde o tema.\n"
        "Justifique a escolha do produto em 1 ou 2 frases integradas ao final do texto."
    )

    schema = {
        "type": "OBJECT",
        "properties": {
            "id_noticia_selecionada": {"type": "INTEGER", "description": "Se usou uma notícia da lista, coloque o ID. Se não usou, ponha 0."},
            "titulo_post": {"type": "STRING", "description": "Manchete atrativa para o LinkedIn"},
            "corpo_post": {"type": "STRING", "description": "O texto do post, respeitando rigorosamente a formatação exigida para o dia (Timeline, Infográfico, TBT, etc)."},
            "termo_busca_amazon": {"type": "STRING", "description": "APENAS Título e Autor do produto. NÃO use 'de' ou 'por'."},
            "nome_produto_exibicao": {"type": "STRING"},
            "explicacao_produto": {"type": "STRING"},
            "hashtags": {"type": "STRING", "description": "Ex: #Gov #Orcamento #Gestao"}
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
                salvar_historico(link_origem)

        # Limpeza do termo de busca para a Amazon
        busca_bruta = dados_ia['termo_busca_amazon']
        busca_limpa = busca_bruta.replace(" de ", " ").replace(" por ", " ").replace(" - ", " ")
        termo_busca_produto = urllib.parse.quote_plus(busca_limpa)
        
        # Cache-buster para garantir a imagem do LinkedIn
        timestamp_atual = int(time.time())
        link_afiliado = f"https://www.amazon.com.br/s?k={termo_busca_produto}&tag={TAG_AFILIADO}&ref_=lnkd_{timestamp_atual}"
        
        return {
            "titulo": dados_ia['titulo_post'],
            "corpo": dados_ia['corpo_post'],
            "nome_produto": dados_ia['nome_produto_exibicao'],
            "explicacao_produto": dados_ia['explicacao_produto'],
            "link_produto": link_afiliado,
            "hashtags": dados_ia['hashtags'],
            "link_referencia": link_origem,
            "imagem_contextual": config_dia["imagem_fallback"]
        }
    except Exception as e:
        print(f"Erro na geração de conteúdo: {e}")
        return None

# ==========================================
# EXECUÇÃO (LINKEDIN E EMAIL)
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

    # Força o Card a apontar para o produto da Amazon sempre
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
    print(f"Iniciando curadoria semanal. Dia da semana atual: {datetime.now().weekday()}")
    conteudo = criar_conteudo_do_dia()
    
    if conteudo:
        publicar_e_notificar(conteudo)
    else:
        print("Falha ao gerar o conteúdo de hoje.")