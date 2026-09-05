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

# CSS customizado para compactar e melhorar a visão no celular
st.markdown("""
    <style>
        .stButton button { width: 100%; border-radius: 6px; font-weight: bold; }
        .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 700px; }
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

    with st.form("form_duplo_lote", clear_on_submit=True):
        st.markdown("#### 📄 1. Endereço")
        tipo_origem_end = st.radio("Origem Endereço:", ["Câmera", "Upload"], key="origem_end", horizontal=True)
        foto_end = st.camera_input("Foto Endereço", key="cam_e") if tipo_origem_end == "Câmera" else st.file_uploader("Arquivo Endereço", type=["png", "jpg", "jpeg"], key="up_e")

        st.markdown("#### 🔢 2. Sequência (#A-1)")
        tipo_origem_seq = st.radio("Origem Sequência:", ["Câmera", "Upload"], key="origem_seq", horizontal=True)
        foto_seq = st.camera_input("Foto Sequência", key="cam_s") if tipo_origem_seq == "Câmera" else st.file_uploader("Arquivo Sequência", type=["png", "jpg", "jpeg"], key="up_s")

        btn_adicionar = st.form_submit_button("📥 Adicionar à Fila", type="primary")
        
        if btn_adicionar:
            if foto_end or foto_seq:
                st.session_state.pacotes.append({
                    "Seq": "PENDENTE_PROCESSAR",
                    "Rastreio": f"PKG_{datetime.now().strftime('%H%M%S')}",
                    "Endereço": "Aguardando IA...",
                    "CEP": "",
                    "Horário": datetime.now().strftime("%H:%M:%S"),
                    "Status": "Pendente",
                    "bytes_end": foto_end.getvalue() if foto_end else None,
                    "bytes_seq": foto_seq.getvalue() if foto_seq else None
                })
                salvar_historico()
                st.success("Adicionado à fila!")
                st.rerun()
            else:
                st.warning("Envie ao menos uma foto.")

    # Correção do parêntese feita aqui:
    pendentes_IA = [p for p in st.session_state.pacotes if p.get("Seq") == "PENDENTE_PROCESSAR"]
    
    if pendentes_IA:
        st.markdown("---")
        if st.button(f"⚡ Processar Fila ({len(pendentes_IA)} itens) com IA", type="primary"):
            with st.spinner("Processando..."):
                try:
                    genai.configure(api_key=CHAVE_API)
                    model = genai.GenerativeModel('gemini-3.6-flash')
                    
                    for p in st.session_state.pacotes:
                        if p.get("Seq") == "PENDENTE_PROCESSAR":
                            imgs = []
                            if p.get("bytes_end"): imgs.append(Image.open(io.BytesIO(p["bytes_end"])))
                            if p.get("bytes_seq"): imgs.append(Image.open(io.BytesIO(p["bytes_seq"])))
                                
                            if imgs:
                                resp = model.generate_content(["Extraia rua, numero, bairro, cidade, estado, cep e sequencia (#A-1) em JSON puro com as chaves: rua, numero, bairro, cidade, estado, cep, sequencia.", *imgs])
                                dados = json.loads(resp.text.strip().replace("```json", "").replace("```", ""))
                                p["Seq"] = dados.get('sequencia') or "#S-N"
                                r_rua, r_num, r_bairro, r_cep = dados.get('rua', ''), dados.get('numero', ''), dados.get('bairro', ''), dados.get('cep', '')
                                p["Endereço"] = f"{r_rua}, {r_num} - {r_bairro}, {r_cep}" if r_rua else "Endereço não identificado"
                                p["CEP"] = r_cep
                            p.pop("bytes_end", None)
                            p.pop("bytes_seq", None)
                            
                    salvar_historico()
                    st.success("Processado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

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
            st.link_button(f"📍 Abrir Waze (Próximo: {pendentes_df.iloc[0]['Seq']})", link_waze, type="primary")

with aba_visual:
    st.markdown("### 👁️ Otimizador de Print")
    p_partida = st.text_input("Partida:", placeholder="Ex: Pino 1")
    print_m = st.file_uploader("Print do Mapa", type=["png", "jpg", "jpeg"])
    if print_m and st.button("🤖 Recalcular"):
        with st.spinner("Analisando..."):
            genai.configure(api_key=CHAVE_API)
            resp = genai.GenerativeModel('gemini-3.6-flash').generate_content([f"Partida: {p_partida}. Otimize a rota.", Image.open(print_m)])
            st.write(resp.text)
