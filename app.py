import streamlit as st
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import json
import urllib.parse
import os
import io

st.set_page_config(page_title="ROTA Mercado Livre - GOM", layout="centered")

CHAVE_API = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))

# CSS otimizado para forçar os elementos na mesma linha e caixa menor com scroll
st.markdown("""
    <style>
        .stButton button { width: 100%; border-radius: 6px; font-weight: bold; }
        .block-container { padding-top: 0.5rem; padding-bottom: 2rem; max-width: 800px; }
        
        /* Bloco menor com barra de rolagem dedicada */
        .scroll-container {
            max-height: 380px;
            overflow-y: auto;
            padding: 8px;
            border: 1px solid #444;
            border-radius: 8px;
            background-color: rgba(255, 255, 255, 0.02);
        }
        
        /* Força os elementos da linha a ficarem perfeitamente na horizontal no mobile */
        [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            align-items: center !important;
            gap: 4px !important;
        }
        [data-testid="column"] {
            width: auto !important;
            flex: 1 1 0% !important;
            min-width: 0px !important;
            padding: 0px 2px !important;
        }
        /* Ajusta o tamanho dos botões de upload na linha */
        .row-widget.stFileUploader {
            font-size: 11px !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- CABEÇALHO COM LOGO DO MERCADO LIVRE E TÍTULO ---
col_logo, col_titulo = st.columns([0.15, 0.85])
with col_logo:
    st.markdown("""
        <div style="background-color: #ffe600; width: 45px; height: 45px; border-radius: 10px; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <span style="font-size: 24px;">🤝</span>
        </div>
    """, unsafe_allow_html=True)
with col_titulo:
    st.markdown("<h3 style='margin: 0; padding-top: 5px; color: #ffe600;'>RODA ML GOM</h3>", unsafe_allow_html=True)

st.markdown("---")

NUM_linhas = 100
if 'linhas_pacotes' not in st.session_state:
    st.session_state.linhas_pacotes = {}
    for i in range(1, NUM_linhas + 1):
        st.session_state.linhas_pacotes[i] = {
            "img_end": None,
            "img_seq": None,
            "resultado_ia": None
        }

def limpar_tudo():
    for i in range(1, NUM_linhas + 1):
        st.session_state.linhas_pacotes[i] = {
            "img_end": None,
            "img_seq": None,
            "resultado_ia": None
        }
    st.success("Tudo limpo!")
    st.rerun()

st.markdown("### 📋 Grade de Cadastro (1 a 100)")
st.info("Linha: 📄 Endereço | 🔢 Etiqueta | ❌ Excluir")

# Bloco menor com barra de rolagem dedicada contendo as 100 opções
with st.container():
    st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
    
    for i in range(1, NUM_linhas + 1):
        # 3 colunas estritamente na mesma linha horizontal: [Endereço, Etiqueta, Botão X]
        cols = st.columns([0.43, 0.43, 0.14])
        
        with cols[0]:
            up_e = st.file_uploader(f"E{i}", type=["png", "jpg", "jpeg"], key=f"end_{i}", label_visibility="collapsed")
            if up_e:
                st.session_state.linhas_pacotes[i]["img_end"] = up_e.getvalue()
        with cols[1]:
            up_s = st.file_uploader(f"S{i}", type=["png", "jpg", "jpeg"], key=f"seq_{i}", label_visibility="collapsed")
            if up_s:
                st.session_state.linhas_pacotes[i]["img_seq"] = up_s.getvalue()
        with cols[2]:
            if st.button("❌", key=f"del_{i}"):
                st.session_state.linhas_pacotes[i] = {"img_end": None, "img_seq": None, "resultado_ia": None}
                st.rerun()
                
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("")
if st.button("🗑️ Limpar Tudo", type="secondary", use_container_width=True):
    limpar_tudo()

st.markdown("---")

# --- ANALISAR ROTA POR IA ---
st.markdown("### 🤖 Processamento Inteligente")
if st.button("⚡ Analisar Rota por IA (Transformar tudo em texto)", type="primary", use_container_width=True):
    with st.spinner("A IA está varrendo todas as imagens preenchidas..."):
        try:
            genai.configure(api_key=CHAVE_API)
            model = genai.GenerativeModel('gemini-3.6-flash')
            
            processou_algum = False
            for i in range(1, NUM_linhas + 1):
                item = st.session_state.linhas_pacotes[i]
                if item["img_end"] or item["img_seq"]:
                    imgs = []
                    if item["img_end"]: imgs.append(Image.open(io.BytesIO(item["img_end"])))
                    if item["img_seq"]: imgs.append(Image.open(io.BytesIO(item["img_seq"])))
                    
                    if imgs:
                        resp = model.generate_content(["Extraia rua, numero, bairro, cidade, estado, cep e sequencia (#A-1) em JSON puro com as chaves exatas: rua, numero, bairro, cidade, estado, cep, sequencia.", *imgs])
                        dados = json.loads(resp.text.strip().replace("```json", "").replace("```", ""))
                        
                        r_seq = dados.get('sequencia') or f"#A-{i}"
                        r_rua = dados.get('rua', '')
                        r_num = dados.get('numero', '')
                        r_bairro = dados.get('bairro', '')
                        r_cep = dados.get('cep', '')
                        
                        end_completo = f"{r_rua}, {r_num} - {r_bairro}, {r_cep}" if r_rua else "Endereço extraído por IA"
                        
                        st.session_state.linhas_pacotes[i]["resultado_ia"] = {
                            "Seq": r_seq,
                            "Endereço": end_completo,
                            "Status": "Pendente"
                        }
                        processou_algum = True
            
            if processou_algum:
                st.success("🎉 Rota processada e transformada em texto com sucesso!")
                st.rerun()
            else:
                st.warning("Nenhuma imagem foi encontrada nas linhas para processar.")
        except Exception as e:
            st.error(f"Erro ao processar com IA: {e}")

# --- EXIBIÇÃO DA LISTA PROCESSADA E ESCOLHA DE MAPA ---
st.markdown("---")
st.markdown("### 📋 Lista de Entregas Organizada")

pacotes_validos = [p["resultado_ia"] for p in st.session_state.linhas_pacotes.values() if p["resultado_ia"] is not None]

if pacotes_validos:
    df_res = pd.DataFrame(pacotes_validos)
    pendentes = df_res[df_res["Status"] == "Pendente"].reset_index(drop=True)
    
    st.write(f"**Total Processados:** {len(df_res)} | **Pendentes:** {len(pendentes)}")
    
    for idx, row in df_res.iterrows():
        c_chk, c_txt = st.columns([0.15, 0.85])
        with c_chk:
            marcado = st.checkbox("", value=(row["Status"] == "Entregue"), key=f"chk_res_{idx}")
            if marcado != (row["Status"] == "Entregue"):
                row["Status"] = "Entregue" if marcado else "Pendente"
                st.rerun()
        with c_txt:
            estilo = "~~" if row["Status"] == "Entregue" else ""
            st.markdown(f"{estilo}**[{row['Seq']}]** {row['Endereço']}{estilo}")

    if not pendentes.empty:
        st.markdown("---")
        st.markdown("#### 🧭 Navegação para o Próximo Destino")
        
        escolha_mapa = st.radio("Escolha o aplicativo de mapas:", ["Waze", "Google Maps"], horizontal=True)
        proximo_end = urllib.parse.quote(str(pendentes.iloc[0]['Endereço']))
        
        if escolha_mapa == "Waze":
            link_mapa = f"https://waze.com/ul?q={proximo_end}&navigate=yes"
        else:
            link_mapa = f"https://www.google.com/maps/search/?api=1&query={proximo_end}"
            
        st.link_button(f"🚀 Navegar para Próximo ({pendentes.iloc[0]['Seq']}) via {escolha_mapa}", link_mapa, type="primary", use_container_width=True)
else:
    st.info("Nenhum pacote processado pela IA ainda. Envie as fotos nas linhas acima e clique em 'Analisar Rota por IA'.")
