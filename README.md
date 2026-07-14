# Clustering Adjudication

A tool for visually comparing two or three researchers' qualitative coding (clustering) of the same set of student responses. Generates an HTML visualisation that makes it easy to identify agreements and disagreements between coders.

## How It Works

### Two annotators

Given two CSV files, the tool produces an HTML page where:

- Quotes are grouped by **Annotator 1's** clusters.
- Each quote is **colour-coded** by **Annotator 2's** cluster assignment.
- The right column shows **Annotator 2's** cluster name for each quote.
- Singleton clusters (only one quote) are rendered in **black** and wrapped in square brackets.
- Cluster names are **underlined** when that cluster is split across multiple base-annotator groups (i.e. not all of its quotes appear in the current group). No underline means every quote of that colour is contained within the current group.
- A **Swap Researchers** button flips which annotator's grouping is displayed.

When Annotator 1's clusters are internally consistent with Annotator 2's, quotes within a group share the same colour. Mixed colours highlight disagreements.

### Three annotators

Given three CSV files, the tool produces an HTML page where:

- Quotes are grouped by the **base annotator's** clusters.
- Two content columns display the same quotes side by side:
  - **Left column** — colour-coded by the second annotator, with their cluster name alongside.
  - **Right column** — colour-coded by the third annotator, with their cluster name alongside.
- Cluster names are **underlined** when that cluster is split across multiple base-annotator groups. No underline means all quotes of that colour are contained within the current group.
- A **Cycle Base** button (labelled with the current base annotator's name) rotates which annotator acts as the base.

Because the same cluster names may appear in both content columns, a suffix `_N` is appended to each displayed cluster name, where N is the position (1, 2, or 3) of the annotator whose colour coding is shown in that column. For example, if file 2 is colour-coding the left column and file 3 the right, a cluster name `a` will appear as `a_2` on the left and `a_3` on the right. Searching `_2` will find only the left-column instances.

### Live adjudication (two annotators)

Instead of only *viewing* disagreements, you can resolve them interactively in the
browser with `--live-adjudication`. This mode takes a single **combined CSV** (produced
by `--combine`, see below) and launches a small local server — no extra dependencies,
just Python's standard library — then opens the GUI in your browser.

- Sentences are grouped by **R1** (Researcher 1, left column) and colour-coded by
  **R2** (Researcher 2, right column), with the sentence in the middle.
- The tool splits the work into **pages** — one per set of clusters that are entangled
  between the two annotators (a connected component of shared clusters). Pages where R1
  and R2 fully agree are skipped so you only see genuine conflicts.
- A **table** at the bottom (Sentence, R1, R2, R1_Original, R2_Original) mirrors the
  current page, sorted by R1 then Sentence.

**Adjudication controls** (right-click):

| Right-click on | Menu | Effect |
|---|---|---|
| An **R2** name | *Reassign R2* | Change that sentence's R2 cluster. The dropdown lists the most relevant clusters first (those sharing the sentence's R1 group, then those co-occurring with the current R2 cluster elsewhere), a divider, then all remaining R2 clusters alphabetically. |
| An **R1** name | *Reassign R1* | Change that sentence's R1 cluster, with a similarly-ranked shortlist. |
| A **sentence** | *Make new Cluster* | Move the sentence into a brand-new cluster created directly beneath the current one (`New - ` is prepended to both its R1 and R2 names until unique). |
| An **R1 or R2** name | *Rename All…* | Rename every instance of that cluster name at once. |

Cells in the table (except Sentence, R1_Original and R2_Original) can also be edited
directly. All edits stay **pending** — the right-click controls lock — until you press
**Submit change** (which re-renders the view and saves the adjudicated CSV to disk) or
**Discard change** (which reverts). Move between pages with **Prev/Next**.

The output is a single adjudicated CSV (`Sentence, R1, R2, R1_Original, R2_Original`)
written on every submitted change, so nothing is lost if the browser closes. Re-running
`--live-adjudication` on that output file resumes where you left off.

## Requirements

- Python 3.7+
- [seaborn](https://seaborn.pydata.org/) (`pip install seaborn`) — only required for
  generating the static HTML comparisons. `--combine` and `--live-adjudication` use only
  the standard library.

## CSV Format

Each input CSV must have two columns: `Code_Name` and `Quote`.

```
Code_Name,Quote
ClusterA, Plants use sunlight to produce glucose. (1)
ClusterB, Leaves are the main site of photosynthesis in most plants. (2)
```

- The first comma in each row separates the code name from the quote; commas within quotes are handled automatically.
- When using `--use-keys`, every quote must end with a numeric identifier in parentheses, e.g. `(42)`.

## Usage

```bash
python clustering_comparison.py <file1.csv> <file2.csv> [file3.csv] [options]
```

### Arguments

| Argument | Description |
|---|---|
| `file1`, `file2` | Paths to two annotation CSVs (required) |
| `file3` | Path to a third annotation CSV (optional — enables three-annotator mode) |
| `-o`, `--output` | Output HTML file path (default: `comparison.html`) |
| `--use-keys` | Match quotes by the numeric key `(N)` at the end of each quote instead of by exact text |
| `--check` | Validate that the CSV files are compatible without generating any HTML |
| `--combine` | Combine two annotation CSVs into a single adjudication CSV (`Sentence, Annotator_1_Code, Annotator_2_Code`) written to `--output`. Requires exactly 2 files. |
| `--live-adjudication` | Launch the interactive two-annotator adjudication GUI. Takes a single combined CSV (from `--combine`); writes the adjudicated CSV to `--output`. |
| `--port` | Port for the `--live-adjudication` local server (default: `8000`). |

### Examples

**Two annotators, match by exact quote text:**

```bash
python clustering_comparison.py annotations_alice.csv annotations_bob.csv -o alice_bob.html
```

**Two annotators, match by numeric keys:**

```bash
python clustering_comparison.py annotations_alice.csv annotations_bob.csv --use-keys -o alice_bob.html
```

**Three annotators:**

```bash
python clustering_comparison.py annotations_alice.csv annotations_bob.csv annotations_carol.csv --use-keys -o three_person_comparison.html
```

### Live adjudication (two annotators)

First combine the two annotators' files into one CSV, then adjudicate it:

```bash
# 1. Combine into a single adjudication CSV
python clustering_comparison.py Example_Data/Kevin_annotations.csv Example_Data/Michael_annotations.csv --use-keys --combine -o combined.csv

# 2. Launch the interactive adjudication GUI (opens in your browser)
python clustering_comparison.py combined.csv --live-adjudication -o adjudicated.csv
```

If `-o` is omitted, `--combine` defaults to `combined.csv` and `--live-adjudication`
defaults to `adjudicated.csv`. Press `Ctrl+C` in the terminal to stop the server.

### Checking compatibility

The `--check` flag validates that files are compatible without producing any output HTML. It checks:

1. That each file has the required `Code_Name` and `Quote` columns.
2. That all quotes/keys are valid and unique within each file (when `--use-keys` is set, every quote must end with a `(N)` key).
3. That all files share the same set of quotes or keys.

```bash
python clustering_comparison.py file1.csv file2.csv --check
python clustering_comparison.py file1.csv file2.csv file3.csv --use-keys --check
```

## Matching Modes

### Default (exact text matching)

Quotes are matched across files by their full text. All files must contain exactly the same set of quotes. The tool reports any quotes present in one file but missing from another.

### `--use-keys`

Quotes are matched by the numeric identifier at the end of each quote (e.g. `(42)`). This is useful when:

- Quote text may differ slightly between files (e.g. minor edits or formatting differences).
- Quotes were assigned unique IDs during data collection.

The tool validates that:
1. Every quote ends with a `(N)` key.
2. There are no duplicate keys within a file.
3. All files contain the same set of keys.

## Example Data

The `Example_Data/` folder contains sample annotation CSVs:

```bash
# Two annotators
python clustering_comparison.py Example_Data/Kevin_annotations.csv Example_Data/Michael_annotations.csv --use-keys -o example_two.html

# Three annotators
python clustering_comparison.py Example_Data/Kevin_annotations.csv Example_Data/Michael_annotations.csv Example_Data/Dwight_annotations.csv --use-keys -o example_three.html
```

`Researcher1_annotations.csv` and `Researcher2_annotations.csv` are a small
two-annotator set for trying out live adjudication. They match by exact quote text (no
`--use-keys` needed) and split into two conflict pages:

```bash
python clustering_comparison.py Example_Data/Researcher1_annotations.csv Example_Data/Researcher2_annotations.csv --combine -o combined.csv
python clustering_comparison.py combined.csv --live-adjudication -o adjudicated.csv
```
