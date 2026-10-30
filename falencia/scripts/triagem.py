#!/usr/bin/env python3
"""Separa as peças de interesse dos autos de falência, sem usar IA.

Uso:
  python3 triagem.py AUTOS.pdf PASTA_SAIDA [--cliente NOME ...] [--advogado NOME ...] [--aj NOME ...]

Antes, rode extrair.py AUTOS.pdf PASTA_SAIDA (cria PASTA_SAIDA/autos.db) e,
de preferência, ocr.py ... --juizo (lê as peças do juízo digitalizadas).

Gera em PASTA_SAIDA:
  indice.csv            todas as peças, com categoria (abre no LibreOffice/Excel)
  despachos.csv         decisões, despachos, sentenças, atos ordinatórios e o teor
                        de cada ato publicado no DJE, em ordem cronológica
  juizo.pdf             peças do juízo, com um marcador por peça (fls, data, tipo)
  partes-de-interesse.pdf administrador judicial, MP e o que cita o cliente
  resumo.md             contagens, administradores judiciais detectados e trechos
                        digitalizados sem texto (precisam de OCR)

--cliente  nome (ou parte do nome, CPF) a destacar; repita para mais de um.
--advogado nome de advogado; marca em despachos.csv as publicações em que
           ele consta entre os intimados.
--sem-reduzir mantém as imagens na resolução original (PDF bem maior).
--aj       nome do administrador judicial como aparece na assinatura; se omitido,
           o script detecta pelos documentos que se apresentam como tal.
"""
import argparse
import csv
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import fitz  # PyMuPDF

# Categorias que entram no PDF de peças de interesse
INTERESSE = {"decisao", "ato_ordinatorio", "publicacao", "recorte_dje", "administrador_judicial",
             "ministerio_publico", "cliente", "contas_judiciais", "expediente", "outro_juizo",
             "juizo_sem_texto"}
# Peças maiores que isso entram no PDF só com as primeiras páginas e as que citam o cliente
MAX_PAGS_PDF = 30
LIMITE_TEXTO = 8000  # caracteres por célula do despachos.csv
# Peças do juízo vão para juizo.pdf; o resto das peças de interesse, para partes-de-interesse.pdf
JUIZO = {"decisao", "ato_ordinatorio", "publicacao", "recorte_dje", "contas_judiciais",
         "expediente", "outro_juizo", "juizo_sem_texto"}

ROTULO = {
    "decisao": "Decisão/despacho/sentença",
    "ato_ordinatorio": "Ato ordinatório",
    "publicacao": "Certidão de publicação (teor do ato)",
    "recorte_dje": "Recorte do Diário Oficial",
    "juizo_sem_texto": "Peça do juízo sem texto (ver no PDF)",
    "intimacao": "Ciência/remessa de intimação",
    "certidao": "Certidão do cartório",
    "expediente": "Ofício/mandado/edital/alvará",
    "contas_judiciais": "Extrato/guia de conta judicial",
    "outro_juizo": "Outro documento do juízo",
    "administrador_judicial": "Administrador judicial",
    "ministerio_publico": "Ministério Público",
    "cliente": "Menciona o cliente",
    "credores": "Petição de credor/terceiro (provável habilitação)",
    "sem_carimbo": "Sem carimbo do e-SAJ",
}


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def corpo(texto):
    """Texto sem o cabeçalho padrão do tribunal (primeiras linhas de endereço)."""
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    cab = re.compile(r"^(TRIBUNAL DE JUSTI|COMARCA|FORO|\d+ª VARA|Praça|Horário|\(11\)|Fone|sp\d?falencias|900,)", re.I)
    i = 0
    while i < len(linhas) and i < 12 and (cab.match(linhas[i]) or "jus.br" in linhas[i]):
        i += 1
    return "\n".join(linhas[i:])


def classificar_juizo(txt):
    c = corpo(txt)
    if len(c) < 50:
        return "juizo_sem_texto"
    topo = sem_acento(c[:600])
    if "publicacao oficial do tribunal de justica" in topo and "disponibilizacao" in topo:
        return "recorte_dje"
    if "certidao de publicacao de relacao" in topo:
        return "publicacao"
    if re.search(r"ciencia da intimacao|certidao de remessa|certidao de nao leitura|certidao de leitura", topo):
        return "intimacao"
    if re.search(r"^ato ordinatorio", topo, re.M):
        return "ato_ordinatorio"
    if re.search(r"^(decisao|despacho|sentenca)\b", topo, re.M):
        return "decisao"
    if re.search(r"extrato|deposito|resgate|guia|saldo|banco do brasil|conta judicial|sisbb|levantamento eletronico", topo):
        return "contas_judiciais"
    if re.search(r"^(oficio|mandado|edital|alvara|carta|termo de)", topo, re.M):
        return "expediente"
    if re.search(r"^certid", topo, re.M):
        return "certidao"
    t = sem_acento(c)
    if re.search(r"\bvistos\b|intime-se|int\.\s*$|cumpra-se|ju[ií]za? de direito", t, re.M):
        return "decisao"
    return "outro_juizo"


def certidoes_publicacao(d):
    """Separa as Certidões de Publicação de Relação de um documento.

    Devolve [(fls, relação, data DJE, advogados intimados, teor)].
    """
    blocos = []
    for fls, txt in d["paginas"]:
        if "CERTIDÃO DE PUBLICAÇÃO DE RELAÇÃO" in txt or not blocos:
            blocos.append([fls, txt])
        else:
            blocos[-1][1] += "\n" + txt
    out = []
    for fls, txt in blocos:
        plano = " ".join(txt.split())
        rel = re.search(r"relação nº (\S+?),", plano)
        dje = re.search(r"Diário da Justiça Eletrônico em (\d\d/\d\d/\d{4})", plano)
        adv = re.search(r"Advogado (.+?) Teor do ato", plano)
        teor = re.search(r"Teor do ato: (.+?)\s+(?:SÃO PAULO|São Paulo), \d", plano)
        out.append((fls, rel.group(1) if rel else "", dje.group(1) if dje else "",
                    adv.group(1) if adv else "", teor.group(1).strip() if teor else ""))
    return out


def montar_documentos(con):
    """Agrupa páginas consecutivas com o mesmo código de conferência."""
    docs = []
    for pag, fls, ass, orig, data, hora, prot, cod, n, txt in con.execute(
            "SELECT pag, fls, assinante, origem, data, hora, protocolo, codigo, n_chars, texto "
            "FROM paginas ORDER BY pag"):
        if docs and (cod is None or cod == docs[-1]["codigo"]):
            d = docs[-1]
            d["pags"].append(pag)
            d["fls_fim"] = fls or d["fls_fim"]
            d["texto"] += "\n" + txt
            d["paginas"].append((fls, txt))
            d["sem_texto"] += n < 50
            continue
        docs.append(dict(codigo=cod, assinante=ass, origem=orig, data=data, hora=hora,
                         protocolo=prot, pags=[pag], fls_ini=fls, fls_fim=fls,
                         texto=txt, primeira=txt, paginas=[(fls, txt)], sem_texto=int(n < 50)))
    return docs


# A petição se apresenta COMO administração judicial (habilitações também citam a AJ, mas
# como destinatária: "dados bancários entregues à administradora judicial")
RE_AJ = re.compile(r"administrador[a]? judicial\W{0,6},? (devidamente |ja )?(nomead|qualificad|vem)"
                   r"|na qualidade de administrador")
RE_MP = re.compile(r"promotoria de justica|manifestacao do ministerio publico|^\s*ministerio publico do estado", re.M)


def peticoes(docs):
    """Agrupa os documentos das partes por protocolo (petição + anexos)."""
    grupos = defaultdict(list)
    for d in docs:
        if d["origem"] == "partes":
            grupos[d["protocolo"] or d["codigo"]].append(d)
    return list(grupos.values())


def detectar_aj(docs):
    """Assinantes cujas petições, em maioria, se apresentam como administração judicial."""
    total, sim = Counter(), Counter()
    for grupo in peticoes(docs):
        d = grupo[0]
        total[d["assinante"]] += 1
        if RE_AJ.search(sem_acento(d["primeira"][:3000])):
            sim[d["assinante"]] += 1
    return sorted(a for a in sim if sim[a] >= 5 and sim[a] / total[a] >= 0.6)


def classificar(docs, clientes, ajs):
    clientes_n = [sem_acento(c) for c in clientes]
    ajs_n = {sem_acento(a) for a in ajs}
    for d in docs:
        d["cliente_pags"] = [i for i, (_, t) in enumerate(d["paginas"])
                             if any(c in sem_acento(t) for c in clientes_n)]
        d["cliente"] = bool(d["cliente_pags"])
        if d["origem"] == "juizo":
            d["categoria"] = classificar_juizo(d["primeira"])
        elif d["origem"] is None:
            d["categoria"] = "sem_carimbo"
    # partes: a categoria vem da petição (primeiro documento do protocolo) e vale para os anexos
    for grupo in peticoes(docs):
        p = grupo[0]
        if sem_acento(p["assinante"] or "") in ajs_n:
            cat = "administrador_judicial"
        elif RE_MP.search(sem_acento(p["primeira"][:800])):
            cat = "ministerio_publico"
        else:
            cat = "credores"
        for d in grupo:
            d["categoria"] = "cliente" if cat == "credores" and d["cliente"] else cat


def resumo_linha(d, n=160):
    c = " ".join(corpo(d["primeira"]).split())
    c = re.sub(r"^.*?(Processo Digital n.:?\s*\S+\s*)", "", c)
    return c[:n]


def faixa_fls(d):
    a, b = d["fls_ini"], d["fls_fim"]
    return f"{a}" if a == b or b is None else f"{a}-{b}"


def data_ord(s):
    return f"{s[6:]}{s[3:5]}{s[:2]}" if s else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("saida")
    ap.add_argument("--cliente", action="append", default=[])
    ap.add_argument("--advogado", action="append", default=[])
    ap.add_argument("--aj", action="append", default=[])
    ap.add_argument("--sem-reduzir", action="store_true",
                    help="não reduz a resolução das imagens dos PDFs (fica muito maior)")
    a = ap.parse_args()
    saida = Path(a.saida)
    con = sqlite3.connect(saida / "autos.db")

    docs = montar_documentos(con)
    ajs = a.aj or detectar_aj(docs)
    classificar(docs, a.cliente, ajs)

    # indice.csv
    with open(saida / "indice.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["fls", "paginas_pdf", "data", "categoria", "assinante", "n_paginas", "cliente", "inicio"])
        for d in docs:
            w.writerow([faixa_fls(d), f"{d['pags'][0]}-{d['pags'][-1]}", d["data"] or "",
                        ROTULO[d["categoria"]], d["assinante"] or "", len(d["pags"]),
                        "SIM" if d["cliente"] else "", resumo_linha(d)])

    # despachos.csv (decisões + teor das publicações), cronológico
    advs = [sem_acento(x) for x in a.advogado]
    linhas = []
    for d in docs:
        if d["categoria"] in ("decisao", "ato_ordinatorio", "juizo_sem_texto"):
            linhas.append((data_ord(d["data"]), d["data"], faixa_fls(d), ROTULO[d["categoria"]],
                           d["assinante"], "", "", "SIM" if d["cliente"] else "",
                           " ".join(corpo(d["texto"]).split())[:LIMITE_TEXTO]))
        elif d["categoria"] == "publicacao":
            for fls, rel, dje, adv, teor in certidoes_publicacao(d):
                intimado = "SIM" if advs and any(x in sem_acento(adv) for x in advs) else ""
                cli = "SIM" if any(sem_acento(c) in sem_acento(teor) for c in a.cliente) else ""
                linhas.append((data_ord(dje or d["data"]), dje or d["data"], fls,
                               "Publicação DJE", "", rel, intimado, cli, teor[:LIMITE_TEXTO]))
    linhas.sort(key=lambda x: (x[0], str(x[2])))
    with open(saida / "despachos.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["data", "fls", "tipo", "assinante", "relacao_dje", "advogado_intimado",
                    "cita_cliente", "texto"])
        for l in linhas:
            w.writerow(l[1:])

    # juizo.pdf e partes-de-interesse.pdf
    origem = fitz.open(a.pdf)
    sel = [d for d in docs if d["categoria"] in INTERESSE or d["cliente"]]
    pdfs = {"juizo.pdf": [d for d in sel if d["categoria"] in JUIZO],
            "partes-de-interesse.pdf": [d for d in sel if d["categoria"] not in JUIZO]}
    paginas_pdf = {}
    for nome, lista in pdfs.items():
        novo, toc = fitz.open(), []
        for d in lista:
            ini = novo.page_count + 1
            if len(d["pags"]) <= MAX_PAGS_PDF:
                novo.insert_pdf(origem, from_page=d["pags"][0] - 1, to_page=d["pags"][-1] - 1)
                extra = ""
            else:
                idx = sorted(set(range(3)) | set(d["cliente_pags"]))
                for i in idx:
                    novo.insert_pdf(origem, from_page=d["pags"][i] - 1, to_page=d["pags"][i] - 1)
                extra = f" (trecho: {len(idx)} de {len(d['pags'])} págs.)"
            rot = ROTULO[d["categoria"]] + (" [CLIENTE]" if d["cliente"] and d["categoria"] != "cliente" else "")
            toc.append([1, f"fls. {faixa_fls(d)} | {d['data'] or '?'} | {rot}{extra} | "
                           f"{(d['assinante'] or '').title()}", ini])
        novo.set_toc(toc)
        if not a.sem_reduzir:
            # páginas escaneadas em alta resolução deixam o PDF com centenas de MB
            novo.rewrite_images(dpi_threshold=160, dpi_target=120, quality=60)
        novo.save(saida / nome, garbage=3, deflate=True)
        paginas_pdf[nome] = novo.page_count

    # resumo.md
    cont = Counter(d["categoria"] for d in docs)
    pags = defaultdict(int)
    for d in docs:
        pags[d["categoria"]] += len(d["pags"])
    sem = [d for d in docs if d["sem_texto"] >= max(1, len(d["pags"]) // 2)]
    with open(saida / "resumo.md", "w", encoding="utf-8") as f:
        f.write(f"# Triagem dos autos\n\nArquivo: `{a.pdf}`\n\n")
        f.write(f"Total: {origem.page_count} páginas, {len(docs)} documentos.\n")
        f.write(f"Peças de interesse: {len(sel)} documentos. "
                + ", ".join(f"`{k}`: {v} páginas" for k, v in paginas_pdf.items()) + ".\n\n")
        f.write("## Documentos por categoria\n\n| Categoria | Documentos | Páginas |\n|---|---:|---:|\n")
        for k, n in cont.most_common():
            f.write(f"| {ROTULO[k]} | {n} | {pags[k]} |\n")
        f.write("\n## Administradores judiciais considerados\n\n")
        f.write("".join(f"- {x}\n" for x in ajs) or "- nenhum detectado; use --aj\n")
        f.write("\nSe faltar ou sobrar alguém, rode de novo com `--aj \"NOME\"` (um por nome).\n")
        if a.cliente:
            nc = [d for d in docs if d["cliente"]]
            f.write(f"\n## Cliente ({', '.join(a.cliente)})\n\n{len(nc)} documentos mencionam:\n\n")
            for d in nc:
                f.write(f"- fls. {faixa_fls(d)} | {d['data'] or '?'} | {ROTULO[d['categoria']]} | {d['assinante']}\n")
        f.write("\n## Trechos sem texto (digitalizados, precisam de OCR)\n\n")
        f.write(f"{sum(len(d['pags']) for d in sem)} páginas em {len(sem)} documentos. Despachos "
                "dentro desses trechos NÃO aparecem nos arquivos acima. Os maiores:\n\n")
        for d in sorted(sem, key=lambda d: -len(d["pags"]))[:15]:
            f.write(f"- fls. {faixa_fls(d)} ({len(d['pags'])} págs.) | {d['data']} | {d['assinante']}\n")
    print((saida / "resumo.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
