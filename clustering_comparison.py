"""
Clustering Adjudication Comparison Tool

Generates an HTML visualisation comparing two or three annotation CSVs.

Two annotators:
    The left column shows quotes grouped by Annotator 1's clusters, colour-coded
    by Annotator 2. The right column shows Annotator 2's cluster name. A swap
    button cycles through both orientations.

Three annotators:
    Quotes are grouped by the base annotator's clusters. Two content columns
    show the same quotes colour-coded by the other two annotators respectively,
    with their cluster names alongside. A cycle button rotates which annotator
    is the base.

Usage:
    python clustering_comparison.py file1.csv file2.csv [-o output.html] [--use-keys]
    python clustering_comparison.py file1.csv file2.csv file3.csv [-o output.html] [--use-keys]
"""

import argparse
import os
import re
import sys
from collections import Counter, OrderedDict

import seaborn as sns


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate an HTML comparison of two or three annotation CSVs."
    )
    parser.add_argument(
        "files", nargs="+", metavar="FILE",
        help="2 or 3 annotation CSV files"
    )
    parser.add_argument(
        "-o", "--output", default="comparison.html", help="Output HTML file path"
    )
    parser.add_argument(
        "--use-keys",
        action="store_true",
        help="Match quotes by numeric key (N) at end of quote instead of full text",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate that the CSV files are compatible without generating HTML",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# CSV reading
# ---------------------------------------------------------------------------

def read_csv(filepath):
    """Read a CSV and return list of dicts with Code_Name and Quote."""
    import csv as _csv
    rows = []
    with open(filepath, encoding="utf-8", newline="") as f:
        reader = _csv.DictReader(f)
        for row in reader:
            code = row.get("Code_Name", "").strip()
            quote = row.get("Quote", "").strip()
            rows.append({"Code_Name": code, "Quote": quote})
    return rows


def validate_columns(rows, filepath):
    if not rows:
        print(f"Error: '{filepath}' is empty.", file=sys.stderr)
        sys.exit(1)
    for col in ("Code_Name", "Quote"):
        if col not in rows[0]:
            print(
                f"Error: '{filepath}' is missing required column '{col}'.",
                file=sys.stderr,
            )
            sys.exit(1)


# ---------------------------------------------------------------------------
# Key extraction and validation
# ---------------------------------------------------------------------------

KEY_PATTERN = re.compile(r"\((\d+)\)\s*$")


def extract_key(quote):
    m = KEY_PATTERN.search(quote.rstrip('"\''))
    return int(m.group(1)) if m else None


def validate_keys(rows, filepath):
    """Ensure every quote ends with (N). Return {key: row}."""
    key_map = {}
    for i, row in enumerate(rows):
        key = extract_key(row["Quote"])
        if key is None:
            print(
                f"Error: Quote on row {i + 2} of '{filepath}' does not end with a "
                f"numeric key like (N): {row['Quote']!r}",
                file=sys.stderr,
            )
            sys.exit(1)
        if key in key_map:
            print(f"Error: Duplicate key ({key}) in '{filepath}'.", file=sys.stderr)
            sys.exit(1)
        key_map[key] = row
    return key_map


def build_lookup_map(rows, use_keys):
    """Build {key: Code_Name} or {quote: Code_Name} for a single file's rows."""
    result = {}
    for row in rows:
        k = extract_key(row["Quote"]) if use_keys else row["Quote"].strip()
        result[k] = row["Code_Name"]
    return result


# ---------------------------------------------------------------------------
# Cross-file validation
# ---------------------------------------------------------------------------

def validate_matching_pair(rows_a, rows_b, file_a, file_b, use_keys):
    """Check that two files have the same set of keys or quotes."""
    if use_keys:
        map_a = validate_keys(rows_a, file_a)
        map_b = validate_keys(rows_b, file_b)
        keys_a, keys_b = set(map_a), set(map_b)
        only_a, only_b = keys_a - keys_b, keys_b - keys_a
        label = "key(s)"
    else:
        keys_a = {r["Quote"].strip() for r in rows_a}
        keys_b = {r["Quote"].strip() for r in rows_b}
        only_a, only_b = keys_a - keys_b, keys_b - keys_a
        label = "quote(s)"

    if only_a or only_b:
        if only_a:
            items = sorted(only_a)[:5] if use_keys else list(only_a)[:3]
            print(
                f"Error: {len(only_a)} {label} in '{file_a}' not found in '{file_b}': "
                f"{items}",
                file=sys.stderr,
            )
        if only_b:
            items = sorted(only_b)[:5] if use_keys else list(only_b)[:3]
            print(
                f"Error: {len(only_b)} {label} in '{file_b}' not found in '{file_a}': "
                f"{items}",
                file=sys.stderr,
            )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Colour maps
# ---------------------------------------------------------------------------

def build_colour_map(rows):
    """Colour map for a file's clusters. Singletons get None (rendered black)."""
    counts = Counter(row["Code_Name"] for row in rows)
    multi = [name for name, c in counts.items() if c > 1]
    palette = sns.color_palette("husl", len(multi)).as_hex()
    colour_map = {name: palette.pop() for name in multi}
    for name, c in counts.items():
        if c == 1:
            colour_map[name] = None
    return colour_map


# ---------------------------------------------------------------------------
# Two-annotator HTML generation
# ---------------------------------------------------------------------------

def build_view(rows_base, lookup_other, cmap_other, use_keys):
    """Build (left_parts, right_parts) for one two-annotator orientation."""
    clusters = OrderedDict()
    for row in rows_base:
        clusters.setdefault(row["Code_Name"], []).append(row)

    left_parts, right_parts = [], []
    sep = '<br><br><hr style="width: 100%; border: 1px solid black;"><br><br>'

    for cluster_rows in clusters.values():
        for row in cluster_rows:
            quote = row["Quote"]
            k = extract_key(quote) if use_keys else quote.strip()
            other_code = lookup_other[k]
            colour = cmap_other.get(other_code) or "#000000"
            display = ("[ " + quote + " ]") if cmap_other.get(other_code) is None else quote

            left_parts.append(f'<p style="color: {colour};">{display}</p>')
            right_parts.append(
                f'<p style="color: {colour}; font-size: 11px;"><em>{other_code}</em></p>'
            )
        left_parts.append(sep)
        right_parts.append(sep)

    return left_parts, right_parts


def render_two_view_html(left_parts, right_parts, base_label, other_label):
    lines = [
        '<div class="container">',
        f'<div class="left_column"><h3 style="text-align:center;"><u>{base_label}</u></h3></div>',
        f'<div class="right_column"><h3><u>{other_label}</u></h3></div>',
        '</div>',
    ]
    for left, right in zip(left_parts, right_parts):
        lines += [
            '<div class="container">',
            f'<div class="left_column">{left}</div>',
            f'<div class="right_column">{right}</div>',
            '</div>',
        ]
    return "\n".join(lines)


def generate_html_two(all_rows, all_lookups, all_cmaps, use_keys, output_path, labels):
    """Write a two-annotator comparison HTML with a swap button."""
    rows1, rows2 = all_rows
    lookup1, lookup2 = all_lookups   # lookup_i: key -> Code_Name for annotator i
    cmap1, cmap2 = all_cmaps
    label1, label2 = labels

    left_a, right_a = build_view(rows1, lookup2, cmap2, use_keys)
    left_b, right_b = build_view(rows2, lookup1, cmap1, use_keys)

    view_a = render_two_view_html(left_a, right_a, label1, label2)
    view_b = render_two_view_html(left_b, right_b, label2, label1)

    with open(output_path, "w", encoding="utf-8") as f:
        _write_html_head(f, output_path, three=False)
        _write_explainer(f, n=2)
        f.write('<button id="cycle-btn" onclick="cycleView()">Swap Researchers</button>\n')
        f.write(f'<div id="view-0">{view_a}</div>\n')
        f.write(f'<div id="view-1" style="display:none;">{view_b}</div>\n')
        f.write(_cycle_script(2))
        f.write("</body>\n</html>\n")


# ---------------------------------------------------------------------------
# Three-annotator HTML generation
# ---------------------------------------------------------------------------

def build_three_view(rows_base, lookup_left, cmap_left, lookup_right, cmap_right,
                     use_keys, left_suffix, right_suffix):
    """Build a list of HTML row strings for one three-annotator orientation.

    rows_base     — annotator whose clusters define the grouping
    lookup_left   — key/quote -> Code_Name for the left-column annotator
    cmap_left     — colour map for the left-column annotator
    lookup_right, cmap_right — same for the right-column annotator
    left_suffix   — integer appended as _N to quotes in the left column
    right_suffix  — integer appended as _N to quotes in the right column
    """
    clusters = OrderedDict()
    for row in rows_base:
        clusters.setdefault(row["Code_Name"], []).append(row)

    row_htmls = []
    sep = '<br><hr style="width:100%; border:1px solid black;"><br>'

    for cluster_rows in clusters.values():
        for row in cluster_rows:
            quote = row["Quote"]
            k = extract_key(quote) if use_keys else quote.strip()

            lcode = lookup_left[k]
            rcode = lookup_right[k]
            lcolour = cmap_left.get(lcode) or "#000000"
            rcolour = cmap_right.get(rcode) or "#000000"
            ldisplay = ("[ " + quote + " ]") if cmap_left.get(lcode) is None else quote
            rdisplay = ("[ " + quote + " ]") if cmap_right.get(rcode) is None else quote
            ldisplay += f"_{left_suffix}"
            rdisplay += f"_{right_suffix}"

            row_htmls.append(
                f'<div class="container">'
                f'<div class="quote_left" style="color:{lcolour};">{ldisplay}</div>'
                f'<div class="code_left" style="color:{lcolour};"><em>{lcode}</em></div>'
                f'<div class="quote_right" style="color:{rcolour};">{rdisplay}</div>'
                f'<div class="code_right" style="color:{rcolour};"><em>{rcode}</em></div>'
                f'</div>'
            )
        row_htmls.append(sep)

    return row_htmls


def render_three_view_html(row_htmls, base_label, left_label, right_label):
    header = (
        '<div class="container" style="font-weight:bold; border-bottom: 2px solid #333; '
        'margin-bottom: 6px; padding-bottom: 4px;">'
        f'<div class="quote_left" style="text-align:center;"><h3><u>{base_label} (grouped by)</u></h3></div>'
        f'<div class="code_left"></div>'
        f'<div class="quote_right" style="text-align:center; border-left: 1px solid #ccc;">'
        f'<h3><u>&nbsp;</u></h3></div>'
        f'<div class="code_right"></div>'
        '</div>'
        '<div class="container" style="font-weight:bold; margin-bottom: 10px;">'
        f'<div class="quote_left" style="text-align:center;"><u>{left_label} (by colour)</u></div>'
        f'<div class="code_left"></div>'
        f'<div class="quote_right" style="text-align:center; border-left: 1px solid #ccc;">'
        f'<u>{right_label} (by colour)</u></div>'
        f'<div class="code_right"></div>'
        '</div>'
    )
    return header + "\n".join(row_htmls)


def generate_html_three(all_rows, all_lookups, all_cmaps, use_keys, output_path, labels):
    """Write a three-annotator comparison HTML with a cycle button."""
    rows = all_rows          # [rows1, rows2, rows3]
    lookups = all_lookups    # [lookup1, lookup2, lookup3]
    cmaps = all_cmaps        # [cmap1, cmap2, cmap3]

    # Three views: each annotator takes a turn as the base
    views = []
    for base_i in range(3):
        others = [i for i in range(3) if i != base_i]
        left_i, right_i = others[0], others[1]
        row_htmls = build_three_view(
            rows[base_i],
            lookups[left_i], cmaps[left_i],
            lookups[right_i], cmaps[right_i],
            use_keys,
            left_suffix=left_i + 1,
            right_suffix=right_i + 1,
        )
        views.append(render_three_view_html(
            row_htmls, labels[base_i], labels[left_i], labels[right_i]
        ))

    with open(output_path, "w", encoding="utf-8") as f:
        _write_html_head(f, output_path, three=True)
        _write_explainer(f, n=3)

        cycle_labels_js = "[" + ", ".join(f'"{l}"' for l in labels) + "]"
        f.write(
            f'<button id="cycle-btn" onclick="cycleView()">Base: {labels[0]} &rarr;</button>\n'
        )

        for i, view in enumerate(views):
            display = "" if i == 0 else ' style="display:none;"'
            f.write(f'<div id="view-{i}"{display}>{view}</div>\n')

        f.write(_cycle_script(3, cycle_labels_js))
        f.write("</body>\n</html>\n")


# ---------------------------------------------------------------------------
# Shared HTML helpers
# ---------------------------------------------------------------------------

def _write_html_head(f, title, three):
    f.write("<!DOCTYPE html>\n<html>\n<head>\n")
    f.write(f"<title>{title}</title>\n")
    f.write("<style>\n")
    f.write(".container { display: flex; }\n")
    if three:
        f.write(".quote_left  { width: 38%; word-wrap: break-word; padding: 0 10px 0 20px; }\n")
        f.write(".code_left   { width: 12%; font-size: 11px; padding-right: 10px; }\n")
        f.write(".quote_right { width: 38%; word-wrap: break-word; padding: 0 10px 0 20px; "
                "border-left: 1px solid #ccc; }\n")
        f.write(".code_right  { width: 12%; font-size: 11px; padding-right: 10px; }\n")
    else:
        f.write(".left_column  { width: 80%; word-wrap: break-word; padding: 0 20px; }\n")
        f.write(".right_column { width: 20%; padding-left: 100px; }\n")
    f.write(
        "#cycle-btn { margin: 10px 20px; padding: 8px 16px; "
        "font-size: 14px; cursor: pointer; }\n"
    )
    f.write("</style>\n</head>\n<body>\n")
    f.write(f'<h1 style="padding-left: 20px;">{title}</h1>\n')


def _write_explainer(f, n):
    if n == 2:
        text = (
            "On the left, quotes are grouped by Annotator 1's clusters.<br><br>"
            "Colour coding reflects Annotator 2's clusters. Singleton clusters are black "
            "and wrapped in square brackets.<br><br>"
            "The right column shows Annotator 2's cluster name for each quote.<br><br>"
            "Use <b>Swap Researchers</b> to flip which annotator's grouping is shown."
        )
    else:
        text = (
            "Quotes are grouped by the <em>base annotator's</em> clusters.<br><br>"
            "The left content column is colour-coded by the second annotator; "
            "the right content column by the third. Singleton clusters are black and "
            "wrapped in square brackets.<br><br>"
            "Use <b>Cycle Base</b> to rotate which annotator acts as the base."
        )
    f.write(
        '<p style="padding-left: 20px;">'
        f'<b>How does the visualisation work?</b><br><br>{text}</p>\n'
    )


def _cycle_script(n_views, cycle_labels_js=None):
    script = f"""<script>
var _view = 0;
var _n = {n_views};
"""
    if cycle_labels_js:
        script += f"var _labels = {cycle_labels_js};\n"
    script += """function cycleView() {
    document.getElementById('view-' + _view).style.display = 'none';
    _view = (_view + 1) % _n;
    document.getElementById('view-' + _view).style.display = '';
"""
    if cycle_labels_js:
        script += (
            "    document.getElementById('cycle-btn').innerHTML = "
            "'Base: ' + _labels[_view] + ' &rarr;';\n"
        )
    script += "}\n</script>\n"
    return script


# ---------------------------------------------------------------------------
# Compatibility check
# ---------------------------------------------------------------------------

def check_compatibility(files, all_rows, use_keys):
    """Validate CSV files are compatible and print a clear pass/fail report."""
    ok = True

    # Column check
    print("Checking columns...")
    for filepath, rows in zip(files, all_rows):
        missing = [c for c in ("Code_Name", "Quote") if c not in rows[0]]
        if missing:
            print(f"  FAIL  '{filepath}' is missing column(s): {missing}")
            ok = False
        else:
            print(f"  OK    '{filepath}'")

    if not ok:
        print("\nColumn check failed — cannot proceed with quote/key matching.")
        sys.exit(1)

    # Key/quote check
    if use_keys:
        print("\nChecking numeric keys (--use-keys)...")
        key_sets = []
        for filepath, rows in zip(files, all_rows):
            valid = True
            key_map = {}
            for i, row in enumerate(rows):
                key = extract_key(row["Quote"])
                if key is None:
                    print(
                        f"  FAIL  '{filepath}' row {i + 2} has no key: {row['Quote']!r}"
                    )
                    valid = False
                    ok = False
                elif key in key_map:
                    print(f"  FAIL  '{filepath}' has duplicate key ({key})")
                    valid = False
                    ok = False
                else:
                    key_map[key] = True
            if valid:
                print(f"  OK    '{filepath}' — {len(key_map)} keys")
            key_sets.append(set(key_map.keys()))

        if len(key_sets) >= 2:
            print("\nChecking key sets match across files...")
            reference = key_sets[0]
            for i in range(1, len(key_sets)):
                only_ref = reference - key_sets[i]
                only_other = key_sets[i] - reference
                if only_ref or only_other:
                    ok = False
                    if only_ref:
                        print(
                            f"  FAIL  Keys in '{files[0]}' not in '{files[i]}': "
                            f"{sorted(only_ref)[:10]}"
                        )
                    if only_other:
                        print(
                            f"  FAIL  Keys in '{files[i]}' not in '{files[0]}': "
                            f"{sorted(only_other)[:10]}"
                        )
                else:
                    print(f"  OK    '{files[0]}' and '{files[i]}' share the same keys")
    else:
        print("\nChecking quotes match across files...")
        quote_sets = [
            {row["Quote"].strip() for row in rows} for rows in all_rows
        ]
        reference = quote_sets[0]
        for i in range(1, len(quote_sets)):
            only_ref = reference - quote_sets[i]
            only_other = quote_sets[i] - reference
            if only_ref or only_other:
                ok = False
                if only_ref:
                    print(
                        f"  FAIL  {len(only_ref)} quote(s) in '{files[0]}' "
                        f"not in '{files[i]}':"
                    )
                    for q in list(only_ref)[:3]:
                        print(f"          - {q!r}")
                if only_other:
                    print(
                        f"  FAIL  {len(only_other)} quote(s) in '{files[i]}' "
                        f"not in '{files[0]}':"
                    )
                    for q in list(only_other)[:3]:
                        print(f"          - {q!r}")
            else:
                print(f"  OK    '{files[0]}' and '{files[i]}' share the same quotes")

    print()
    if ok:
        print("All checks passed — files are compatible.")
    else:
        print("Compatibility check failed.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    if len(args.files) not in (2, 3):
        print("Error: provide either 2 or 3 CSV files.", file=sys.stderr)
        sys.exit(1)

    files = args.files
    all_rows = [read_csv(f) for f in files]

    for rows, filepath in zip(all_rows, files):
        validate_columns(rows, filepath)

    if args.check:
        check_compatibility(files, all_rows, args.use_keys)
        return

    # Validate that all files have the same quotes/keys
    validate_matching_pair(all_rows[0], all_rows[1], files[0], files[1], args.use_keys)
    if len(files) == 3:
        validate_matching_pair(all_rows[0], all_rows[2], files[0], files[2], args.use_keys)

    # If --use-keys, also run full key validation on each file individually
    if args.use_keys:
        for rows, filepath in zip(all_rows, files):
            validate_keys(rows, filepath)

    all_lookups = [build_lookup_map(rows, args.use_keys) for rows in all_rows]
    all_cmaps = [build_colour_map(rows) for rows in all_rows]
    labels = [os.path.splitext(os.path.basename(f))[0] for f in files]

    if len(files) == 2:
        generate_html_two(all_rows, all_lookups, all_cmaps, args.use_keys, args.output, labels)
    else:
        generate_html_three(all_rows, all_lookups, all_cmaps, args.use_keys, args.output, labels)

    print(f"HTML written to {args.output}")


if __name__ == "__main__":
    main()
