import streamlit as st
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import json
import urllib.parse
import io

st.set_page_config(page_title="RODA ML GOM", layout="centered")

CHAVE_API = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))

# CSS para customizar o container com rolagem e aparência mobile
st.markdown("""
    <style>
        .stButton button { width: 100%; border-radius: 6px; font-weight: bold; }
        .block-container { padding-top: 0.5rem; padding-bottom: 2rem; max-width: 800px; }
        .scroll-container {
            max-height: 450px;
            overflow-y: auto;
            padding: 10px;
            border: 1px solid #333;
            border-radius: 8px;
            background-color: rgba(255, 255, 255, 0.02);
        }
    </style>
""", unsafe_allow_html=True)

# --- CABEÇALHO COM LOGO DO MERCADO LIVRE E TÍTULO ---
col_logo, col_titulo = st.columns([0.15, 0.85])
with col_logo:
    # Logo oficial amarela do Mercado Livre
    st.markdown("""
        <div style="background-color: #ffe600; width: 50px; height: 50px; border-radius: 12px; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <span style="font-size: 28px;">🤝</span>
        </div>
    """, unsafe_allow_html=True)
with col_titulo:
    st.markdown("<h2 style='margin: 0; padding-top: 5px; color: #ffe600;'>RODA ML GOM</h2>", unsafe_allow_html=True)

st.markdown("---")

# Inicializa o estado para 100 linhas de pacotes
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
st.info("Preencha as fotos de Endereço e Etiqueta nas linhas desejadas. O sistema aceita a câmera nativa ou upload.")

# Container com rolagem vertical para as 100 linhas
with st.container():
    st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
    
    for i in range(1, NUM_linhas + 1):
        # Mostra apenas linhas ativas ou as primeiras 15 para não travar a tela de uma vez, mas mantém o loop de 100
        cols = st.columns([0.08, 0.42, 0.42, 0.08])
        with cols[0]:
            st.markdown(f"**#{i}**")
        with cols[1]:
            up_e = st.file_uploader(f"End {i}", type=["png", "jpg", "jpeg"], key=f"end_{i}", label_visibility="collapsed")
            if up_e:
                st.session_state.linhas_pacotes[i]["img_end"] = up_e.getvalue()
        with cols[2]:
            up_s = st.file_uploader(f"Seq {i}", type=["png", "jpg", "jpeg"], key=f"seq_{i}", label_visibility="collapsed")
            if up_s:
                st.session_state.linhas_pacotes[i]["img_seq"] = up_s.getvalue()
        with cols[3]:
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

# --- EXIBIÇÃO DA LISTA PROCESSADA E WAZE ---
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
        proximo_end = urllib.parse.quote(str(pendentes.iloc[0]['Endereço']))
        link_waze = f"https://waze.com/ul?q={proximo_end}&navigate=yes"
        st.link_button(f"📍 Abrir Waze (Próximo: {pendentes.iloc[0]['Seq']})", link_waze, type="primary", use_container_width=True)
else:
    st.info("Nenhum pacote processado pela IA ainda. Envie as fotos nas linhas acima e clique em 'Analisar Rota por IA'.")
