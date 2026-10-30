#!/usr/bin/env python3
"""Extrai o texto e o carimbo do e-SAJ de cada página dos autos para um banco SQLite.

Uso: python3 extrair.py AUTOS.pdf PASTA_SAIDA

Não usa IA. Cria PASTA_SAIDA/autos.db com:
  paginas(pag, fls, assinante, origem, data, hora, protocolo, codigo, n_chars, texto, ocr)
  busca   (índice de texto completo das páginas, FTS5)

Páginas digitalizadas ou com fonte corrompida ficam com texto vazio; use ocr.py.
"""
import re
import sqlite3
import sys
from pathlib import Path

import fitz  # PyMuPDF

RE_ASSIN = re.compile(r"assinado digitalmente por (.+?)(?:,| e Tribunal de Justi)", re.S)
RE_DATA = re.compile(r"(protocolado|liberado nos autos) em (\d\d/\d\d/\d{4})")
RE_NUM = re.compile(r"sob o número (\w+)")
RE_FLS = re.compile(r"\nfls\. (\d+)\s*$")
RE_COD = re.compile(r"e código (\w+)\.")
RE_HORA = re.compile(r"em \d\d/\d\d/\d{4} às (\d\d:\d\d)")
RE_RODAPE = re.compile(r"Para conferir o original, acesse o site.*", re.S)


def ilegivel(texto):
    """Fonte corrompida: o PDF devolve caracteres de controle em vez de letras."""
    if not texto:
        return False
    ruins = sum(1 for ch in texto if ord(ch) < 32 and ch not in "\n\t\r")
    return ruins / len(texto) > 0.05


def ler_carimbo(texto):
    m = RE_ASSIN.search(texto)
    c = RE_COD.search(texto)
    h = RE_HORA.search(texto)
    d = RE_DATA.search(texto)
    n = RE_NUM.search(texto)
    f = RE_FLS.search(texto)
    return dict(
        assinante=" ".join(m.group(1).split()) if m else None,
        origem={"protocolado": "partes", "liberado nos autos": "juizo"}.get(d.group(1)) if d else None,
        data=d.group(2) if d else None,
        protocolo=n.group(1) if n else None,
        fls=int(f.group(1)) if f else None,
        codigo=c.group(1) if c else None,
        hora=h.group(1) if h else None,
    )


def main():
    if len(sys.argv) != 3 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if len(sys.argv) > 1 else 1)
    pdf, saida = Path(sys.argv[1]), Path(sys.argv[2])
    if not pdf.is_file():
        sys.exit(f"Arquivo não encontrado: {pdf}")
    saida.mkdir(parents=True, exist_ok=True)
    db = saida / "autos.db"
    if db.exists():
        db.replace(db.with_suffix(".db.anterior"))
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE paginas(pag INTEGER PRIMARY KEY, fls INTEGER, assinante TEXT, origem TEXT,
                             data TEXT, hora TEXT, protocolo TEXT, codigo TEXT,
                             n_chars INTEGER, texto TEXT, ocr INTEGER DEFAULT 0);
        CREATE VIRTUAL TABLE busca USING fts5(texto, content='paginas', content_rowid='pag',
                                              tokenize='unicode61 remove_diacritics 2');
    """)
    doc = fitz.open(pdf)
    total = doc.page_count
    for i, pg in enumerate(doc):
        bruto = pg.get_text()
        c = ler_carimbo(bruto)
        texto = RE_RODAPE.sub("", bruto).strip()
        if ilegivel(texto):
            texto = ""
        con.execute("INSERT INTO paginas VALUES (?,?,?,?,?,?,?,?,?,?,0)",
                    (i + 1, c["fls"], c["assinante"], c["origem"], c["data"], c["hora"],
                     c["protocolo"], c["codigo"], len(texto), texto))
        if (i + 1) % 2000 == 0:
            print(f"  {i + 1}/{total} páginas", flush=True)
    con.execute("INSERT INTO busca(busca) VALUES('rebuild')")
    con.commit()
    print(f"Pronto: {total} páginas em {db}")


if __name__ == "__main__":
    main()
