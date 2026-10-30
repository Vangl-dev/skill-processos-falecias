# Triagem de autos de falência

Skill de IA para quem acompanha credores em **processos de falência ou
recuperação judicial** do e-SAJ (TJSP). Esses autos chegam a dezenas de
milhares de páginas, quase todas de habilitações de crédito de outros credores.
Achar um despacho perdido ali leva horas.

A skill resolve isso **sem passar os autos pela IA**. Programas comuns leem o
carimbo de cada página do e-SAJ e separam o que importa. Em poucos minutos,
25 mil páginas viram:

| Arquivo | O que tem |
|---|---|
| `despachos.csv` | linha do tempo do juízo: decisões, atos ordinatórios e o **teor de cada ato publicado no DJE**, inclusive os despachos curtos dados em petição |
| `juizo.pdf` | só as peças do juízo, com um marcador por peça (folha, data, tipo) |
| `partes-de-interesse.pdf` | administrador judicial, Ministério Público e o que cita o seu cliente |
| `indice.csv` | todos os documentos dos autos, classificados |
| `resumo.md` | contagens, peças que citam o cliente e trechos digitalizados sem texto |

E uma **busca por palavra** em todas as páginas, que responde em menos de um
segundo. Só no fim a IA entra, lendo o material já filtrado para montar o
relatório do crédito do cliente.

## Como funciona

Cada página baixada do e-SAJ traz na margem um carimbo:

- *"assinado digitalmente por FULANO, **protocolado** em…"*: veio das partes;
- *"assinado digitalmente por FULANO, **liberado nos autos** em…"*: veio do juízo.

O código de conferência separa os documentos e o número de protocolo junta a
petição com seus anexos. Daí a classificação: juízo (decisões, certidões,
publicações, ofícios), administrador judicial (detectado pelas petições que se
apresentam como tal), MP, cliente e os demais credores, que ficam de fora.

## Instalação

Requer Python 3 e PyMuPDF (`pip install -r falencia/requirements.txt`). O OCR,
opcional, requer o Tesseract com o idioma português.

**Claude Code, Codex, Gemini CLI, Copilot:** copie ou faça um atalho da pasta
`falencia/` para a pasta de skills da sua IA, por exemplo:

```bash
git clone https://github.com/Vangl-dev/skill-processos-falecias.git
ln -s "$PWD/skill-processos-falecias/falencia" ~/.claude/skills/falencia
```

**claude.ai:** compacte a pasta `falencia/` num `.zip` e envie em
*Configurações → Capacidades → Skills*.

## Uso sem IA

```bash
cd falencia
python3 scripts/extrair.py AUTOS.pdf PASTA
python3 scripts/ocr.py AUTOS.pdf PASTA --juizo          # opcional
python3 scripts/triagem.py AUTOS.pdf PASTA --cliente "Fulana" --advogado "Beltrana"
python3 scripts/buscar.py PASTA "alvará"
```

Todos os scripts têm `--help`.

## Limites

- Feito para o e-SAJ do TJSP. Outros sistemas usam outro carimbo.
- Volumes físicos digitalizados (imagem) só entram depois de OCR, que é lento.
- A classificação é por regras. Confira a lista de administradores judiciais
  no `resumo.md`.

Veja também a skill
[marcos-e-valores](https://github.com/Vangl-dev/skill-processos-marcas-e-valores),
que levanta datas, valores e prazos de qualquer processo.

## Licença

MIT
