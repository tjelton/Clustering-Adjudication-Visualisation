# Clustering Adjudication

A tool for visually comparing two or three researchers' qualitative coding (clustering) of the same set of student responses. Generates an HTML visualisation that makes it easy to identify agreements and disagreements between coders.

## How It Works

### Two annotators

Given two CSV files, the tool produces an HTML page where:

- Quotes are grouped by **Annotator 1's** clusters.
- Each quote is **colour-coded** by **Annotator 2's** cluster assignment.
- The right column shows **Annotator 2's** cluster name for each quote.
- Singleton clusters (only one quote) are rendered in **black** and wrapped in square brackets.
- A **Swap Researchers** button flips which annotator's grouping is displayed.

When Annotator 1's clusters are internally consistent with Annotator 2's, quotes within a group share the same colour. Mixed colours highlight disagreements.

### Three annotators

Given three CSV files, the tool produces an HTML page where:

- Quotes are grouped by the **base annotator's** clusters.
- Two content columns display the same quotes side by side:
  - **Left column** — colour-coded by the second annotator, with their cluster name alongside.
  - **Right column** — colour-coded by the third annotator, with their cluster name alongside.
- A **Cycle Base** button (labelled with the current base annotator's name) rotates which annotator acts as the base.

Because the same quote text appears in both content columns, using browser Ctrl+F to search for a quote would highlight it in both columns simultaneously. To make each instance uniquely searchable, a suffix is appended to every displayed quote: `_N`, where N is the position (1, 2, or 3) of the annotator whose colour coding is shown in that column. For example, if file 2 is colour-coding the left column and file 3 the right, the same quote will appear as `...quote text..._2` on the left and `...quote text..._3` on the right. Searching `_2` will find only the left-column instances.

## Requirements

- Python 3.7+
- [seaborn](https://seaborn.pydata.org/) (`pip install seaborn`)

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
python clustering_comparison.py annotations_alice.csv annotations_bob.csv annotations_carol.csv --use-keys -o three_way.html
```

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
