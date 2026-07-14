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
import random
import re
import sys
from collections import Counter, OrderedDict


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
    parser.add_argument(
        "--combine",
        action="store_true",
        help="Combine two annotation CSVs into a single adjudication CSV with columns "
        "Sentence, Annotator_1_Code, Annotator_2_Code (written to --output)",
    )
    parser.add_argument(
        "--live-adjudication",
        dest="live_adjudication",
        action="store_true",
        help="Launch the interactive two-annotator adjudication GUI in a browser. "
        "Takes a single combined CSV (see --combine) and writes the adjudicated CSV "
        "to --output on each submitted change.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the --live-adjudication local server (default: 8000)",
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
# Combine two CSVs into a single adjudication CSV
# ---------------------------------------------------------------------------

def combine_csvs(rows_a, rows_b, use_keys, output_path):
    """Write a single CSV with columns Sentence, Annotator_1_Code, Annotator_2_Code.

    Rows are emitted in the order of the first file. Annotator 2's code is looked
    up by the numeric key (--use-keys) or by exact quote text. Annotator 1's quote
    text is used as the Sentence.
    """
    import csv as _csv

    lookup_b = build_lookup_map(rows_b, use_keys)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = _csv.writer(f)
        writer.writerow(["Sentence", "Annotator_1_Code", "Annotator_2_Code"])
        for row in rows_a:
            quote = row["Quote"]
            k = extract_key(quote) if use_keys else quote.strip()
            writer.writerow([quote, row["Code_Name"], lookup_b[k]])

    print(f"Combined adjudication CSV written to {output_path} ({len(rows_a)} rows)")


# ---------------------------------------------------------------------------
# Colour maps
# ---------------------------------------------------------------------------

def build_colour_map(rows):
    """Colour map for a file's clusters. Singletons get None (rendered black)."""
    import seaborn as sns

    counts = Counter(row["Code_Name"] for row in rows)
    multi = [name for name, c in counts.items() if c > 1]
    palette = sns.color_palette("husl", len(multi)).as_hex()
    random.shuffle(palette)
    colour_map = {name: palette[i] for i, name in enumerate(multi)}
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

    # Reverse map: other_code -> set of keys that belong to that cluster
    other_code_keys = {}
    for row in rows_base:
        k = extract_key(row["Quote"]) if use_keys else row["Quote"].strip()
        oc = lookup_other[k]
        other_code_keys.setdefault(oc, set()).add(k)

    left_parts, right_parts = [], []
    sep = '<br><br><hr style="width: 100%; border: 1px solid black;"><br><br>'

    for cluster_rows in clusters.values():
        base_keys = set()
        for row in cluster_rows:
            base_keys.add(extract_key(row["Quote"]) if use_keys else row["Quote"].strip())

        for row in cluster_rows:
            quote = row["Quote"]
            k = extract_key(quote) if use_keys else quote.strip()
            other_code = lookup_other[k]
            colour = cmap_other.get(other_code) or "#000000"
            display = ("[ " + quote + " ]") if cmap_other.get(other_code) is None else quote
            fully_contained = other_code_keys[other_code].issubset(base_keys)
            underline = "" if fully_contained else " text-decoration: underline;"

            left_parts.append(f'<p style="color: {colour};">{display}</p>')
            right_parts.append(
                f'<p style="color: {colour}; font-size: 11px;{underline}"><em>{other_code}</em></p>'
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

    # Reverse maps: cluster_code -> set of keys for left and right annotators
    left_code_keys, right_code_keys = {}, {}
    for row in rows_base:
        k = extract_key(row["Quote"]) if use_keys else row["Quote"].strip()
        lc = lookup_left[k]
        rc = lookup_right[k]
        left_code_keys.setdefault(lc, set()).add(k)
        right_code_keys.setdefault(rc, set()).add(k)

    row_htmls = []
    sep = '<br><hr style="width:100%; border:1px solid black;"><br>'

    for cluster_rows in clusters.values():
        base_keys = set()
        for row in cluster_rows:
            base_keys.add(extract_key(row["Quote"]) if use_keys else row["Quote"].strip())

        for row in cluster_rows:
            quote = row["Quote"]
            k = extract_key(quote) if use_keys else quote.strip()

            lcode = lookup_left[k]
            rcode = lookup_right[k]
            lcolour = cmap_left.get(lcode) or "#000000"
            rcolour = cmap_right.get(rcode) or "#000000"
            ldisplay = ("[ " + quote + " ]") if cmap_left.get(lcode) is None else quote
            rdisplay = ("[ " + quote + " ]") if cmap_right.get(rcode) is None else quote

            l_contained = left_code_keys[lcode].issubset(base_keys)
            r_contained = right_code_keys[rcode].issubset(base_keys)
            l_underline = "" if l_contained else " text-decoration: underline;"
            r_underline = "" if r_contained else " text-decoration: underline;"

            lcode_display = f"{lcode}_{left_suffix}"
            rcode_display = f"{rcode}_{right_suffix}"

            row_htmls.append(
                f'<div class="container">'
                f'<div class="quote_left" style="color:{lcolour};">{ldisplay}</div>'
                f'<div class="code_left" style="color:{lcolour};{l_underline}"><em>{lcode_display}</em></div>'
                f'<div class="quote_right" style="color:{rcolour};">{rdisplay}</div>'
                f'<div class="code_right" style="color:{rcolour};{r_underline}"><em>{rcode_display}</em></div>'
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
            "The right column shows Annotator 2's cluster name for each quote. "
            "An <u>underlined</u> cluster name means that cluster is split across "
            "multiple groups — some of its quotes appear elsewhere. No underline means "
            "all quotes of that cluster are contained within the current group.<br><br>"
            "Use <b>Swap Researchers</b> to flip which annotator's grouping is shown."
        )
    else:
        text = (
            "Quotes are grouped by the <em>base annotator's</em> clusters.<br><br>"
            "The left content column is colour-coded by the second annotator; "
            "the right content column by the third. Singleton clusters are black and "
            "wrapped in square brackets.<br><br>"
            "An <u>underlined</u> cluster name means that cluster is split across "
            "multiple groups — some of its quotes appear elsewhere. No underline means "
            "all quotes of that cluster are contained within the current group.<br><br>"
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
# Live adjudication GUI (two annotators)
# ---------------------------------------------------------------------------

_ADJUDICATION_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Live Adjudication</title>
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
         margin: 0; padding: 0 0 40px 0; color: #222; }
  h1 { font-size: 20px; padding: 16px 20px 0 20px; margin: 0; }
  .explainer { padding: 6px 20px 0 20px; color: #555; font-size: 13px; max-width: 1100px; }
  .toolbar { position: sticky; top: 0; background: #fff; z-index: 50;
             padding: 12px 20px; border-bottom: 1px solid #ddd; display: flex;
             align-items: center; gap: 12px; flex-wrap: wrap; }
  button { padding: 7px 14px; font-size: 13px; cursor: pointer; border: 1px solid #bbb;
           border-radius: 5px; background: #f7f7f7; }
  button:disabled { opacity: 0.4; cursor: not-allowed; }
  #page-label { font-weight: 600; }
  .banner { display: none; margin: 0; padding: 8px 20px; background: #fff4d6;
            border-bottom: 1px solid #e6c964; color: #7a5c00; font-size: 13px; }
  .section-title { font-weight: 600; padding: 14px 20px 4px 20px; font-size: 14px; }
  #viz { padding: 4px 20px 10px 20px; }
  .viz-header, .viz-row { display: flex; align-items: baseline; }
  .viz-header { font-weight: 700; color: #333 !important; border-bottom: 2px solid #333;
                margin-bottom: 8px; padding-bottom: 4px; }
  .col-r1 { width: 22%; padding-right: 12px; }
  .col-sent { width: 56%; padding-right: 12px; word-wrap: break-word; }
  .col-r2 { width: 22%; }
  .viz-row { padding: 3px 0; }
  .viz-row [data-role] { cursor: context-menu; }
  .viz-row .col-r1 em, .viz-row .col-r2 em { font-style: normal; }
  hr.grp-sep { border: none; border-top: 1px solid #000; margin: 10px 0; }
  .table-wrap { padding: 0 20px; overflow-x: auto; }
  table.adj-table { border-collapse: collapse; width: 100%; font-size: 13px; }
  table.adj-table th, table.adj-table td { border: 1px solid #ccc; padding: 5px 8px;
        text-align: left; vertical-align: top; }
  table.adj-table th { background: #f0f0f0; }
  td.ro { background: #fafafa; color: #555; }
  td.editable { background: #fffef2; }
  td.editable:focus { outline: 2px solid #4a90d9; background: #fff; }
  .table-actions { padding: 10px 20px; display: flex; gap: 10px; }
  #submit-btn { background: #d9f0d9; border-color: #7bbf7b; }
  #discard-btn { background: #f7dede; border-color: #cf8f8f; }
  .ctx-menu { position: absolute; background: #fff; border: 1px solid #999;
              border-radius: 6px; box-shadow: 0 4px 16px rgba(0,0,0,0.2); z-index: 1000;
              min-width: 170px; max-height: 60vh; overflow-y: auto; padding: 4px 0;
              font-size: 13px; }
  .ctx-title { font-weight: 700; padding: 6px 12px; color: #333; }
  .ctx-item { padding: 5px 14px; cursor: pointer; white-space: nowrap; }
  .ctx-item:hover { background: #e8f0fe; }
  .ctx-item.ctx-action { color: #1a5fb4; }
  .ctx-div { border-top: 1px solid #ddd; margin: 4px 0; }
  #toast { position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%);
           background: #333; color: #fff; padding: 8px 16px; border-radius: 6px;
           font-size: 13px; opacity: 0; transition: opacity 0.25s; pointer-events: none; }
  #toast.show { opacity: 0.95; }
</style>
</head>
<body>
<h1>Live Adjudication — Researcher 1 (R1) vs Researcher 2 (R2)</h1>
<p class="explainer">
  Sentences are grouped by <b>R1</b> (left); rows are coloured by <b>R2</b> (right).
  Singleton R2 clusters are shown in black and wrapped in [ brackets ]. An
  <u>underlined</u> R2 name means that cluster spans more than one R1 group on this page.
  <b>Right-click</b> an R1 name, R2 name, or a sentence to adjudicate, or edit the R1/R2
  cells in the table directly. Changes stay pending until you <b>Submit</b> (which saves
  to disk) or <b>Discard</b>.
</p>
<div class="toolbar">
  <button id="prev-btn" onclick="prevPage()">&larr; Prev</button>
  <span id="page-label"></span>
  <button id="next-btn" onclick="nextPage()">Next &rarr;</button>
</div>
<div class="banner" id="banner">Pending change — Submit or Discard to continue.</div>

<div class="section-title">Cluster view</div>
<div id="viz"></div>

<div class="section-title">Table view (editable: R1, R2)</div>
<div class="table-wrap"><div id="table"></div></div>
<div class="table-actions">
  <button id="submit-btn" onclick="submitChange()">Submit change</button>
  <button id="discard-btn" onclick="discardChange()">Discard change</button>
</div>

<div id="toast"></div>

<script>
const INITIAL = __INITIAL_DATA__;
const N_PAGES = __N_PAGES__;
let committed = INITIAL.records.map(r => ({...r}));
let draft = clone(committed);
let dirty = false;
let currentPage = 0;

function clone(arr) { return arr.map(r => ({...r})); }
function esc(s) { return (s == null ? '' : String(s))
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

// Ordering: strip leading "New - " so a new cluster sorts directly under its base.
function baseOf(label) {
  let d = 0, s = label;
  while (s.startsWith('New - ')) { s = s.slice(6); d++; }
  return [s, d];
}
function cmpLabel(a, b) {
  const [ba, da] = baseOf(a), [bb, db] = baseOf(b);
  if (ba < bb) return -1;
  if (ba > bb) return 1;
  if (da !== db) return da - db;
  return a < b ? -1 : (a > b ? 1 : 0);
}
function cmpStr(a, b) { return a < b ? -1 : (a > b ? 1 : 0); }

function r2Counts() {
  const c = {};
  for (const r of draft) c[r.r2] = (c[r.r2] || 0) + 1;
  return c;
}
function allR1() { return [...new Set(draft.map(r => r.r1))]; }
function allR2() { return [...new Set(draft.map(r => r.r2))]; }
function hashHue(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return ((h % 360) + 360) % 360;
}
function colourFor(label, counts) {
  if ((counts[label] || 0) <= 1) return null;
  return 'hsl(' + hashHue(label) + ', 60%, 42%)';
}
function pageRecords() { return draft.filter(r => r.page === currentPage); }

function render() { renderNav(); renderViz(); renderTable(); renderDirty(); }

function renderNav() {
  document.getElementById('page-label').textContent =
      'Page ' + (currentPage + 1) + ' of ' + N_PAGES;
  document.getElementById('prev-btn').disabled = currentPage <= 0 || dirty;
  document.getElementById('next-btn').disabled = currentPage >= N_PAGES - 1 || dirty;
}

function renderViz() {
  const recs = pageRecords();
  const counts = r2Counts();
  const groups = {};
  for (const r of recs) (groups[r.r1] = groups[r.r1] || []).push(r);
  const r1keys = Object.keys(groups).sort(cmpLabel);

  const r2r1 = {};
  for (const r of recs) (r2r1[r.r2] = r2r1[r.r2] || new Set()).add(r.r1);

  let html = '<div class="viz-header"><div class="col-r1">R1</div>'
      + '<div class="col-sent">Sentence</div><div class="col-r2">R2</div></div>';

  r1keys.forEach((r1, gi) => {
    if (gi > 0) html += '<hr class="grp-sep">';
    const rows = groups[r1].slice().sort((a, b) => cmpStr(a.sentence, b.sentence));
    for (const r of rows) {
      const col = colourFor(r.r2, counts);
      const colour = col || '#000000';
      const single = col === null;
      const sent = single ? '[ ' + esc(r.sentence) + ' ]' : esc(r.sentence);
      const under = (r2r1[r.r2] && r2r1[r.r2].size > 1) ? 'text-decoration:underline;' : '';
      html += '<div class="viz-row" style="color:' + colour + ';">'
        + '<div class="col-r1" data-role="r1" data-id="' + r.id + '">' + esc(r.r1) + '</div>'
        + '<div class="col-sent" data-role="sent" data-id="' + r.id + '">' + sent + '</div>'
        + '<div class="col-r2" data-role="r2" data-id="' + r.id + '" style="' + under + '">'
        + esc(r.r2) + '</div>'
        + '</div>';
    }
  });
  document.getElementById('viz').innerHTML = html;
}

function renderTable() {
  const recs = pageRecords().slice().sort((a, b) => {
    const c = cmpLabel(a.r1, b.r1);
    return c !== 0 ? c : cmpStr(a.sentence, b.sentence);
  });
  let html = '<table class="adj-table"><thead><tr>'
    + '<th>Sentence</th><th>R1</th><th>R2</th><th>R1_Original</th><th>R2_Original</th>'
    + '</tr></thead><tbody>';
  for (const r of recs) {
    html += '<tr>'
      + '<td class="ro">' + esc(r.sentence) + '</td>'
      + '<td class="editable" contenteditable="true" data-id="' + r.id + '" data-field="r1">'
      + esc(r.r1) + '</td>'
      + '<td class="editable" contenteditable="true" data-id="' + r.id + '" data-field="r2">'
      + esc(r.r2) + '</td>'
      + '<td class="ro">' + esc(r.r1_original) + '</td>'
      + '<td class="ro">' + esc(r.r2_original) + '</td>'
      + '</tr>';
  }
  html += '</tbody></table>';
  document.getElementById('table').innerHTML = html;
  document.querySelectorAll('#table .editable').forEach(td => {
    td.addEventListener('blur', onCellBlur);
    td.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); td.blur(); }
    });
  });
}

function onCellBlur(e) {
  const td = e.target;
  const id = +td.dataset.id, field = td.dataset.field;
  const val = td.textContent.trim();
  const rec = draft.find(r => r.id === id);
  if (rec && rec[field] !== val) { rec[field] = val; markDirty(); render(); }
}

function renderDirty() {
  document.getElementById('banner').style.display = dirty ? 'block' : 'none';
  document.getElementById('submit-btn').disabled = !dirty;
  document.getElementById('discard-btn').disabled = !dirty;
}

function markDirty() { dirty = true; }

function prevPage() { if (!dirty && currentPage > 0) { currentPage--; render(); } }
function nextPage() { if (!dirty && currentPage < N_PAGES - 1) { currentPage++; render(); } }

// ---- Reassignment shortlist algorithms ----
function reassignR2Options(rec) {
  const sameCluster = [...new Set(draft.filter(r => r.r1 === rec.r1).map(r => r.r2))]
      .filter(x => x !== rec.r2);
  const clustersWithTarget = new Set(draft.filter(r => r.r2 === rec.r2).map(r => r.r1));
  const otherR2 = [...new Set(draft.filter(r => clustersWithTarget.has(r.r1)).map(r => r.r2))]
      .filter(x => x !== rec.r2);
  const tier1 = sameCluster.slice().sort(cmpLabel);
  const s1 = new Set(tier1);
  const tier2 = otherR2.filter(x => !s1.has(x)).sort(cmpLabel);
  const shortlist = tier1.concat(tier2);
  const sset = new Set(shortlist);
  const bottom = allR2().filter(x => x !== rec.r2 && !sset.has(x)).sort(cmpLabel);
  return { shortlist, bottom };
}

function reassignR1Options(rec) {
  const r2sInCluster = new Set(draft.filter(r => r.r1 === rec.r1).map(r => r.r2));
  const shortlist = [...new Set(draft.filter(r => r2sInCluster.has(r.r2)).map(r => r.r1))]
      .filter(x => x !== rec.r1).sort(cmpLabel);
  const sset = new Set(shortlist);
  const bottom = allR1().filter(x => x !== rec.r1 && !sset.has(x)).sort(cmpLabel);
  return { shortlist, bottom };
}

// ---- Actions ----
function uniquePrefixed(name, existing) {
  const set = new Set(existing);
  let n = name;
  while (set.has(n)) n = 'New - ' + n;
  return n;
}
function makeNewCluster(rec) {
  rec.r1 = uniquePrefixed('New - ' + rec.r1, allR1());
  rec.r2 = uniquePrefixed('New - ' + rec.r2, allR2());
  markDirty(); render();
}
function renameAll(field, oldName) {
  const nn = prompt('Rename all "' + oldName + '" to:', oldName);
  if (nn === null) return;
  const v = nn.trim();
  if (!v || v === oldName) return;
  for (const r of draft) if (r[field] === oldName) r[field] = v;
  markDirty(); render();
}

// ---- Context menu ----
document.addEventListener('contextmenu', function(e) {
  const el = e.target.closest('[data-role]');
  if (!el) return;
  e.preventDefault();
  if (dirty) { toast('Submit or discard the pending change first.'); return; }
  openMenu(e.pageX, e.pageY, el.dataset.role, +el.dataset.id);
});
document.addEventListener('click', closeMenu);
document.addEventListener('scroll', closeMenu, true);

function closeMenu() {
  const m = document.getElementById('ctx-menu');
  if (m) m.remove();
}

function openMenu(x, y, role, id) {
  closeMenu();
  const rec = draft.find(r => r.id === id);
  if (!rec) return;
  const menu = document.createElement('div');
  menu.className = 'ctx-menu';
  menu.id = 'ctx-menu';
  const addTitle = t => {
    const d = document.createElement('div');
    d.className = 'ctx-title'; d.textContent = t; menu.appendChild(d);
  };
  const addItem = (label, fn, cls) => {
    const d = document.createElement('div');
    d.className = 'ctx-item' + (cls ? ' ' + cls : '');
    d.textContent = label;
    d.addEventListener('click', ev => { ev.stopPropagation(); closeMenu(); fn(); });
    menu.appendChild(d);
  };
  const addDivider = () => {
    const d = document.createElement('div');
    d.className = 'ctx-div'; menu.appendChild(d);
  };

  if (role === 'r2') {
    addTitle('Reassign R2');
    const { shortlist, bottom } = reassignR2Options(rec);
    shortlist.forEach(l => addItem(l, () => { rec.r2 = l; markDirty(); render(); }));
    if (shortlist.length && bottom.length) addDivider();
    bottom.forEach(l => addItem(l, () => { rec.r2 = l; markDirty(); render(); }));
    addDivider();
    addItem('Rename All…', () => renameAll('r2', rec.r2), 'ctx-action');
  } else if (role === 'r1') {
    addTitle('Reassign R1');
    const { shortlist, bottom } = reassignR1Options(rec);
    shortlist.forEach(l => addItem(l, () => { rec.r1 = l; markDirty(); render(); }));
    if (shortlist.length && bottom.length) addDivider();
    bottom.forEach(l => addItem(l, () => { rec.r1 = l; markDirty(); render(); }));
    addDivider();
    addItem('Rename All…', () => renameAll('r1', rec.r1), 'ctx-action');
  } else if (role === 'sent') {
    addTitle('Sentence');
    addItem('Make new Cluster', () => makeNewCluster(rec), 'ctx-action');
  }
  document.body.appendChild(menu);
  const w = menu.offsetWidth, h = menu.offsetHeight;
  menu.style.left = Math.min(x, window.innerWidth - w - 6) + 'px';
  menu.style.top = Math.min(y, window.scrollY + window.innerHeight - h - 6) + 'px';
}

// ---- Submit / discard ----
function submitChange() {
  fetch('/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ records: draft }),
  }).then(r => {
    if (!r.ok) throw new Error('save failed');
    committed = clone(draft);
    dirty = false;
    render();
    toast('Saved to disk.');
  }).catch(() => toast('Save failed — check the terminal.'));
}
function discardChange() {
  draft = clone(committed);
  dirty = false;
  render();
  toast('Change discarded.');
}

let _toastTimer = null;
function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => t.classList.remove('show'), 1800);
}

render();
</script>
</body>
</html>
"""


def read_combined_csv(filepath):
    """Read a combined adjudication CSV into a list of record dicts.

    Accepts either the raw combined schema (Sentence, Annotator_1_Code,
    Annotator_2_Code) or a previously-adjudicated file (Sentence, R1, R2,
    R1_Original, R2_Original) so work can be resumed.
    """
    import csv as _csv

    records = []
    with open(filepath, encoding="utf-8", newline="") as f:
        reader = _csv.DictReader(f)
        cols = reader.fieldnames or []
        if "Sentence" not in cols:
            print(
                f"Error: '{filepath}' is missing the 'Sentence' column. Expected a "
                f"combined CSV — generate one with --combine.",
                file=sys.stderr,
            )
            sys.exit(1)
        has_ann = "Annotator_1_Code" in cols and "Annotator_2_Code" in cols
        has_r = "R1" in cols and "R2" in cols
        if not (has_ann or has_r):
            print(
                f"Error: '{filepath}' must have either 'Annotator_1_Code'/"
                f"'Annotator_2_Code' or 'R1'/'R2' columns.",
                file=sys.stderr,
            )
            sys.exit(1)

        for i, row in enumerate(reader):
            sentence = (row.get("Sentence") or "").strip()
            if has_r:
                r1 = (row.get("R1") or "").strip()
                r2 = (row.get("R2") or "").strip()
            else:
                r1 = (row.get("Annotator_1_Code") or "").strip()
                r2 = (row.get("Annotator_2_Code") or "").strip()
            r1_orig = (row.get("R1_Original") or "").strip() or (
                (row.get("Annotator_1_Code") or "").strip() or r1
            )
            r2_orig = (row.get("R2_Original") or "").strip() or (
                (row.get("Annotator_2_Code") or "").strip() or r2
            )
            records.append({
                "id": i,
                "sentence": sentence,
                "r1": r1,
                "r2": r2,
                "r1_original": r1_orig,
                "r2_original": r2_orig,
            })
    if not records:
        print(f"Error: '{filepath}' contains no rows.", file=sys.stderr)
        sys.exit(1)
    return records


def compute_pages(records):
    """Assign each record a 'page' index (conflict component) or None.

    Clusters are nodes in a bipartite graph; each sentence is an edge linking
    its R1 and R2 clusters (using the *original* labels so pages stay stable as
    edits are made). A connected component is a conflict page only if it spans
    more than one R1 cluster or more than one R2 cluster. Returns the page count.
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for rec in records:
        union(("1", rec["r1_original"]), ("2", rec["r2_original"]))

    comps = OrderedDict()
    for rec in records:
        root = find(("1", rec["r1_original"]))
        comps.setdefault(root, []).append(rec)

    pages = []
    for recs in comps.values():
        r1s = {r["r1_original"] for r in recs}
        r2s = {r["r2_original"] for r in recs}
        if len(r1s) > 1 or len(r2s) > 1:
            pages.append(recs)

    pages.sort(key=lambda recs: min(r["r1_original"] for r in recs))

    for rec in records:
        rec["page"] = None
    for pi, recs in enumerate(pages):
        for r in recs:
            r["page"] = pi

    return len(pages)


def write_adjudication_csv(records, output_path):
    """Write the adjudicated records, sorted by R1 then Sentence."""
    import csv as _csv

    ordered = sorted(records, key=lambda r: (r.get("r1", ""), r.get("sentence", "")))
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["Sentence", "R1", "R2", "R1_Original", "R2_Original"])
        for r in ordered:
            w.writerow([
                r.get("sentence", ""), r.get("r1", ""), r.get("r2", ""),
                r.get("r1_original", ""), r.get("r2_original", ""),
            ])


def _adjudication_html(records, n_pages):
    import json

    data = json.dumps({"records": records})
    return (
        _ADJUDICATION_TEMPLATE
        .replace("__INITIAL_DATA__", data)
        .replace("__N_PAGES__", str(n_pages))
    )


def run_live_adjudication(input_csv, output_path, port):
    import http.server
    import socketserver
    import threading
    import webbrowser

    records = read_combined_csv(input_csv)
    n_pages = compute_pages(records)
    state = {"records": records}
    write_adjudication_csv(records, output_path)

    if n_pages == 0:
        print("The two annotators fully agree — there are no conflicts to adjudicate.")
        print(f"Adjudication CSV written to {output_path}")
        return

    def html_bytes():
        return _adjudication_html(state["records"], n_pages).encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                body = html_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == "/save":
                import json
                length = int(self.headers.get("Content-Length", 0))
                try:
                    payload = json.loads(self.rfile.read(length) or b"{}")
                    recs = payload.get("records", [])
                    state["records"] = recs
                    write_adjudication_csv(recs, output_path)
                except Exception as exc:  # noqa: BLE001
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(str(exc).encode("utf-8"))
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            else:
                self.send_error(404)

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler) as httpd:
        url = f"http://127.0.0.1:{port}/"
        print(f"Live adjudication running at {url}")
        print(f"{n_pages} conflict page(s) to review.")
        print(f"Adjudicated CSV is saved to '{output_path}' on each submitted change.")
        print("Press Ctrl+C to stop.")
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # --- Live adjudication: takes a single combined CSV ---
    if args.live_adjudication:
        if len(args.files) != 1:
            print(
                "Error: --live-adjudication takes a single combined CSV "
                "(see --combine).",
                file=sys.stderr,
            )
            sys.exit(1)
        output = args.output
        if output == "comparison.html":
            output = "adjudicated.csv"
        run_live_adjudication(args.files[0], output, args.port)
        return

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

    # --- Combine two CSVs into a single adjudication CSV ---
    if args.combine:
        if len(files) != 2:
            print("Error: --combine requires exactly 2 CSV files.", file=sys.stderr)
            sys.exit(1)
        validate_matching_pair(
            all_rows[0], all_rows[1], files[0], files[1], args.use_keys
        )
        if args.use_keys:
            for rows, filepath in zip(all_rows, files):
                validate_keys(rows, filepath)
        output = args.output
        if output == "comparison.html":
            output = "combined.csv"
        combine_csvs(all_rows[0], all_rows[1], args.use_keys, output)
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
