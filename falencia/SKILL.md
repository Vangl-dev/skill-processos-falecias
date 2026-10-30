---
name: falencia
description: Faz a triagem de autos enormes de falência ou recuperação judicial do e-SAJ (TJSP), sem IA: separa decisões, despachos, publicações, atos do administrador judicial e do MP das milhares de habilitações de crédito, gera um PDF só com as peças de interesse e permite buscar palavras em todos os autos. Depois, acompanha o crédito de um cliente. Use quando pedirem para achar despachos ou peças num processo de falência, para organizar ou "enxugar" autos de falência, ou para analisar o crédito de um cliente numa falência.
---

# Falência: triagem dos autos e crédito do cliente

Autos de falência têm dezenas de milhares de páginas, quase todas de
habilitações de crédito de outros credores. **Não leia os autos com a IA.** Os
scripts fazem a triagem pelo carimbo do e-SAJ de cada página. A IA só entra no
fim, sobre o material já filtrado.

## Como a triagem funciona

Cada página baixada do e-SAJ traz na margem um carimbo assim:

- *"…assinado digitalmente por FULANO, **protocolado** em…"*: veio das partes
  (credores, administrador judicial, MP, falida);
- *"…assinado digitalmente por FULANO, **liberado nos autos** em…"*: veio do
  juízo (decisões, despachos, certidões, atos ordinatórios, ofícios).

O código de conferência do carimbo separa os documentos, e o número de protocolo
junta a petição com seus anexos. As **Certidões de Publicação de Relação**
trazem o teor literal de cada ato publicado no DJE, inclusive os despachos
curtos dados nas petições ("J. à administradora judicial"), que são os mais
difíceis de achar.

## Passo 0: dados

Pergunte, se não estiver claro:

- onde está o PDF dos autos (download completo da pasta digital do e-SAJ);
- o nome da cliente (e o CPF/CNPJ, se houver) e o nome do advogado dela;
- em que pasta do caso salvar os resultados. Se não houver resposta, use a
  pasta `<nome do PDF>-triagem` ao lado do PDF. **Nunca** salve dados do caso
  dentro da pasta da skill.

## Passo 1: extrair (sem IA, ~3 min para 25 mil páginas)

```bash
python3 scripts/extrair.py AUTOS.pdf PASTA
python3 scripts/ocr.py AUTOS.pdf PASTA --juizo
```

O segundo comando passa OCR só nas peças do juízo que vieram como imagem ou com
fonte corrompida (poucas centenas de páginas, alguns minutos).

## Passo 2: triagem

```bash
python3 scripts/triagem.py AUTOS.pdf PASTA --cliente "Nome da cliente" --advogado "Nome do advogado"
```

Gera na PASTA:

| Arquivo | Conteúdo |
|---|---|
| `resumo.md` | contagens por categoria, administradores judiciais detectados, documentos que citam a cliente e trechos sem texto |
| `despachos.csv` | linha do tempo do juízo: decisões, atos ordinatórios e o teor de cada publicação, com data, folha, se o advogado foi intimado e se cita a cliente |
| `indice.csv` | todos os documentos, com folhas, data, categoria e assinante |
| `juizo.pdf` | peças do juízo, com um marcador por peça (fls., data, tipo) |
| `partes-de-interesse.pdf` | administrador judicial, MP e o que cita a cliente; peças muito longas entram só com as primeiras páginas e as que citam a cliente |

Confira em `resumo.md` a lista de administradores judiciais. Se faltar ou sobrar
alguém, rode de novo com `--aj "NOME"` (um por nome, como aparece na assinatura).

## Passo 3: buscar

```bash
python3 scripts/buscar.py PASTA "termo"            # ignora acentos e maiúsculas
python3 scripts/buscar.py PASTA '"frase exata"' --juizo
```

## Passo 4: os volumes digitalizados (opcional e demorado)

Processos antigos têm os volumes físicos digitalizados como imagem. Despachos
dentro deles **não aparecem** na triagem até passarem por OCR. O `resumo.md`
lista esses trechos. O OCR leva de 2 a 4 segundos por página, por núcleo do
processador. Avise o usuário do tempo estimado antes de começar, e rode em
segundo plano:

```bash
python3 scripts/ocr.py AUTOS.pdf PASTA --paginas 1-7790
python3 scripts/triagem.py AUTOS.pdf PASTA --cliente ...   # de novo, depois
```

O OCR pode ser interrompido e retomado. Despacho manuscrito não é lido pelo OCR.

## Passo 5: o crédito da cliente (aqui entra a IA)

Leia apenas `despachos.csv`, as peças marcadas como cliente no `resumo.md` e, se
preciso, as páginas indicadas do `juizo.pdf` e do `partes-de-interesse.pdf`. Monte o relatório:

1. **Status atual do crédito**: valor, classe (trabalhista, com garantia real,
   tributário, quirografário, subordinado…), situação (habilitado, impugnado,
   incluído no quadro geral, pago em parte), em 3 a 5 linhas;
2. **Linha do tempo**: eventos em ordem cronológica, cada um com data e folha;
3. **Pendências e prazos em aberto**: o que ainda corre ou espera decisão;
4. **Despachos gerais que afetam todos os credores** (rateios, pagamentos,
   prazos para dados bancários, editais), com folha.

Regras:

- Toda afirmação cita a folha. Valor sem folha não entra.
- Grafias diferentes do nome e o nome do advogado também contam como menção.
- Créditos distintos da mesma cliente ficam separados. Se houver cessão de
  crédito, mostre a cadeia.
- Diga o que não foi coberto, como os volumes digitalizados sem OCR.

## Limites

- Feito para o e-SAJ do TJSP. Em PJe, eproc ou Projudi o carimbo é outro, e os
  scripts avisam que não acharam carimbos.
- A classificação é por regras. Petições de credores podem citar a
  administradora judicial e vice-versa, então confira o `resumo.md`.
