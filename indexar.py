"""
Gera o índice de busca a partir dos documentos oficiais.

    python indexar.py

Lê documentos/ + fontes.csv e grava indice/trechos.json.
Rode de novo sempre que adicionar ou trocar um documento (ex.: edital novo).
"""
import json
from datetime import date
from pathlib import Path

from rag.documentos import carregar_trechos, ler_fontes, para_dict

RAIZ = Path(__file__).parent
PASTA_DOCS = RAIZ / "documentos"
ARQUIVO_FONTES = RAIZ / "fontes.csv"
ARQUIVO_INDICE = RAIZ / "indice" / "trechos.json"

if __name__ == "__main__":
    fontes = ler_fontes(ARQUIVO_FONTES)
    print(f"Lendo documentos de {PASTA_DOCS.name}/")
    trechos = carregar_trechos(PASTA_DOCS, fontes)
    sem_cadastro = sorted({t.arquivo for t in trechos} - set(fontes))
    if sem_cadastro:
        print(f"\nATENÇÃO: arquivos sem linha no fontes.csv (aparecem sem título e sem link): {sem_cadastro}")
    ARQUIVO_INDICE.parent.mkdir(exist_ok=True)
    ARQUIVO_INDICE.write_text(json.dumps(
        {"gerado_em": date.today().isoformat(), "trechos": [para_dict(t) for t in trechos]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(trechos)} trechos salvos em {ARQUIVO_INDICE.relative_to(RAIZ)}")
