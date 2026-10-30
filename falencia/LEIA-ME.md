# falencia

Triagem de autos de falência do e-SAJ (TJSP) sem IA: separa o que veio do juízo,
do administrador judicial e do MP das habilitações de crédito, gera um PDF
enxuto e permite buscar palavras nas milhares de páginas. As instruções para a IA
estão em `SKILL.md`.

## Instalar

```bash
pip install -r requirements.txt                 # PyMuPDF
sudo pacman -S tesseract tesseract-data-por     # só para o OCR
```

## Uso sem IA

```bash
cd ~/SKILLS/falencia
A="/caminho/autos.pdf"; P="/caminho/pasta-do-caso/triagem"

python3 scripts/extrair.py "$A" "$P"                       # ~3 min / 25 mil págs.
python3 scripts/ocr.py "$A" "$P" --juizo                   # peças do juízo em imagem
python3 scripts/triagem.py "$A" "$P" --cliente "Fulana" --advogado "Beltrana"
python3 scripts/buscar.py "$P" "alvará"
```

Abra `despachos.csv` e `indice.csv` no LibreOffice, separador `;`.

Volumes antigos digitalizados (demora horas, roda sozinho):

```bash
python3 scripts/ocr.py "$A" "$P" --paginas 1-7790
python3 scripts/triagem.py "$A" "$P" --cliente "Fulana" --advogado "Beltrana"
```

## Arquivos

- `SKILL.md`: instruções para a IA.
- `scripts/extrair.py`: lê o texto e o carimbo de cada página para `autos.db`.
- `scripts/ocr.py`: OCR das páginas sem texto (juízo, trecho ou tudo).
- `scripts/triagem.py`: classifica e gera `resumo.md`, `despachos.csv`,
  `indice.csv`, `juizo.pdf` e `partes-de-interesse.pdf`.
- `scripts/buscar.py`: busca por palavra em todos os autos.
