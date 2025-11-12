# redigir_pdfs.py (versão otimizada)

import re
import sys
import argparse
from pathlib import Path
import fitz

CPF_REGEXES = [
    r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
    r"\b\d{11}\b",
]
RG_REGEXES = [
    r"\b\d{1,2}\.\d{3}\.\d{3}-[\dxX]\b",
    r"\b\d{7,10}[-\s]?[\dxX]?\b",
]

def compilar_padroes():
    return [re.compile(p) for p in (CPF_REGEXES + RG_REGEXES)]

def buscar_caixas(page, trecho: str):
    try:
        return page.search_for(trecho, quads=False)
    except TypeError:
        return page.search_for(trecho)

def redigir_arquivo(pdf_in: Path, pdf_out: Path, padroes):
    doc = fitz.open(pdf_in.as_posix())
    fitz.TOOLS.set_small_glyph_heights(True)
    total_redacoes = 0
    page = doc[0]
    texto = page.get_text("text")
    id_areas = page.search_for("ID Único")
    y_limite = 0
    if id_areas:
        y_limite = max(rect.y0 for rect in id_areas)
    for rx in padroes:
        for m in rx.finditer(texto):
            trecho = m.group(0)
            caixas = buscar_caixas(page, trecho)
            for rect in caixas:
                if y_limite and rect.y0 > y_limite - 20:
                    continue
                shrink = 0.1 * rect.height
                safe_rect = fitz.Rect(rect.x0, rect.y0 + shrink, rect.x1, rect.y1)
                page.add_redact_annot(safe_rect, fill=(0, 0, 0))
                total_redacoes += 1
    page.apply_redactions()
    pdf_out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(pdf_out.as_posix(), deflate=True, garbage=4)
    doc.close()
    return total_redacoes

def contem_padrao(pdf_path: Path, padroes):
    doc = fitz.open(pdf_path.as_posix())
    texto_total = doc[0].get_text("text")
    doc.close()
    return any(rx.search(texto_total) for rx in padroes)

def listar_pdfs(pasta_in: Path, glob_pat: str):
    return [p for p in pasta_in.rglob(glob_pat) if p.suffix.lower() == ".pdf"]

def main():
    ap = argparse.ArgumentParser(description="Anonimização (redaction) de CPF e RG na primeira página de PDFs.")
    ap.add_argument("--entrada", required=True, help="Pasta de origem dos PDFs")
    ap.add_argument("--saida", required=True, help="Pasta de destino dos PDFs anonimizados")
    ap.add_argument("--glob", default="*.pdf", help='Padrão de busca (use "**/*.pdf" p/ recursivo)')
    args = ap.parse_args()

    pasta_in = Path(args.entrada)
    pasta_out = Path(args.saida)
    padroes = compilar_padroes()

    if not pasta_in.exists():
        print(f"Pasta de entrada não encontrada: {pasta_in}")
        sys.exit(1)

    arquivos = sorted(listar_pdfs(pasta_in, args.glob))
    if not arquivos:
        print("Nenhum PDF encontrado.")
        sys.exit(0)

    total_docs, total_redacoes = 0, 0
    for pdf_in in arquivos:
        rel = pdf_in.relative_to(pasta_in)
        pdf_out = pasta_out / rel
        try:
            red = redigir_arquivo(pdf_in, pdf_out, padroes)
            total_docs += 1
            total_redacoes += red
            if contem_padrao(pdf_out, padroes):
                print(f"[ATENÇÃO] Possíveis padrões remanescentes em {pdf_out}")
            else:
                print(f"[OK] {pdf_in.name} -> {pdf_out.name} (redações: {red})")
        except Exception as e:
            print(f"[ERRO] {pdf_in}: {e}")

    print(f"\nConcluído. Documentos processados: {total_docs}. Redações aplicadas: {total_redacoes}.")

if __name__ == "__main__":
    main()
