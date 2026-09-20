#!/usr/bin/env python3
"""Translate the English LaTeX report to German without altering equations.

The translator masks mathematics, result-file names, references, units, and
LaTeX control sequences before sending prose to the installed Argos en->de
model.  The generated source deliberately keeps the English report structure
so that figures, tables, equations, and cross-references remain identical.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from argostranslate import translate


HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
SOURCE_DIR = DOCS / "en"
TARGET_DIR = DOCS / "de"
SOURCE = SOURCE_DIR / "phenolic_pyrolysis_ablation_report.tex"
TARGET = TARGET_DIR / "phenolic_pyrolysis_ablation_report.tex"

PROTECTED_ENVIRONMENTS = (
    "equation",
    "equation*",
    "align",
    "align*",
    "gather",
    "gather*",
    "multline",
    "multline*",
    "tikzpicture",
    "lstlisting",
    "verbatim",
    "thebibliography",
)

PROTECTED_MACROS = {
    "SI": 2,
    "SIrange": 3,
    "num": 1,
    "si": 1,
    "code": 1,
    "codepath": 1,
    "path": 1,
    "url": 1,
    "href": 2,
    "ref": 1,
    "eqref": 1,
    "pageref": 1,
    "cite": 1,
    "label": 1,
    "includegraphics": 1,
    "lstinputlisting": 1,
    "bibitem": 1,
    "begin": 1,
    "end": 1,
    "color": 1,
    "definecolor": 3,
    "setcounter": 2,
    "addtocounter": 2,
    "vspace": 1,
    "hspace": 1,
}


def token_name(index: int) -> str:
    return f'<ph id="{index}"/>'


def consume_group(text: str, start: int, opening: str, closing: str) -> int:
    if start >= len(text) or text[start] != opening:
        return start
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == opening and (index == 0 or text[index - 1] != "\\"):
            depth += 1
        elif char == closing and (index == 0 or text[index - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return start


def mask_fragment(text: str) -> tuple[str, list[str]]:
    protected: list[str] = []

    def store(value: str) -> str:
        token = token_name(len(protected))
        protected.append(value)
        return token

    output: list[str] = []
    index = 0
    while index < len(text):
        if text[index].isdigit():
            number = re.match(r"[0-9]+(?:\.[0-9]+)?", text[index:])
            if number:
                output.append(store(number.group(0)))
                index += len(number.group(0))
                continue

        if text.startswith("%", index) and (index == 0 or text[index - 1] != "\\"):
            end = text.find("\n", index)
            if end < 0:
                end = len(text)
            output.append(store(text[index:end]))
            index = end
            continue

        if text.startswith("\\[", index):
            end = text.find("\\]", index + 2)
            if end >= 0:
                output.append(store(text[index : end + 2]))
                index = end + 2
                continue
        if text.startswith("\\(", index):
            end = text.find("\\)", index + 2)
            if end >= 0:
                output.append(store(text[index : end + 2]))
                index = end + 2
                continue
        if text[index] == "$" and (index == 0 or text[index - 1] != "\\"):
            delimiter = "$$" if text.startswith("$$", index) else "$"
            end = text.find(delimiter, index + len(delimiter))
            if end >= 0:
                output.append(store(text[index : end + len(delimiter)]))
                index = end + len(delimiter)
                continue

        if text[index] == "\\":
            command = re.match(r"\\([A-Za-z@]+\*?|.)", text[index:])
            if command:
                name = command.group(1)
                end = index + len(command.group(0))
                base_name = name.rstrip("*")
                if base_name in PROTECTED_MACROS:
                    while end < len(text) and text[end].isspace() and text[end] != "\n":
                        end += 1
                    if end < len(text) and text[end] == "[":
                        candidate = consume_group(text, end, "[", "]")
                        if candidate > end:
                            end = candidate
                    for _ in range(PROTECTED_MACROS[base_name]):
                        while end < len(text) and text[end].isspace() and text[end] != "\n":
                            end += 1
                        candidate = consume_group(text, end, "{", "}")
                        if candidate == end:
                            break
                        end = candidate
                    output.append(store(text[index:end]))
                    index = end
                    continue
                output.append(store(command.group(0)))
                index += len(command.group(0))
                continue

        if text[index] in "{}&":
            output.append(store(text[index]))
            index += 1
            continue

        output.append(text[index])
        index += 1

    return "".join(output), protected


def restore_fragment(text: str, protected: list[str]) -> str:
    for index, value in reversed(list(enumerate(protected))):
        text = text.replace(token_name(index), value)
    return text


def translate_fragment(text: str) -> str:
    if not re.search(r"[A-Za-z]", text):
        return text
    masked, protected = mask_fragment(text)
    translated = translate.translate(masked, "en", "de")
    return restore_fragment(translated, protected)


def protect_environments(body: str) -> tuple[str, list[str]]:
    protected: list[str] = []
    for environment in PROTECTED_ENVIRONMENTS:
        pattern = re.compile(
            rf"\\begin\{{{re.escape(environment)}\}}.*?\\end\{{{re.escape(environment)}\}}",
            re.DOTALL,
        )
        while True:
            match = pattern.search(body)
            if not match:
                break
            token = f"\n\n{token_name(10000 + len(protected))}\n\n"
            protected.append(match.group(0))
            body = body[: match.start()] + token + body[match.end() :]
    return body, protected


def restore_environments(body: str, protected: list[str]) -> str:
    for index, value in reversed(list(enumerate(protected))):
        body = body.replace(token_name(10000 + index), value)
    return body


def translate_body(body: str) -> str:
    lines = body.splitlines()
    translated: list[str] = []
    paragraph: list[str] = []
    protected_environment: str | None = None
    in_tabular = False

    structural = re.compile(
        r"^\\(?:begin|end|centering|small|scriptsize|footnotesize|clearpage|"
        r"vfill|maketitle|tableofcontents|toprule|midrule|bottomrule|"
        r"renewcommand|setcounter|addtocounter|includegraphics|label|"
        r"lstinputlisting|listoffigures|listoftables)\b"
    )

    def flush_paragraph() -> None:
        if not paragraph:
            return
        joined = " ".join(line.strip() for line in paragraph)
        translated.append(translate_fragment(joined))
        paragraph.clear()

    for line in lines:
        stripped = line.strip()

        if protected_environment is not None:
            translated.append(line)
            if stripped.startswith(f"\\end{{{protected_environment}}}"):
                protected_environment = None
            continue

        environment_match = re.match(r"\\begin\{([^}]+)\}", stripped)
        if environment_match and environment_match.group(1) in PROTECTED_ENVIRONMENTS:
            flush_paragraph()
            protected_environment = environment_match.group(1)
            translated.append(line)
            continue

        if in_tabular:
            if stripped.startswith("\\end{tabular}"):
                translated.append(line)
                in_tabular = False
            elif not stripped or structural.match(stripped):
                translated.append(line)
            else:
                translated.append(translate_fragment(line))
            continue

        if stripped.startswith("\\begin{tabular}"):
            flush_paragraph()
            translated.append(line)
            in_tabular = True
            continue

        if not stripped:
            flush_paragraph()
            translated.append("")
            continue

        if (
            stripped.startswith("%")
            or structural.match(stripped)
            or "\\includegraphics" in stripped
            or not re.search(r"[A-Za-z]", stripped)
        ):
            flush_paragraph()
            translated.append(line)
            continue

        if stripped.startswith("\\item"):
            flush_paragraph()
            paragraph.append(line)
            continue

        paragraph.append(line)

    flush_paragraph()
    return "\n".join(translated) + "\n"


def fixed_replacements(text: str) -> str:
    replacements = {
        r"\usepackage[english]{babel}": r"\usepackage[ngerman]{babel}",
        r"\selectlanguage{english}": r"\selectlanguage{ngerman}",
        r"\selectlanguage{englisch}": r"\selectlanguage{ngerman}",
        "locale=US": "locale=DE",
        "_en.pdf": "_de.pdf",
        "-en}": "-de}",
        r"\title{~\\[-2em]\sc Thermochemical Modeling of a Phenolic Liner\\\nin a Solid Rocket Motor Using ANSYS Mechanical}": (
            r"\title{~\\[-2em]\sc Thermochemische Modellierung einer Phenolharzauskleidung\\"
            "\n"
            r"in einem Feststoffraketenmotor mit ANSYS Mechanical}"
        ),
        r"\author{\sc MIT Rocket Team --- M. Nichitiu --- Solid Propulsion Simulations}": (
            r"\author{\sc MIT Rocket Team --- M. Nichitiu --- Simulationen von Feststoffantrieben}"
        ),
        r"\date{\sc September 18, 2026}": r"\date{\sc 18. September 2026}",
        r"\renewcommand{\refname}{References}": r"\renewcommand{\refname}{Literatur}",
        r"\renewcommand{\bibname}{References}": r"\renewcommand{\bibname}{Literatur}",
        r"\renewcommand{\listfigurename}{List of Figures}": r"\renewcommand{\listfigurename}{Abbildungsverzeichnis}",
        r"\renewcommand{\listtablename}{List of Tables}": r"\renewcommand{\listtablename}{Tabellenverzeichnis}",
        r"{hot gas\\propellant\\not meshed}": r"{Heißgas\\Treibstoff\\nicht vernetzt}",
        r"\node[rotate=90] at (4.025,1.2) {epoxy};": (
            r"\node[rotate=90] at (4.025,1.2) {Epoxid};"
        ),
        r"\node at (9.30,1.2) {aluminum};": r"\node at (9.30,1.2) {Aluminium};",
        r"<\includegraphics": r"\includegraphics",
        r"{hot-side flux \(q''_\mathrm{in}\)}": r"{heißseitiger Wärmestrom \(q''_\mathrm{in}\)}",
        r"{convection}": r"{Konvektion}",
        r"{radiation}": r"{Strahlung}",
        r"{\it radial direction: inside \(\longrightarrow\) outside}": (
            r"{\it Radialrichtung: innen \(\longrightarrow\) außen}"
        ),
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(
        r"\\title\{.*?\}\n\\author",
        lambda _match: (
            r"\title{~\\[-2em]\sc Thermochemische Modellierung einer "
            "Phenolharzauskleidung\\\\\n"
            r"in einem Feststoffraketenmotor mit ANSYS Mechanical}"
            "\n"
            r"\author"
        ),
        text,
        count=1,
        flags=re.DOTALL,
    )
    return text


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    marker = "\\begin{document}"
    preamble, body = source.split(marker, 1)
    translated = fixed_replacements(preamble) + marker + translate_body(body)
    translated = fixed_replacements(translated)

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    for directory in ("logos", "code"):
        destination = TARGET_DIR / directory
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(SOURCE_DIR / directory, destination)
    TARGET.write_text(translated, encoding="utf-8")
    print(f"Wrote {TARGET}")


if __name__ == "__main__":
    main()
