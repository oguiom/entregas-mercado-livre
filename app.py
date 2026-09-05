import streamlit as st
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import json
import urllib.parse
import os
import io

st.set_page_config(page_title="Rota Pro - Lote Flexível", layout="centered")

CHAVE_API = "AQ.Ab8RN6LHqgr4PrMWVjzL8M4N-c7NbcBdw_K3xil4lSeRoju1YA"
ARQUIVO_HISTORICO = "historico_lote_flex.csv"

st.title("📦 Rota Pro - Captura Dupla Lado a Lado")

# --- GERENCIAMENTO DE ESTADO E HISTÓRICO ---
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

# --- MENU DE ABAS ---
aba_principal, aba_visual = st.tabs(["🚀 Cadastro Lado a Lado & Waze", "👁️ Otimizador Visual por Print"])

with aba_principal:
    with st.expander("🧪 Gerenciamento"):
        st.button("Limpar Todos os Pacotes", on_click=limpar_tabela, use_container_width=True)

    st.markdown("### 1. Novo Pacote (Lado a Lado)")
    st.info("Para cada pacote, escolha se prefere usar a câmera ou upload nas duas etiquetas, jogue na fila e processe com a IA quando quiser!")

    with st.form("form_duplo_lote", clear_on_submit=True):
        col_c1, col_c2 = st.columns(2)
        
        # --- COLUNA 1: ENDEREÇO ---
        with col_c1:
            st.markdown("#### 📄 1. Endereço")
            tipo_origem_end = st.radio("Origem:", ["Câmera", "Upload"], key="origem_end", horizontal=True)
            if tipo_origem_end == "Câmera":
                foto_end = st.camera_input("Tirar foto Endereço", key="cam_e")
            else:
                foto_end = st.file_uploader("Enviar Endereço", type=["png", "jpg", "jpeg"], key="up_e")

        # --- COLUNA 2: SEQUÊNCIA (#A-1) ---
        with col_c2:
            st.markdown("#### 🔢 2. Sequência (#A-1)")
            tipo_origem_seq = st.radio("Origem:", ["Câmera", "Upload"], key="origem_seq", horizontal=True)
            if tipo_origem_seq == "Câmera":
                foto_seq = st.camera_input("Tirar foto Sequência", key="cam_s")
            else:
                foto_seq = st.file_uploader("Enviar Sequência", type=["png", "jpg", "jpeg"], key="up_s")

        btn_adicionar = st.form_submit_button("📥 Adicionar Pacote à Fila", type="secondary", use_container_width=True)
        
        if btn_adicionar:
            if foto_end or foto_seq:
                st.session_state.pacotes.append({
                    "Seq": "PENDENTE_PROCESSAR",
                    "Rastreio": f"PKG_{datetime.now().strftime('%H%M%S')}",
                    "Endereço": "Aguardando processamento da IA...",
                    "CEP": "",
                    "Horário": datetime.now().strftime("%H:%M:%S"),
                    "Status": "Pendente",
                    "bytes_end": foto_end.getvalue() if foto_end else None,
                    "bytes_seq": foto_seq.getvalue() if foto_seq else None
                })
                salvar_historico()
                st.success("Pacote adicionado à fila com sucesso!")
                st.rerun()
            else:
                st.warning("Envie pelo menos uma das fotos do pacote.")

    # --- BOTÃO DE PROCESSAR LOTE COM IA ---
    pendentes_IA = [p for p in st.session_state.pacotes if p.get("Seq") == "PENDENTE_PROCESSAR"]
    
    if pendentes_IA:
        st.markdown("---")
        st.warning(f"⚠️ Você tem {len(pendentes_IA)} pacotes na fila aguardando processamento.")
        if st.button("⚡ Processar Fila Inteira com IA Agora", type="primary", use_container_width=True):
            with st.spinner("A IA está varrendo os pacotes em lote..."):
                try:
                    genai.configure(api_key=CHAVE_API)
                    model = genai.GenerativeModel('gemini-3.6-flash')
                    
                    for p in st.session_state.pacotes:
                        if p.get("Seq") == "PENDENTE_PROCESSAR":
                            imgs_para_ia = []
                            if p.get("bytes_end"):
                                imgs_para_ia.append(Image.open(io.BytesIO(p["bytes_end"])))
                            if p.get("bytes_seq"):
                                imgs_para_ia.append(Image.open(io.BytesIO(p["bytes_seq"])))
                                
                            if imgs_para_ia:
                                prompt = """
                                Analise estas imagens de etiquetas de um pacote de entrega.
                                Extraia o endereço completo (rua, numero, bairro, cidade, estado, cep) e o código de sequência (ex: '#A-1').
                                Retorne APENAS um objeto JSON válido, sem markdown, com as chaves exatas: 
                                "rua", "numero", "bairro", "cidade", "estado", "cep", "sequencia".
                                Se algum dado faltar, deixe em branco.
                                """
                                response = model.generate_content([prompt] + imgs_para_ia)
                                texto_limpo = response.text.strip().replace("```json", "").replace("```", "")
                                dados = json.loads(texto_limpo)
                                
                                r_rua = dados.get('rua', '')
                                r_num = dados.get('numero', '')
                                r_bairro = dados.get('bairro', '')
                                r_cep = dados.get('cep', '')
                                seq_lida = dados.get('sequencia', '')
                                
                                if seq_lida:
                                    p["Seq"] = seq_lida
                                else:
                                    p["Seq"] = "#S-N"
                                    
                                if r_rua or r_num:
                                    p["Endereço"] = f"{r_rua}, {r_num} - {r_bairro}, {r_cep}"
                                    p["CEP"] = r_cep
                                else:
                                    p["Endereço"] = "Endereço não identificado claramente"
                                    
                            # Limpa os binários salvos
                            p.pop("bytes_end", None)
                            p.pop("bytes_seq", None)
                            
                    salvar_historico()
                    st.success("🎉 Todos os pacotes da fila foram processados pela IA!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar lote: {e}")

    st.markdown("---")
    st.markdown("### 📋 Pacotes da Rota Atual")

    if st.session_state.pacotes:
        df = pd.DataFrame([{k: v for k, v in p.items() if k != 'bytes_end' and k != 'bytes_seq'} for p in st.session_state.pacotes])
        pendentes_df = df[df["Status"] == "Pendente"].reset_index(drop=True)
        
        st.write(f"**Total:** {len(df)} | **Pendentes:** {len(pendentes_df)}")
        
        for idx, row in df.iterrows():
            col_chk, col_txt = st.columns([0.1, 0.9])
            with col_chk:
                status_atual = True if row["Status"] == "Entregue" else False
                marcado = st.checkbox("", value=status_atual, key=f"chk_{row['Rastreio']}_{idx}")
                if marcado != status_atual:
                    for p in st.session_state.pacotes:
                        if p.get("Rastreio") == row['Rastreio']:
                            p["Status"] = "Entregue" if marcado else "Pendente"
                    salvar_historico()
                    st.rerun()
            with col_txt:
                estilo = "~~" if row["Status"] == "Entregue" else ""
                st.markdown(f"{estilo}**[Seq: {row['Seq']}]** - {row['Endereço']} ({row['Horário']}){estilo}")

        if not pendentes_df.empty:
            st.markdown("---")
            st.markdown("### 📍 Waze Dinâmico (Individual)")
            proximo_endereco = urllib.parse.quote(str(pendentes_df.iloc[0]["Endereço"]))
            link_waze = f"https://waze.com/ul?q={proximo_endereco}&navigate=yes"
            st.link_button(f"Waze: Próximo (Seq: {pendentes_df.iloc[0]['Seq']})", link_waze, type="primary", use_container_width=True)

with aba_visual:
    st.markdown("### 👁️ Otimizador Inteligente por Print de Mapa com Âncora")
    ponto_partida = st.text_input("Onde você está ou qual o pino de início?", placeholder="Ex: Pino 1")
    print_mapa = st.file_uploader("Envie o Print do Mapa", type=["png", "jpg", "jpeg"], key="print_mapa_upload")
    if print_mapa:
        img_mapa = Image.open(print_mapa)
        st.image(img_mapa, caption="Mapa enviado", use_column_width=True)
        if st.button("🤖 Recalcular Rota", type="primary"):
            with st.spinner("Calculando..."):
                genai.configure(api_key=CHAVE_API)
                modelo_visao = genai.GenerativeModel('gemini-3.6-flash')
                resp = modelo_visao.generate_content([f"Partida: {ponto_partida}. Reordene os pinos sem zigue-zague.", img_mapa])
                st.write(resp.text)