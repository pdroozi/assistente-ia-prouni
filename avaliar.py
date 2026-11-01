"""
Avalia a busca sem gastar API: para cada pergunta de teste, confere se algum
dos trechos recuperados contém a informação esperada.

    python avaliar.py

Métrica: acerto@6 = % de perguntas em que a resposta certa está entre os 6
trechos enviados ao modelo. Se a busca não traz o trecho, o modelo não tem
como acertar, então este é o primeiro número a melhorar.
"""
import json
import unicodedata
from pathlib import Path

from rag.busca import Buscador

RAIZ = Path(__file__).parent
K = 6


def simples(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return " ".join("".join(c for c in t if unicodedata.category(c) != "Mn").split())


if __name__ == "__main__":
    trechos = json.loads((RAIZ / "indice" / "trechos.json").read_text(encoding="utf-8"))["trechos"]
    perguntas = json.loads((RAIZ / "avaliacao" / "perguntas.json").read_text(encoding="utf-8"))
    buscador = Buscador(trechos)
    acertos = 0
    for p in perguntas:
        achados = buscador.buscar(p["pergunta"], k=K)
        posicao = next((i for i, t in enumerate(achados, 1)
                        if any(simples(e) in simples(t["texto"]) for e in p["espera_algum"])), None)
        acertos += posicao is not None
        marca = f"ok (trecho {posicao})" if posicao else "FALHOU"
        print(f"{marca:<14} {p['pergunta']}")
        if not posicao and achados:
            print(f"{'':<14} 1º trecho veio de: {achados[0]['documento']}")
    print(f"\nAcerto@{K}: {acertos}/{len(perguntas)} ({acertos / len(perguntas):.0%})")
