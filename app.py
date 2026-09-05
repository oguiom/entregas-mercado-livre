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
ARQUIVO_HISTORICO = "historico_lote_2passos.csv"

# CSS limpo para celular
st.markdown("""
    <style>
        .stButton button { width: 100%; border-radius: 8px; font-weight: bold; height: 3.2em; }
        .block-container { padding-top: 0.5rem; padding-bottom: 2rem; max-width: 700px; }
    </style>
""", unsafe_allow_html=True)

st.title("📦 Rota Pro - 2 Passos")

if 'pacotes' not in st.session_state:
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            df_hist = pd.read_csv(ARQUIVO_HISTORICO)
            st.session_state.pacotes = df_hist.to_dict('records')
        except:
            st.session_state.pacotes = []
    else:
        st.session_state.pacotes = []

if 'etapa_cadastro' not in st.session_state:
    st.session_state.etapa_cadastro = 1
if 'temp_end' not in st.session_state:
    st.session_state.temp_end = None
if 'temp_end_tipo' not in st.session_state:
    st.session_state.temp_end_tipo = None

def salvar_historico():
    if st.session_state.pacotes:
        dados_limpos = [{k: v for k, v in p.items() if k != 'bytes_end' and k != 'bytes_seq'} for p in st.session_state.pacotes]
        df = pd.DataFrame(dados_limpos)
        df.to_csv(ARQUIVO_HISTORICO, index=False)

def limpar_tabela():
    st.session_state.pacotes = []
    st.session_state.etapa_cadastro = 1
    st.session_state.temp_end = None
    st.session_state.temp_end_tipo = None
    if os.path.exists(ARQUIVO_HISTORICO):
        os.remove(ARQUIVO_HISTORICO)

aba_principal, aba_visual = st.tabs(["🚀 Cadastro", "👁️ Mapa"])

with aba_principal:
    with st.expander("⚙️ Opções"):
        st.button("Limpar Todos os Pacotes", on_click=limpar_tabela)

    # --- PASSO 1: ENDEREÇO ---
    if st.session_state.etapa_cadastro == 1:
        st.markdown("### 📄 Passo 1 de 2: Endereço")
        st.info("💡 Dica: Use 'Tirar Foto / Upload' para abrir a câmera nativa do seu celular instantaneamente.")
        
        tipo_envio_e = st.radio("Como informar o Endereço?", ["📷 Tirar Foto / Upload", "✍️ Digitar Manual"], horizontal=True)
        
        val_end = None
        texto_end = ""
        
        if tipo_envio_e == "📷 Tirar Foto / Upload":
            val_end = st.file_uploader("Selecione ou tire a foto da rua/CEP", type=["png", "jpg", "jpeg"], key="up_e")
        else:
            texto_end = st.text_input("Digite o Endereço:", placeholder="Ex: Rua Cardeal Arcoverde, 174")

        st.markdown("")
        if st.button("Avançar para Sequência ➡️", type="primary"):
            if val_end or texto_end:
                if val_end:
                    st.session_state.temp_end = val_end.getvalue()
                    st.session_state.temp_end_tipo = "foto"
                else:
                    st.session_state.temp_end = texto_end
                    st.session_state.temp_end_tipo = "texto"
                
                st.session_state.etapa_cadastro = 2
                st.rerun()
            else:
                st.warning("⚠️ Insira a foto ou digite o endereço para continuar.")

    # --- PASSO 2: SEQUÊNCIA ---
    elif st.session_state.etapa_cadastro == 2:
        st.markdown("### 🔢 Passo 2 de 2: Sequência (#A-1)")
        
        tipo_envio_s = st.radio("Como informar a Sequência?", ["📷 Tirar Foto / Upload", "✍️ Digitar Manual"], horizontal=True)
        
        val_seq = None
        texto_seq = ""
        
        if tipo_envio_s == "📷 Tirar Foto / Upload":
            val_seq = st.file_uploader("Selecione ou tire a foto da etiqueta #A-1", type=["png", "jpg", "jpeg"], key="up_s")
        else:
            texto_seq = st.text_input("Digite a Sequência:", placeholder="Ex: #A-1")

        st.markdown("")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("⬅️ Voltar"):
                st.session_state.etapa_cadastro = 1
                st.rerun()
        with col_b2:
            if st.button("📥 Salvar na Fila", type="primary"):
                if val_seq or texto_seq:
                    end_val = st.session_state.temp_end
                    end_tipo = st.session_state.temp_end_tipo
                    
                    seq_val = val_seq.getvalue() if val_seq else texto_seq
                    seq_tipo = "foto" if val_seq else "texto"
                    
                    # Monta o registro
                    novo_pacote = {
                        "Seq": seq_val if seq_tipo == "texto" else "PENDENTE_PROCESSAR",
                        "Rastreio": f"PKG_{datetime.now().strftime('%H%M%S_%f')}",
                        "Endereço": end_val if end_tipo == "texto" else "Aguardando IA...",
                        "CEP": "",
                        "Horário": datetime.now().strftime("%H:%M:%S"),
                        "Status": "Pendente",
                        "bytes_end": end_val if end_tipo == "foto" else None,
                        "bytes_seq": seq_val if seq_tipo == "foto" else None
                    }
                    
                    st.session_state.pacotes.append(novo_pacote)
                    
                    # Reseta para o próximo pacote
                    st.session_state.etapa_cadastro = 1
                    st.session_state.temp_end = None
                    st.session_state.temp_end_tipo = None
                    
                    salvar_historico()
                    st.success("✅ Pacote salvo na fila com sucesso!")
                    st.rerun()
                else:
                    st.warning("⚠️ Insira a foto ou digite a sequência para salvar.")

    # --- PROCESSAR FILA COM IA ---
    pendentes_IA = [p for p in st.session_state.pacotes if p.get("Seq") == "PENDENTE_PROCESSAR" or "Aguardando" in p.get("Endereço", "")]
    
    if pendentes_IA:
        st.markdown("---")
        if st.button(f"⚡ Processar Fila com IA ({len(pendentes_IA)} pendentes)", type="primary", use_container_width=True):
            with st.spinner("A IA está varrendo os pacotes..."):
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
                    st.success("Fila processada!")
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
