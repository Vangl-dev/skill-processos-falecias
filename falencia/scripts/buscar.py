#!/usr/bin/env python3
"""Busca palavras em todas as páginas dos autos (ignora acentos e maiúsculas).

Uso:
  python3 buscar.py PASTA_SAIDA "termo"
  python3 buscar.py PASTA_SAIDA '"frase exata"'
  python3 buscar.py PASTA_SAIDA 'fulana AND alvará'
  python3 buscar.py PASTA_SAIDA 'penhora' --juizo      só peças do juízo

Mostra folha, data, quem assinou e o trecho. Requer o autos.db do extrair.py.
"""
import argparse
import sqlite3
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("saida")
    ap.add_argument("termo")
    ap.add_argument("--juizo", action="store_true", help="só documentos liberados pelo juízo")
    ap.add_argument("--limite", type=int, default=50)
    a = ap.parse_args()

    con = sqlite3.connect(Path(a.saida) / "autos.db")
    sql = """SELECT p.fls, p.pag, p.data, p.origem, p.assinante,
                    snippet(busca, 0, '>>', '<<', ' … ', 24)
             FROM busca JOIN paginas p ON p.pag = busca.rowid
             WHERE busca MATCH ?""" + (" AND p.origem = 'juizo'" if a.juizo else "") + \
          " ORDER BY p.pag LIMIT ?"
    linhas = con.execute(sql, (a.termo, a.limite)).fetchall()
    for fls, pag, data, origem, ass, trecho in linhas:
        quem = "JUÍZO" if origem == "juizo" else (ass or "?")
        print(f"fls. {fls or '?'} (pág. {pag}) | {data or '?'} | {quem}\n   {' '.join(trecho.split())}\n")
    print(f"{len(linhas)} resultado(s){' (limite atingido; use --limite)' if len(linhas) == a.limite else ''}.")


if __name__ == "__main__":
    main()
