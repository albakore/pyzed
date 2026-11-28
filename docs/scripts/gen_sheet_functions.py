"""Writes the function list of the spreadsheet docs (spreadsheet/formulas.mdx, English and Spanish).

    python docs/scripts/gen_sheet_functions.py

The names, arguments and English descriptions come from ``pz.Workbook.functions()`` (the table in
src/sheet/functions.rs); this file groups them and translates the descriptions. It fails when a
function has no group or no translation, so a new function can't be left out of the docs.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pyzed as pz

DOCS = Path(__file__).resolve().parents[1] / "src" / "content" / "docs"
PAGES = {"en": DOCS / "spreadsheet" / "formulas.mdx", "es": DOCS / "es" / "spreadsheet" / "formulas.mdx"}
START, END = "{/* functions:start */}", "{/* functions:end */}"

GROUPS = [
    (("Math", "Matemáticas"), "ABS CEILING EVEN EXP FACT FLOOR GCD INT LCM LN LOG LOG10 MOD MROUND ODD PI POWER PRODUCT "
     "QUOTIENT RAND RANDBETWEEN ROUND ROUNDDOWN ROUNDUP SEQUENCE SIGN SQRT SUM SUMIF SUMIFS SUMPRODUCT SUMSQ TRUNC"),
    (("Statistics", "Estadística"), "AVERAGE AVERAGEIF AVERAGEIFS COUNT COUNTA COUNTBLANK COUNTIF COUNTIFS LARGE MAX MAXIFS "
     "MEDIAN MIN MINIFS MODE PERCENTILE RANK SMALL STDEV STDEV.P STDEV.S VAR VAR.P VAR.S"),
    (("Logic", "Lógica"), "AND FALSE IF IFERROR IFNA IFS NOT OR SWITCH TRUE XOR"),
    (("Lookup and reference", "Búsqueda y referencia"), "CHOOSE COLUMN COLUMNS FILTER HLOOKUP INDEX INDIRECT MATCH OFFSET "
     "ROW ROWS SORT TRANSPOSE UNIQUE VLOOKUP XLOOKUP"),
    (("Text", "Texto"), "CHAR CLEAN CODE CONCAT CONCATENATE EXACT FIND LEFT LEN LOWER MID PROPER REPLACE REPT RIGHT "
     "SEARCH SPLIT SUBSTITUTE T TEXT TEXTJOIN TRIM UPPER VALUE"),
    (("Date and time", "Fecha y hora"), "DATE DATEDIF DATEVALUE DAY DAYS EDATE EOMONTH HOUR MINUTE MONTH NETWORKDAYS NOW "
     "SECOND TIME TODAY WEEKDAY YEAR"),
    (("Information", "Información"), "ISBLANK ISERR ISERROR ISEVEN ISFORMULA ISLOGICAL ISNA ISNUMBER ISODD ISTEXT N NA"),
    (("Trigonometry", "Trigonometría"), "ACOS ASIN ATAN ATAN2 COS DEGREES RADIANS SIN TAN"),
]

ES = {
    "ABS": "Valor absoluto.",
    "ACOS": "Arcocoseno, en radianes.",
    "AND": "TRUE si todos los argumentos son TRUE.",
    "ASIN": "Arcoseno, en radianes.",
    "ATAN": "Arcotangente, en radianes.",
    "ATAN2": "Arcotangente de y/x, en radianes.",
    "AVERAGE": "Media aritmética de los números.",
    "AVERAGEIF": "Media de las celdas que cumplen un criterio.",
    "AVERAGEIFS": "Media de las celdas que cumplen todos los criterios.",
    "CEILING": "Redondea hacia arriba a un múltiplo.",
    "CHAR": "El carácter con este código.",
    "CHOOSE": "El valor que está en una posición de la lista.",
    "CLEAN": "Quita los caracteres que no se imprimen.",
    "CODE": "El código del primer carácter.",
    "COLUMN": "Número de columna de una referencia.",
    "COLUMNS": "Número de columnas.",
    "CONCAT": "Une textos.",
    "CONCATENATE": "Une textos.",
    "COS": "Coseno de un ángulo en radianes.",
    "COUNT": "Cuántos números hay.",
    "COUNTA": "Cuántos valores no vacíos hay.",
    "COUNTBLANK": "Cuántas celdas vacías hay.",
    "COUNTIF": "Cuántas celdas cumplen un criterio (\">5\", \"manzana\", \"a*\").",
    "COUNTIFS": "Cuántas filas cumplen todos los criterios.",
    "DATE": "Una fecha a partir de sus partes.",
    "DATEDIF": "Diferencia entre fechas en \"Y\", \"M\", \"D\", \"YM\", \"MD\" o \"YD\".",
    "DATEVALUE": "La fecha que representa un texto.",
    "DAY": "Día del mes (1-31).",
    "DAYS": "Días entre dos fechas.",
    "DEGREES": "De radianes a grados.",
    "EDATE": "La fecha unos meses antes o después.",
    "EOMONTH": "El último día del mes a unos meses de distancia.",
    "EVEN": "Redondea, alejándose de cero, a un entero par.",
    "EXACT": "TRUE si los dos textos son idénticos (distingue mayúsculas).",
    "EXP": "e elevado a una potencia.",
    "FACT": "Factorial.",
    "FALSE": "El valor lógico FALSE.",
    "FILTER": "Las filas de un rango donde la condición es TRUE.",
    "FIND": "Posición de un texto (distingue mayúsculas).",
    "FLOOR": "Redondea hacia abajo a un múltiplo.",
    "GCD": "Máximo común divisor.",
    "HLOOKUP": "Busca una clave en la primera fila y devuelve un valor de otra fila.",
    "HOUR": "Hora (0-23).",
    "IF": "Un valor u otro según una condición.",
    "IFERROR": "El valor, u otro si es un error.",
    "IFNA": "El valor, u otro si es #N/A.",
    "IFS": "El valor de la primera condición TRUE.",
    "INDEX": "La celda de una fila y columna de un rango.",
    "INDIRECT": "La referencia escrita en un texto (\"B3\", \"Hoja2!A1:A9\").",
    "INT": "Redondea hacia abajo a un entero.",
    "ISBLANK": "TRUE si la celda está vacía.",
    "ISERR": "TRUE para los errores que no son #N/A.",
    "ISERROR": "TRUE para cualquier error.",
    "ISEVEN": "TRUE para los números pares.",
    "ISFORMULA": "TRUE si la celda tiene una fórmula.",
    "ISLOGICAL": "TRUE para TRUE o FALSE.",
    "ISNA": "TRUE para #N/A.",
    "ISNUMBER": "TRUE para los números.",
    "ISODD": "TRUE para los números impares.",
    "ISTEXT": "TRUE para el texto.",
    "LARGE": "El k-ésimo número más grande.",
    "LCM": "Mínimo común múltiplo.",
    "LEFT": "Los primeros caracteres de un texto.",
    "LEN": "Número de caracteres.",
    "LN": "Logaritmo natural.",
    "LOG": "Logaritmo (en base 10 si no se indica).",
    "LOG10": "Logaritmo en base 10.",
    "LOWER": "En minúsculas.",
    "MATCH": "Posición de un valor en un rango (1: ≤ ordenado, 0: exacto, -1: ≥).",
    "MAX": "El número más grande.",
    "MAXIFS": "El mayor de las celdas que cumplen todos los criterios.",
    "MEDIAN": "La mediana.",
    "MID": "Caracteres del medio de un texto.",
    "MIN": "El número más pequeño.",
    "MINIFS": "El menor de las celdas que cumplen todos los criterios.",
    "MINUTE": "Minuto (0-59).",
    "MOD": "Resto de una división (con el signo del divisor).",
    "MODE": "El número más frecuente.",
    "MONTH": "Mes (1-12).",
    "MROUND": "Redondea al múltiplo más cercano.",
    "N": "El valor como número (el texto vale 0).",
    "NA": "El error #N/A.",
    "NETWORKDAYS": "Días laborables (de lunes a viernes) entre dos fechas.",
    "NOT": "El contrario de un valor lógico.",
    "NOW": "La fecha y la hora actuales.",
    "ODD": "Redondea, alejándose de cero, a un entero impar.",
    "OFFSET": "Una referencia desplazada y redimensionada.",
    "OR": "TRUE si algún argumento es TRUE.",
    "PERCENTILE": "El percentil k (de 0 a 1).",
    "PI": "π.",
    "POWER": "Un número elevado a una potencia.",
    "PRODUCT": "Los números multiplicados entre sí.",
    "PROPER": "Pone En Mayúscula Cada Palabra.",
    "QUOTIENT": "Parte entera de una división.",
    "RADIANS": "De grados a radianes.",
    "RAND": "Un número al azar entre 0 y 1.",
    "RANDBETWEEN": "Un entero al azar entre dos números.",
    "RANK": "Puesto de un número en una lista (1 = el mayor).",
    "REPLACE": "Reemplaza parte de un texto por posición.",
    "REPT": "Repite un texto.",
    "RIGHT": "Los últimos caracteres de un texto.",
    "ROUND": "Redondea a unos decimales.",
    "ROUNDDOWN": "Redondea hacia cero.",
    "ROUNDUP": "Redondea alejándose de cero.",
    "ROW": "Número de fila de una referencia.",
    "ROWS": "Número de filas.",
    "SEARCH": "Posición de un texto (sin distinguir mayúsculas, admite * y ?).",
    "SECOND": "Segundo (0-59).",
    "SEQUENCE": "Una matriz de números consecutivos.",
    "SIGN": "1, 0 o -1.",
    "SIN": "Seno de un ángulo en radianes.",
    "SMALL": "El k-ésimo número más pequeño.",
    "SORT": "Las filas de un rango, ordenadas.",
    "SPLIT": "Divide un texto en celdas.",
    "SQRT": "Raíz cuadrada.",
    "STDEV": "Desviación típica de una muestra.",
    "STDEV.P": "Desviación típica de una población.",
    "STDEV.S": "Desviación típica de una muestra.",
    "SUBSTITUTE": "Cambia un texto por otro.",
    "SUM": "Suma los números.",
    "SUMIF": "Suma las celdas que cumplen un criterio.",
    "SUMIFS": "Suma las celdas que cumplen todos los criterios.",
    "SUMPRODUCT": "Suma de los productos de las matrices.",
    "SUMSQ": "Suma de los cuadrados.",
    "SWITCH": "El valor del primer caso igual a la expresión.",
    "T": "El valor si es texto; si no, \"\".",
    "TAN": "Tangente de un ángulo en radianes.",
    "TEXT": "Un número como texto con un formato (\"0.00\", \"yyyy-mm-dd\").",
    "TEXTJOIN": "Une textos con un separador.",
    "TIME": "Una hora a partir de sus partes.",
    "TODAY": "La fecha de hoy.",
    "TRANSPOSE": "Las filas pasan a ser columnas.",
    "TRIM": "Quita los espacios de más.",
    "TRUE": "El valor lógico TRUE.",
    "TRUNC": "Corta los decimales.",
    "UNIQUE": "Las filas distintas de un rango.",
    "UPPER": "En mayúsculas.",
    "VALUE": "El número que representa un texto.",
    "VAR": "Varianza de una muestra.",
    "VAR.P": "Varianza de una población.",
    "VAR.S": "Varianza de una muestra.",
    "VLOOKUP": "Busca una clave en la primera columna y devuelve un valor de otra columna.",
    "WEEKDAY": "Día de la semana (1 = domingo por defecto).",
    "XLOOKUP": "Busca una clave y devuelve el elemento que le corresponde.",
    "XOR": "TRUE si un número impar de argumentos es TRUE.",
    "YEAR": "Año.",
}


def table(lang: str) -> str:
    funcs = {name: (args, desc) for name, args, desc in pz.Workbook.functions()}
    grouped = {n for _, names in GROUPS for n in names.split()}
    missing = sorted(set(funcs) - grouped)
    unknown = sorted(grouped - set(funcs))
    untranslated = sorted(set(funcs) - set(ES))
    if missing or unknown or untranslated:
        raise SystemExit(f"no group: {missing}; not a function: {unknown}; no translation: {untranslated}")
    out = []
    head = ("Function", "Description") if lang == "en" else ("Función", "Descripción")
    for (en, es), names in GROUPS:
        out.append(f"### {en if lang == 'en' else es}\n")
        out.append(f"| {head[0]} | {head[1]} |\n| --- | --- |")
        for name in names.split():
            args, desc = funcs[name]
            desc = desc if lang == "en" else ES[name]
            desc = desc.replace("|", "\\|")
            out.append(f"| `{name}({args})` | {desc} |")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    total = len(pz.Workbook.functions())
    for lang, page in PAGES.items():
        text = page.read_text(encoding="utf-8")
        if START not in text or END not in text:
            raise SystemExit(f"{page} has no {START} … {END} markers")
        new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: f"{START}\n\n{table(lang)}\n{END}", text,
                     flags=re.S)
        new = re.sub(r"\b\d+ functions\b" if lang == "en" else r"\b\d+ funciones\b",
                     f"{total} functions" if lang == "en" else f"{total} funciones", new)
        page.write_text(new, encoding="utf-8")
        print(f"{page.relative_to(DOCS)}: {total} functions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
