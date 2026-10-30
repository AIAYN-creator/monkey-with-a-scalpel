"""Print every CAD parameter with its value and source as a Markdown table.

Usage: python cad/params_report.py
"""
import params as P


def main():
    rows = []
    for name, source in P.SOURCE.items():
        value = getattr(P, name, None)
        if value is None and name == "PRINT_X":
            value = P.PRINT_VOLUME
        kind, _, note = source.partition(": ")
        rows.append((name, value, kind, note))
    order = {"assumed": 0, "typical": 1, "decided": 2, "catalog": 3}
    rows.sort(key=lambda r: (order.get(r[2], 9), r[0]))
    print("| Parámetro | Valor actual | Estado | Nota |")
    print("|---|---|---|---|")
    labels = {"assumed": "supuesto", "typical": "valor típico de catálogo, verificar", "decided": "decidido en esta versión",
              "catalog": "dato del catálogo Hamilton"}
    for name, value, kind, note in rows:
        print(f"| `{name}` | {value} | {labels.get(kind, kind)} | {note} |")


if __name__ == "__main__":
    main()
