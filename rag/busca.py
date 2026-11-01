"""
Busca dos trechos mais relevantes para uma pergunta, com BM25.

BM25 é o algoritmo clássico de busca por palavras (o mesmo princípio do
Elasticsearch). Para textos de lei, cheios de termos exatos como "renda per
capita" e "bolsa parcial", ele funciona muito bem e não precisa de nenhuma API.
"""
from __future__ import annotations

import re
import unicodedata

from rank_bm25 import BM25Okapi

PARADAS = set("""
a ao aos as com como da das de do dos e ela ele em entre essa esse esta este eu foi ha isso ja la mais mas me
mesmo meu minha muito na nas nao nem no nos o os ou para pela pelas pelo pelos por qual quais quando que quem se
sem ser seu sua so sobre tambem tem ter um uma umas uns voce voces vou eh pra posso pode preciso quero sao estou
""".split())

SINONIMOS = {  # o estudante escreve de um jeito, a lei de outro
    "faculdade": "educacao superior", "universidade": "educacao superior", "particular": "privada",
    "salario": "salario-minimo", "documentos": "documentacao comprovacao", "nota": "desempenho enem",
    "cotas": "reserva vagas", "pobre": "renda", "dinheiro": "renda", "prova": "enem",
}


def normalizar(texto: str) -> list[str]:
    """Minúsculas, sem acento, sem palavras vazias e com 'radical' simples (7 letras)."""
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    tokens = re.findall(r"[a-z0-9]+(?:[.,/][0-9]+)*", texto)
    return [t[:7] for t in tokens if t not in PARADAS and len(t) > 1]


def expandir(pergunta: str) -> str:
    extras = [v for k, v in SINONIMOS.items() if re.search(rf"\b{k}", pergunta.lower())]
    return " ".join([pergunta, *extras])


class Buscador:
    def __init__(self, trechos: list[dict]):
        self.trechos = trechos
        self.bm25 = BM25Okapi([normalizar(f"{t['documento']} {t['texto']}") for t in trechos])

    def buscar(self, pergunta: str, k: int = 6, programa: str | None = None) -> list[dict]:
        notas = self.bm25.get_scores(normalizar(expandir(pergunta)))
        ordem = sorted(range(len(notas)), key=lambda i: notas[i], reverse=True)
        resultado = []
        for i in ordem:
            if notas[i] <= 0:
                break
            if programa and self.trechos[i]["programa"] not in (programa, "Geral"):
                continue
            resultado.append({**self.trechos[i], "relevancia": round(float(notas[i]), 2)})
            if len(resultado) == k:
                break
        return resultado
