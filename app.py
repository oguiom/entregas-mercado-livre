import streamlit as st
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import json
import urllib.parse
import os
import io

st.set_page_config(page_title="Rota Pro Mobile", layout="centered")

CHAVE_API = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
ARQUIVO_HISTORICO = "historico_lote_flex.csv"

# CSS para customizar botões e espaçamento ideal para celular
st.markdown("""
    <style>
        .stButton button { width: 100%; border-radius: 6px; font-weight: bold; }
        .block-container { padding-top: 0.5rem; padding-bottom: 2rem; max-width: 700px; }
        div[data-testid="stHorizontalBlock"] { display: flex; gap: 8px; }
    </style>
""", unsafe_allow_html=True)

st.title("📦 Rota Pro - Mobile")

if 'pacotes' not in st.session_state:
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            df_hist = pd.read_csv(ARQUIVO_HISTORICO)
            st.session_state.pacotes = df_hist.to_dict('records')
        except:
            st.session_state.pacotes = []
    else:
        st.session_state.pacotes = []

def salvar_historico():
    if st.session_state.pacotes:
        dados_limpos = [{k: v for k, v in p.items() if k != 'bytes_end' and k != 'bytes_seq'} for p in st.session_state.pacotes]
        df = pd.DataFrame(dados_limpos)
        df.to_csv(ARQUIVO_HISTORICO, index=False)

def limpar_tabela():
    st.session_state.pacotes = []
    if os.path.exists(ARQUIVO_HISTORICO):
        os.remove(ARQUIVO_HISTORICO)

aba_principal, aba_visual = st.tabs(["🚀 Cadastro", "👁️ Mapa"])

with aba_principal:
    with st.expander("⚙️ Opções"):
        st.button("Limpar Todos os Pacotes", on_click=limpar_tabela)

    st.markdown("### 📸 Novo Pacote")

    # Abas ou blocos organizados para evitar conflito de câmera dupla no mobile
    modo_entrada = st.radio("Método de Captura:", ["📸 Usar Câmera", "📁 Upload de Arquivos / Digitação Manual"], horizontal=True)

    foto_end = None
    foto_seq = None
    manual_end = ""
    manual_seq = ""

    if modo_entrada == "📸 Usar Câmera":
        st.info("💡 Como o navegador bloqueia duas câmeras juntas, tire uma foto por vez abaixo:")
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("##### 📄 1. Endereço")
            foto_end = st.camera_input("Foto Endereço", key="cam_unica_e")
        with col_c2:
            st.markdown("##### 🔢 2. Sequência")
            foto_seq = st.camera_input("Foto Sequência", key="cam_unica_s")
            
        st.markdown("---")
        st.markdown("##### ✍️ Ou digite manualmente se preferir:")
        manual_end = st.text_input("Endereço Manual (Opcional)", placeholder="Ex: Rua A, 100")
        manual_seq = st.text_input("Sequência Manual (Opcional)", placeholder="Ex: #A-1")

    else:
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            st.markdown("##### 📄 1. Endereço")
            tipo_e = st.radio("Tipo E:", ["Arquivo", "Texto"], horizontal=True, key="tipo_e")
            if tipo_e == "Arquivo":
                foto_end = st.file_uploader("Arq End", type=["png", "jpg", "jpeg"], key="up_e")
            else:
                manual_end = st.text_input("Digite o Endereço:", key="txt_end")

        with col_u2:
            st.markdown("##### 🔢 2. Sequência")
            tipo_s = st.radio("Tipo S:", ["Arquivo", "Texto"], horizontal=True, key="tipo_s")
            if tipo_s == "Arquivo":
                foto_seq = st.file_uploader("Arq Seq", type=["png", "jpg", "jpeg"], key="up_s")
            else:
                manual_seq = st.text_input("Digite a Sequência:", key="txt_seq")

    st.markdown("")
    if st.button("📥 Adicionar Pacote à Fila", type="primary", use_container_width=True):
        if foto_end or foto_seq or manual_end or manual_seq:
            st.session_state.pacotes.append({
                "Seq": manual_seq if manual_seq else "PENDENTE_PROCESSAR",
                "Rastreio": f"PKG_{datetime.now().strftime('%H%M%S')}",
                "Endereço": manual_end if manual_end else "Aguardando IA...",
                "CEP": "",
                "Horário": datetime.now().strftime("%H:%M:%S"),
                "Status": "Pendente",
                "bytes_end": foto_end.getvalue() if foto_end else None,
                "bytes_seq": foto_seq.getvalue() if foto_seq else None,
                "manual": True if (manual_end and manual_seq) else False
            })
            salvar_historico()
            st.success("Pacote adicionado com sucesso!")
            st.rerun()
        else:
            st.warning("Forneça pelo menos a foto ou o texto de endereço/sequência.")

    pendentes_IA = [p for p in st.session_state.pacotes if p.get("Seq") == "PENDENTE_PROCESSAR" or "Aguardando" in p.get("Endereço", "")]
    
    if pendentes_IA:
        st.markdown("---")
        if st.button(f"⚡ Processar Fila com IA ({len(pendentes_IA)} pendentes)", type="primary", use_container_width=True):
            with st.spinner("Processando imagens com IA..."):
                try:
                    genai.configure(api_key=CHAVE_API)
                    model = genai.GenerativeModel('gemini-3.6-flash')
                    
                    for p in st.session_state.pacotes:
                        if p.get("Seq") == "PENDENTE_PROCESSAR" or "Aguardando" in p.get("Endereço", ""):
                            imgs = []
                            if p.get("bytes_end"): imgs.append(Image.open(io.BytesIO(p["bytes_end"])))
                            if p.get("bytes_seq"): imgs.append(Image.open(io.BytesIO(p["bytes_seq"])))
                                
                            if imgs:
                                resp = model.generate_content(["Extraia rua, numero, bairro, cidade, estado, cep e sequencia (#A-1) em JSON puro com as chaves: rua, numero, bairro, cidade, estado, cep, sequencia.", *imgs])
                                dados = json.loads(resp.text.strip().replace("```json", "").replace("```", ""))
                                if p.get("Seq") == "PENDENTE_PROCESSAR":
                                    p["Seq"] = dados.get('sequencia') or "#S-N"
                                if "Aguardando" in p.get("Endereço", ""):
                                    r_rua, r_num, r_bairro, r_cep = dados.get('rua', ''), dados.get('numero', ''), dados.get('bairro', ''), dados.get('cep', '')
                                    p["Endereço"] = f"{r_rua}, {r_num} - {r_bairro}, {r_cep}" if r_rua else "Endereço não identificado"
                                    p["CEP"] = r_cep
                            p.pop("bytes_end", None)
                            p.pop("bytes_seq", None)
                            
                    salvar_historico()
                    st.success("Fila processada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar: {e}")

    st.markdown("---")
    st.markdown("### 📋 Lista de Pacotes")

    if st.session_state.pacotes:
        df = pd.DataFrame([{k: v for k, v in p.items() if k != 'bytes_end' and k != 'bytes_seq'} for p in st.session_state.pacotes])
        pendentes_df = df[df["Status"] == "Pendente"].reset_index(drop=True)
        
        st.write(f"Total: {len(df)} | Pendentes: {len(pendentes_df)}")
        
        for idx, row in df.iterrows():
            c1, c2 = st.columns([0.15, 0.85])
            with c1:
                marcado = st.checkbox("", value=(row["Status"] == "Entregue"), key=f"chk_{row['Rastreio']}_{idx}")
                if marcado != (row["Status"] == "Entregue"):
                    for p in st.session_state.pacotes:
                        if p.get("Rastreio") == row['Rastreio']: p["Status"] = "Entregue" if marcado else "Pendente"
                    salvar_historico()
                    st.rerun()
            with c2:
                estilo = "~~" if row["Status"] == "Entregue" else ""
                st.markdown(f"{estilo}**[{row['Seq']}]** {row['Endereço']}{estilo}")

        if not pendentes_df.empty:
            st.markdown("---")
            link_waze = f"https://waze.com/ul?q={urllib.parse.quote(str(pendentes_df.iloc[0]['Endereço']))}&navigate=yes"
            st.link_button(f"📍 Abrir Waze (Próximo: {pendentes_df.iloc[0]['Seq']})", link_waze, type="primary", use_container_width=True)

with aba_visual:
    st.markdown("### 👁️ Otimizador de Print")
    p_partida = st.text_input("Partida:", placeholder="Ex: Pino 1")
    print_m = st.file_uploader("Print do Mapa", type=["png", "jpg", "jpeg"])
    if print_m and st.button("🤖 Recalcular", use_container_width=True):
        with st.spinner("Analisando..."):
            genai.configure(api_key=CHAVE_API)
            resp = genai.GenerativeModel('gemini-3.6-flash').generate_content([f"Partida: {p_partida}. Otimize a rota.", Image.open(print_m)])
            st.write(resp.text)
