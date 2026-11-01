"""
Monta o prompt com os trechos encontrados e pede a resposta ao Gemini.

A regra de ouro do RAG está nas instruções: o modelo só pode responder com
base nos trechos oficiais e precisa citar de onde tirou cada informação.
"""
from __future__ import annotations

import os

MODELO_PADRAO = "gemini-3.5-flash-lite"

INSTRUCOES = """Você é um assistente de orientação para estudantes brasileiros sobre ProUni, FIES e Sisu.

Regras:
1. Responda APENAS com base nos TRECHOS OFICIAIS fornecidos. Não use conhecimento próprio sobre os programas.
2. Cite a fonte de cada informação com o número do trecho entre colchetes, por exemplo [2].
3. Se os trechos não trazem a resposta, diga claramente que não encontrou essa informação nos documentos
   e oriente a pessoa a confirmar no site oficial do programa, no portal do MEC (gov.br/mec).
4. Escreva em português simples, para um estudante de ensino médio. Frases curtas. Explique termos como
   "renda per capita" quando aparecerem.
5. Datas e prazos mudam a cada edição: sempre que falar de prazo, lembre que é preciso conferir o edital vigente.
6. Nunca peça nem comente dados pessoais (CPF, renda exata, endereço).
"""


def montar_prompt(pergunta: str, trechos: list[dict], historico: list[dict] | None = None) -> str:
    partes = []
    if historico:
        conversa = "\n".join(f"{'Estudante' if m['papel'] == 'usuario' else 'Assistente'}: {m['texto']}"
                             for m in historico[-4:])
        partes.append(f"CONVERSA ATÉ AGORA:\n{conversa}")
    blocos = [f"[{i}] {t['documento']}" + (f", página {t['pagina']}" if t.get("pagina") else "") + f"\n{t['texto']}"
              for i, t in enumerate(trechos, start=1)]
    partes.append("TRECHOS OFICIAIS:\n\n" + "\n\n---\n\n".join(blocos) if blocos else "TRECHOS OFICIAIS: nenhum trecho encontrado.")
    partes.append(f"PERGUNTA DO ESTUDANTE: {pergunta}")
    return "\n\n".join(partes)


def gerar_resposta(prompt: str, chave_api: str, modelo: str | None = None) -> str:
    if os.environ.get("RAG_MODO_TESTE") == "1":   # usado só nos testes automáticos, sem chamar a API
        return "Resposta de teste montada a partir dos trechos [1] e [2]."

    from google import genai
    from google.genai import types

    cliente = genai.Client(api_key=chave_api)
    resposta = cliente.models.generate_content(
        model=modelo or MODELO_PADRAO,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCOES,
            temperature=0.2,          # baixa: queremos fidelidade ao texto, não criatividade
            max_output_tokens=900,
        ),
    )
    return (resposta.text or "").strip()
