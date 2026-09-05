import streamlit as st
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import json
import urllib.parse
import os
import io

st.set_page_config(page_title="Rota Pro Mobile - 2 Passos", layout="centered")

CHAVE_API = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
ARQUIVO_HISTORICO = "historico_lote_2passos.csv"

# CSS para deixar a interface limpa e otimizada para toque no celular
st.markdown("""
    <style>
        .stButton button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
        .block-container { padding-top: 0.5rem; padding-bottom: 2rem; max-width: 700px; }
    </style>
""", unsafe_allow_html=True)

st.title("📦 Rota Pro - Cadastro em 2 Passos")

if 'pacotes' not in st.session_state:
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            df_hist = pd.read_csv(ARQUIVO_HISTORICO)
            st.session_state.pacotes = df_hist.to_dict('records')
        except:
            st.session_state.pacotes = []
    else:
        st.session_state.pacotes = []

# Estado de controle do fluxo de 2 passos
if 'etapa_cadastro' not in st.session_state:
    st.session_state.etapa_cadastro = 1
if 'temp_bytes_end' not in st.session_state:
    st.session_state.temp_bytes_end = None

def salvar_historico():
    if st.session_state.pacotes:
        dados_limpos = [{k: v for k, v in p.items() if k != 'bytes_end' and k != 'bytes_seq'} for p in st.session_state.pacotes]
        df = pd.DataFrame(dados_limpos)
        df.to_csv(ARQUIVO_HISTORICO, index=False)

def limpar_tabela():
    st.session_state.pacotes = []
    st.session_state.etapa_cadastro = 1
    st.session_state.temp_bytes_end = None
    if os.path.exists(ARQUIVO_HISTORICO):
        os.remove(ARQUIVO_HISTORICO)

aba_principal, aba_visual = st.tabs(["🚀 Cadastro Rápido", "👁️ Mapa"])

with aba_principal:
    with st.expander("⚙️ Opções"):
        st.button("Limpar Todos os Pacotes", on_click=limpar_tabela)

    # --- FLUXO EM 2 PASSOS ---
    if st.session_state.etapa_cadastro == 1:
        st.markdown("### 📄 Passo 1 de 2: Etiqueta de Endereço")
        
        metodo_1 = st.radio("Como quer enviar o Endereço?", ["📸 Câmera", "📁 Upload de Arquivo", "✍️ Digitar Manual"], horizontal=True, key="m1")
        
        foto_end = None
        texto_end = ""
        
        if metodo_1 == "📸 Câmera":
            foto_end = st.camera_input("Tirar foto do Endereço", key="cam_1")
        elif metodo_1 == "📁 Upload de Arquivo":
            foto_end = st.file_uploader("Selecionar foto do Endereço", type=["png", "jpg", "jpeg"], key="up_1")
        else:
            texto_end = st.text_input("Digite o Endereço completo:", placeholder="Ex: Rua Cardeal Arcoverde, 174")

        st.markdown("")
        if st.button("Avançar para Sequência ➡️", type="primary"):
            if foto_end or texto_end:
                if foto_end:
                    st.session_state.temp_bytes_end = foto_end.getvalue()
                else:
                    st.session_state.temp_bytes_end = texto_end # Armazena texto temporariamente se for manual
                st.session_state.etapa_cadastro = 2
                st.rerun()
            else:
                st.warning("Por favor, capture ou digite o endereço antes de avançar.")

    elif st.session_state.etapa_cadastro == 2:
        st.markdown("### 🔢 Passo 2 de 2: Etiqueta de Sequência (#A-1)")
        
        metodo_2 = st.radio("Como quer enviar a Sequência?", ["📸 Câmera", "📁 Upload de Arquivo", "✍️ Digitar Manual"], horizontal=True, key="m2")
        
        foto_seq = None
        texto_seq = ""
        
        if metodo_2 == "📸 Câmera":
            foto_seq = st.camera_input("Tirar foto da Sequência", key="cam_2")
        elif metodo_2 == "📁 Upload de Arquivo":
            foto_seq = st.file_uploader("Selecionar foto da Sequência", type=["png", "jpg", "jpeg"], key="up_2")
        else:
            texto_seq = st.text_input("Digite a Sequência:", placeholder="Ex: #A-1")

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("⬅️ Voltar"):
                st.session_state.etapa_cadastro = 1
                st.rerun()
        with col_b2:
            if st.button("📥 Salvar Pacote na Fila", type="primary"):
                if foto_seq or texto_seq:
                    is_manual_end = isinstance(st.session_state.temp_bytes_end, str)
                    is_manual_seq = isinstance(texto_seq, str) and len(texto_seq) > 0
                    
                    st.session_state.pacotes.append({
                        "Seq": texto_seq if is_manual_seq else "PENDENTE_PROCESSAR",
                        "Rastreio": f"PKG_{datetime.now().strftime('%H%M%S')}",
                        "Endereço": st.session_state.temp_bytes_end if is_manual_end else "Aguardando IA...",
                        "CEP": "",
                        "Horário": datetime.now().strftime("%H:%M:%S"),
                        "Status": "Pendente",
                        "bytes_end": None if is_manual_end else st.session_state.temp_bytes_end,
                        "bytes_seq": None if is_manual_seq else (foto_seq.getvalue() if foto_seq else None)
                    })
                    
                    # Reseta para o próximo pacote
                    st.session_state.etapa_cadastro = 1
                    st.session_state.temp_bytes_end = None
                    salvar_historico()
                    st.success("Pacote adicionado com sucesso! Pronto para o próximo.")
                    st.rerun()
                else:
                    st.warning("Por favor, capture ou digite a sequência.")

    # --- PROCESSAMENTO DA IA EM LOTE ---
    pendentes_IA = [p for p in st.session_state.pacotes if p.get("Seq") == "PENDENTE_PROCESSAR" or "Aguardando" in p.get("Endereço", "")]
    
    if pendentes_IA:
        st.markdown("---")
        if st.button(f"⚡ Processar Fila com IA ({len(pendentes_IA)} pendentes)", type="primary", use_container_width=True):
            with st.spinner("A IA está lendo as fotos..."):
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
