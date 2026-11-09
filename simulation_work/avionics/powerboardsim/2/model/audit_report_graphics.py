"""Check the TeX sources and the included PDF objects in each finished publication (requires pypdf)."""
import argparse
from pathlib import Path
import re

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
GRAPHIC = re.compile(r"\\includegraphics\*?(?:\s*\[[^\]]*\])?\s*\{([^}]+)\}")


def audit(publication, pdf):
    source = ROOT/'docs'/f'battery-case-{publication}.tex'
    src = source.read_text()
    for relative in re.findall(r"\\input\{(appendices/[^{}]+)\}", src):
        src += (source.parent/relative).with_suffix('.tex').read_text()
    names = GRAPHIC.findall(src)
    assert names and len(names) == src.count(r'\includegraphics')
    seen = set()
    for name in names:
        path = source.parent/name
        if path.suffix != '.pdf':
            raise ValueError(f'{name} must be a LaTeX-rendered PDF')
        file = PdfReader(path)
        if 'Matplotlib pgf backend' not in str(file.metadata.producer) or len(file.pages) != 1:
            raise ValueError(f'{name} was not rendered by PGF')
        fonts = file.pages[0]['/Resources']['/Font']
        for ref in fonts.values():
            font = ref.get_object()
            if 'LM' not in str(font['/BaseFont']) or font['/Subtype'] != '/Type1':
                raise ValueError(f'{name} has an unexpected font: {font.get("/BaseFont")}')
            if '/FontFile' not in font['/FontDescriptor']:
                raise ValueError(f'{name} has an unembedded font')
        if not len(fonts) or not file.pages[0].extract_text().strip():
            raise ValueError(f'{name} has no typeset text')
        seen.add(path.name)

    # pdfTeX embeds each linked figure as a Form XObject, preserving its PDF info.
    pages = PdfReader(pdf)
    included = []
    for page in pages.pages:
        resources = page['/Resources']
        if '/XObject' not in resources:
            continue
        for ref in resources['/XObject'].values():
            obj = ref.get_object()
            if '/PTEX.FileName' not in obj:
                continue
            name = Path(str(obj['/PTEX.FileName'])).name
            if name in seen:
                if 'Matplotlib pgf backend' not in str(obj['/PTEX.InfoDict'].get('/Producer')):
                    raise ValueError(f'Previously rendered figure embedded in {pdf.name}: {name}')
                included.append(name)
    if set(included) != seen:
        raise ValueError(f'{pdf.name} missing PGF objects: {sorted(seen-set(included))}')
    print(f'{publication}: {len(seen)} PGF graphics, {len(pages.pages)} pages')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('publication', choices=['report','slides'])
    parser.add_argument('pdf',type=Path)
    args = parser.parse_args()
    audit(args.publication,args.pdf)
