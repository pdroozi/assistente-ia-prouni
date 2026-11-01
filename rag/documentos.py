"""
Leitura e divisão dos documentos oficiais em trechos.

Formatos aceitos na pasta documentos/:
  * .pdf  -> lido página por página (a página vira a referência da citação)
  * .html / .htm -> páginas salvas do site do Planalto ou do MEC
  * .txt / .md   -> texto simples
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, asdict
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader

TAMANHO_TRECHO = 1200   # caracteres por trecho (~250 palavras)
SOBREPOSICAO = 200      # repete o fim do trecho anterior para não cortar uma regra ao meio


@dataclass
class Trecho:
    id: int
    documento: str      # título amigável (ex.: "Lei do ProUni (Lei 11.096/2005)")
    programa: str       # ProUni, FIES, Sisu ou Geral
    arquivo: str
    url: str
    pagina: int | None  # só para PDFs
    texto: str

    def referencia(self) -> str:
        return f"{self.documento}, p. {self.pagina}" if self.pagina else self.documento


def limpar(texto: str) -> str:
    texto = texto.replace(" ", " ")
    texto = re.sub(r"-\n(?=[a-zà-ú])", "", texto)          # junta palavras hifenizadas na quebra de linha
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def corrigir_ligaturas(texto: str) -> str:
    """PDFs gerados pelo SEI (sistema do governo) usam ligaturas tipográficas:
    'ﬁ' vira 'fi', e o 'ti' costuma sair como '<' ('sele<vo' -> 'seletivo')."""
    for ligatura, letras in {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}.items():
        texto = texto.replace(ligatura, letras)
    return re.sub(r"(?<=[A-Za-zÀ-ÿ])<|<(?=[a-zà-ÿ])", "ti", texto)


def ler_pdf(caminho: Path) -> list[tuple[int | None, str]]:
    leitor = PdfReader(str(caminho))
    return [(i + 1, limpar(corrigir_ligaturas(p.extract_text() or ""))) for i, p in enumerate(leitor.pages)]


def decodificar(dados: bytes) -> str:
    """As páginas do Planalto vêm em Windows-1252 e muitas vezes sem declarar a codificação."""
    for codificacao in ("utf-8", "cp1252"):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return dados.decode("latin-1", errors="replace")


def ler_html(caminho: Path) -> list[tuple[int | None, str]]:
    sopa = BeautifulSoup(decodificar(caminho.read_bytes()), "html.parser")
    # No site do Planalto, o texto revogado aparece riscado (tag <strike> ou estilo
    # "line-through"). Ele não pode virar resposta: removemos antes de indexar.
    for tag in sopa.find_all(["strike", "s", "del", "script", "style", "nav", "header", "footer"]):
        tag.decompose()
    for tag in sopa.find_all(style=re.compile(r"line-through", re.I)):
        tag.decompose()
    # quebras de linha do código-fonte HTML não são quebras de parágrafo
    for trecho in sopa.find_all(string=True):
        trecho.replace_with(re.sub(r"\s+", " ", str(trecho)))
    for bloco in sopa.find_all(["p", "div", "li", "br", "h1", "h2", "h3", "tr"]):
        bloco.insert_after("\n")
    return [(None, limpar(sopa.get_text()))]


def ler_texto(caminho: Path) -> list[tuple[int | None, str]]:
    return [(None, limpar(caminho.read_text(encoding="utf-8", errors="replace")))]


LEITORES = {".pdf": ler_pdf, ".html": ler_html, ".htm": ler_html, ".txt": ler_texto, ".md": ler_texto}


def dividir(texto: str) -> list[str]:
    """Divide em trechos de ~TAMANHO_TRECHO caracteres, preferindo cortar entre parágrafos."""
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n|\n(?=Art\. )", texto) if p.strip()]
    trechos, atual = [], ""
    for p in paragrafos:
        if len(atual) + len(p) + 1 <= TAMANHO_TRECHO:
            atual = f"{atual}\n{p}".strip()
            continue
        if atual:
            trechos.append(atual)
            atual = atual[-SOBREPOSICAO:] + "\n" + p if len(p) < TAMANHO_TRECHO else ""
        while len(p) > TAMANHO_TRECHO:               # parágrafo gigante: corta em janelas
            corte = p.rfind(" ", 0, TAMANHO_TRECHO)
            corte = corte if corte > TAMANHO_TRECHO // 2 else TAMANHO_TRECHO
            trechos.append(p[:corte].strip())
            p = p[max(corte - SOBREPOSICAO, 0):]
        if not atual:
            atual = p
    if atual.strip():
        trechos.append(atual.strip())
    return [t for t in trechos if len(t) > 80]       # descarta cabeçalhos e rodapés soltos


def ler_fontes(arquivo_csv: Path) -> dict[str, dict]:
    """fontes.csv descreve cada arquivo: título, programa e link oficial (para a citação)."""
    with open(arquivo_csv, encoding="utf-8") as f:
        return {linha["arquivo"]: linha for linha in csv.DictReader(f, delimiter=";")}


def carregar_trechos(pasta: Path, fontes: dict[str, dict]) -> list[Trecho]:
    trechos: list[Trecho] = []
    for caminho in sorted(pasta.iterdir()):
        leitor = LEITORES.get(caminho.suffix.lower())
        if not leitor:
            continue
        info = fontes.get(caminho.name, {})
        paginas = leitor(caminho)
        antes = len(trechos)
        for pagina, texto in paginas:
            for pedaco in dividir(texto):
                trechos.append(Trecho(
                    id=len(trechos), documento=info.get("titulo") or caminho.stem,
                    programa=info.get("programa") or "Geral", arquivo=caminho.name,
                    url=info.get("url", ""), pagina=pagina, texto=pedaco))
        print(f"  {caminho.name:<45} {len(paginas):>3} página(s) -> {len(trechos) - antes:>4} trechos")
        if len(trechos) == antes:
            print("    ATENÇÃO: nenhum texto extraído (PDF escaneado como imagem?)")
    return trechos


def para_dict(t: Trecho) -> dict:
    return asdict(t)
