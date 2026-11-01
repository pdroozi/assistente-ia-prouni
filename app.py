"""
Tira-dúvidas ProUni, FIES e Sisu
Interface de chat (Streamlit) do assistente com RAG.

    streamlit run app.py
"""
import json
import os
from pathlib import Path

import streamlit as st

from rag.busca import Buscador
from rag.gerador import gerar_resposta, montar_prompt

RAIZ = Path(__file__).parent
EXEMPLOS = [
    "Qual a renda máxima para ter bolsa integral no ProUni?",
    "Quem já tem diploma pode se inscrever no ProUni?",
    "Como funcionam as cotas para quem estudou em escola pública?",
    "O que é o FIES e quem pode pedir?",
]

st.set_page_config(page_title="Tira-dúvidas ProUni, FIES e Sisu", page_icon="🎓", layout="centered")


@st.cache_resource
def carregar_buscador() -> tuple[Buscador, str]:
    dados = json.loads((RAIZ / "indice" / "trechos.json").read_text(encoding="utf-8"))
    return Buscador(dados["trechos"]), dados["gerado_em"]


def segredo(nome: str) -> str | None:
    try:
        return st.secrets.get(nome) or os.environ.get(nome)
    except Exception:  # sem arquivo secrets.toml
        return os.environ.get(nome)


def mostrar_fontes(trechos: list[dict]) -> None:
    with st.expander(f"Trechos oficiais usados ({len(trechos)})"):
        for i, t in enumerate(trechos, start=1):
            ref = t["documento"] + (f", página {t['pagina']}" if t.get("pagina") else "")
            st.markdown(f"**[{i}] {ref}**" + (f" · [abrir documento]({t['url']})" if t.get("url") else ""))
            resumo = t["texto"][:500] + ("…" if len(t["texto"]) > 500 else "")
            st.caption(resumo)


buscador, data_indice = carregar_buscador()
chave = segredo("GEMINI_API_KEY")
modelo = segredo("GEMINI_MODELO")

# ---------------- barra lateral ----------------
with st.sidebar:
    st.markdown("### Sobre")
    st.write("Este assistente responde dúvidas sobre ProUni, FIES e Sisu usando **somente** trechos de leis "
             "e editais oficiais, e mostra de onde tirou cada informação.")
    programa = st.radio("Buscar em", ["Todos", "ProUni", "FIES", "Sisu"], horizontal=True)
    st.markdown("### Documentos consultados")
    docs = {}
    for t in buscador.trechos:
        docs.setdefault(t["documento"], t.get("url"))
    for nome, url in docs.items():
        st.markdown(f"- [{nome}]({url})" if url else f"- {nome}")
    st.caption(f"Índice atualizado em {data_indice.split('-')[2]}/{data_indice.split('-')[1]}/{data_indice.split('-')[0]}.")
    st.markdown("### Privacidade")
    st.caption("Não digite CPF, renda exata, endereço ou outros dados pessoais. As perguntas são enviadas à API "
               "do Google Gemini para gerar a resposta.")
    st.caption("Projeto de extensão universitária (UNIP). Não é um canal oficial do MEC: confirme sempre no edital vigente.")

# ---------------- conteúdo principal ----------------
st.title("Tira-dúvidas ProUni, FIES e Sisu")
st.write("Pergunte com suas palavras. As respostas vêm dos documentos oficiais, com a fonte de cada informação.")

if "mensagens" not in st.session_state:
    st.session_state.mensagens = []

for m in st.session_state.mensagens:
    with st.chat_message("user" if m["papel"] == "usuario" else "assistant"):
        st.markdown(m["texto"])
        if m.get("trechos"):
            mostrar_fontes(m["trechos"])

pergunta = st.chat_input("Ex.: posso usar o ProUni se estudei em escola particular com bolsa?")
if not st.session_state.mensagens and not pergunta:
    st.markdown("**Experimente perguntar:**")
    colunas = st.columns(2)
    for i, exemplo in enumerate(EXEMPLOS):
        if colunas[i % 2].button(exemplo, use_container_width=True):
            pergunta = exemplo

if pergunta:
    historico = st.session_state.mensagens[-4:]
    st.session_state.mensagens.append({"papel": "usuario", "texto": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        # a pergunta anterior ajuda a busca em perguntas de seguimento ("e para o FIES?")
        anterior = next((m["texto"] for m in reversed(historico) if m["papel"] == "usuario"), "")
        trechos = buscador.buscar(f"{pergunta} {anterior}".strip(), k=6,
                                  programa=None if programa == "Todos" else programa)
        if not chave:
            texto = ("A chave da API do Gemini não foi configurada. Veja no README como criar a chave gratuita "
                     "e colocá-la em `.streamlit/secrets.toml`.")
        elif not trechos:
            texto = ("Não encontrei nada sobre isso nos documentos oficiais que tenho. Tente perguntar de outro jeito "
                     "ou confira no site oficial do programa, no portal do MEC (gov.br/mec).")
        else:
            with st.spinner("Lendo os documentos oficiais…"):
                try:
                    texto = gerar_resposta(montar_prompt(pergunta, trechos, historico), chave, modelo)
                except Exception as erro:  # cota, rede, chave inválida
                    mensagem = str(erro)
                    if "429" in mensagem or "RESOURCE_EXHAUSTED" in mensagem:
                        texto = "Muitas perguntas ao mesmo tempo: o limite gratuito da API foi atingido. Tente de novo em um minuto."
                    elif "API key" in mensagem or "401" in mensagem or "403" in mensagem:
                        texto = "A chave da API do Gemini foi recusada. Confira se ela foi copiada inteira."
                    else:
                        texto = f"Não consegui gerar a resposta agora ({type(erro).__name__}). Tente de novo."
        st.markdown(texto)
        if trechos and chave:
            mostrar_fontes(trechos)
    st.session_state.mensagens.append({"papel": "assistente", "texto": texto, "trechos": trechos if chave else []})
