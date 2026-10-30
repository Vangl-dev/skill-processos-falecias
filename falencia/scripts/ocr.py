#!/usr/bin/env python3
"""Passa OCR (Tesseract, português) nas páginas sem texto e grava no autos.db.

Uso:
  python3 ocr.py AUTOS.pdf PASTA_SAIDA --juizo             só peças do juízo (minutos)
  python3 ocr.py AUTOS.pdf PASTA_SAIDA --paginas 1-7790    um trecho (pode levar horas)
  python3 ocr.py AUTOS.pdf PASTA_SAIDA --tudo              todas as páginas sem texto

Opções: --processos N (padrão: núcleos - 1). Pode ser interrompido e retomado:
páginas que já passaram por OCR são puladas. Não usa IA.
Requer o Tesseract com o idioma "por" instalado.
"""
import argparse
import os
import sqlite3
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import fitz  # PyMuPDF

_doc = None


def _abrir(pdf):
    global _doc
    _doc = fitz.open(pdf)


def _ocr(pag):
    page = _doc[pag - 1]
    tp = page.get_textpage_ocr(language="por", dpi=200, full=True)
    return pag, tp.extractText().strip()


def faixa(s):
    a, _, b = s.partition("-")
    return int(a), int(b or a)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("saida")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--juizo", action="store_true")
    g.add_argument("--paginas")
    g.add_argument("--tudo", action="store_true")
    ap.add_argument("--processos", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()

    con = sqlite3.connect(Path(a.saida) / "autos.db")
    filtro = "n_chars < 50 AND ocr = 0"
    if a.juizo:
        filtro += " AND origem = 'juizo'"
    elif a.paginas:
        ini, fim = faixa(a.paginas)
        filtro += f" AND pag BETWEEN {ini} AND {fim}"
    pags = [r[0] for r in con.execute(f"SELECT pag FROM paginas WHERE {filtro} ORDER BY pag")]
    if not pags:
        print("Nenhuma página pendente de OCR nesse filtro.")
        return
    print(f"{len(pags)} páginas para OCR com {a.processos} processos...", flush=True)

    t0 = time.time()
    with ProcessPoolExecutor(a.processos, initializer=_abrir, initargs=(a.pdf,)) as ex:
        for i, (pag, texto) in enumerate(ex.map(_ocr, pags, chunksize=4), 1):
            con.execute("UPDATE paginas SET texto = ?, n_chars = ?, ocr = 1 WHERE pag = ?",
                        (texto, len(texto), pag))
            if i % 50 == 0 or i == len(pags):
                con.commit()
                resta = (time.time() - t0) / i * (len(pags) - i)
                print(f"  {i}/{len(pags)} (faltam ~{resta / 60:.0f} min)", flush=True)
    con.execute("INSERT INTO busca(busca) VALUES('rebuild')")
    con.commit()
    print("Pronto. Rode triagem.py de novo para atualizar os resultados.")


if __name__ == "__main__":
    sys.exit(main())
