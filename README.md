# Support Team RAG Assistant (Turkish)

[Türkçe](README.tr.md)

A **fully local** RAG (retrieval-augmented generation) assistant that answers a software
support team's questions based on runbooks (troubleshooting guides) and knowledge notes.
The embedding and language models run on your own machine through [Ollama](https://ollama.com);
no data leaves the computer.

The documents, the questions and the answers are in Turkish. A support agent describes the
problem in everyday language (e.g. *"müşteri paketim nerde diyo ama sistemde gönderi kodu boş"*,
roughly "the customer asks where their parcel is but the tracking code is empty in the system").
The assistant:

1. Finds the most relevant runbook,
2. Writes a short action plan in Turkish: which runbook applies, which step to check first,
   likely causes depending on the result, and when to escalate to a developer,
3. Appends the runbook itself below the answer, **added by code, unmodified**. SQL queries
   always come from the source, never from the model.

## Architecture

```
question -> hybrid search (bge-m3 + BM25, RRF) -> candidate files -> LLM reranking
         -> at most 2 files as context -> LLM answer -> output validation -> answer + runbook
```

### Indexing
- `.md` files under `runbooks/` are loaded (except `README.md`).
- **Developer-approval sections are not indexed.** Sections whose heading contains
  `SADECE geliştirici onayından sonra` ("ONLY after developer approval"), i.e. the data-changing
  UPDATE/DELETE scripts, are stripped from the text at load time and replaced with a note
  saying "This case requires a data-changing operation. Contact a developer." As a result these
  scripts are never matched by search and never sent to the model as context.
- Text is split into 800-character chunks with a 150-character overlap.

### Hybrid search
- **Embedding:** `bge-m3` (multilingual); vectors are normalized and scored by cosine similarity.
- **BM25:** keyword search with `rank-bm25`. The tokenizer is tuned for Turkish:
  - **Turkish character normalization:** `ç ğ ı ö ş ü â î` -> `c g i o s u a i`, `İ` -> `i`.
    This way *"yazdırdığım"* and *"yazdirdigim"* (typed without Turkish characters) match.
  - **5-letter prefix stemming:** only the first 5 letters of each word are kept
    (*"siparişleri"* -> `sipar`). A simple but effective stemmer for Turkish, which is agglutinative.
- **RRF (Reciprocal Rank Fusion):** the two rankings are merged with `1 / (60 + rank)` scores.
  Ranks are used instead of raw scores because the two scores are on different scales.

### LLM reranking
The beginning of the top 4 distinct files from search (title, symptoms, "how it is usually
asked") is given to the LLM together with the question, and the model picks the number of the
best-matching document. If the model returns an invalid answer, the search order is kept.

### Answer generation and output validation
- The model writes a 3–6 sentence plan in Turkish, based only on the provided sources, without SQL.
- **SQL validation:** if the model writes SQL anyway, every SQL block is searched verbatim in
  the source text (with whitespace normalized). If it is not found, a warning is appended.
- **Language mixing check:** if the answer contains Chinese characters (a known failure of small
  multilingual models), a warning is appended and the user is pointed to the runbook itself.

### Logging unanswered questions
If the sources are unrelated to the question, the model replies with a fixed sentence:
*"Kaynaklarda bulamadım, geliştiriciye sorun."* ("Not found in the sources, ask a developer.")
These questions are written with a timestamp to `bulunamayan_sorular.txt`, which shows where
runbooks are missing.

## Evaluation

`eval.py` uses the `(question, correct file)` pairs in `tests.py` to measure only the
**search and reranking** step; it does not evaluate the answer text.

- **Hit@1:** Is the correct file ranked first? The first file is the most reliable context
  for the model.
- **Hit@4:** Is the correct file among the 4 candidates that go into reranking? This separates
  cases where search never found the right file from cases where reranking picked the wrong one.

The test questions are written to mimic how a real support team talks: words from document
titles are avoided, the language is casual with typos (*"gorunuyo"*, *"atcam"*), and some
questions deliberately mix up similar topics (shipping integration vs. warehouse handheld
terminal, returns vs. stock).

**`AMBIGUOUS` questions are kept separate.** These are intentionally vague questions that could
fit more than one file when read on their own (e.g. *"her şeyi yaptık ama hâlâ bekliyor"*,
"we did everything but it's still waiting"). Even a human could not pick the right file without
more information. They are therefore excluded from the score: they would lower it meaninglessly
and hide real changes in search quality. They are kept for testing a future clarifying-question
feature ("which one did you mean?").

### Results

```
Experiment               Hit@1         Hit@4
----------------------   -----------   ------------
Embedding only           24/30 (80%)   27/30 (90%)
Hybrid search            24/30 (80%)   30/30 (100%)
Hybrid + reranking       28/30 (93%)   30/30 (100%)
```

- Hybrid search always gets the correct file into the top 4 (Hit@4 100%). BM25 catches the
  typo-heavy, keyword-driven questions that embeddings miss.
- Reranking lifts the correct candidate to the top, raising Hit@1 from 80% to 93%.

**Model used:** the experiments used `qwen2.5:7b` as the LLM (`LLM_MODEL` in `rag.py`). Since
reranking relies on this model's decision, the "Hybrid + reranking" row depends on the model;
Hit@1 may differ with another model. The first two rows depend only on `bge-m3` and BM25.

To reproduce the experiments, use the settings at the top of `rag.py`:

```
Experiment               HYBRID   RERANK
----------------------   ------   ------
Embedding only           False    False
Hybrid search            True     False
Hybrid + reranking       True     True
```

## Limitations and what was tried

- **Small test set.** 30 questions; each question is worth about 3 percentage points, so small differences between experiments may be noise.
- **Crude stemming has side effects.** 5-letter prefix stemming handles Turkish suffixes and typos well, but unrelated words can collapse to the same stem (e.g. *"satın almak"*, "to buy", and the *"satınalma"*, "procurement", module).
- **Heading-based chunking was tried and dropped.** Splitting runbooks by `##` headings, with the document title added to each chunk, lowered Hit@1. Generic sections that look alike across runbooks (e.g. "Affected module", "When to escalate") became separate chunks and started scoring high for the wrong files. The simple 800-character chunking was kept.
- **Short knowledge notes are still the weakest point.** Most remaining misses are knowledge notes losing to longer runbooks.
- **Only retrieval is evaluated.** The eval does not measure whether the generated summary is faithful to the source. This is one reason the runbook is always shown verbatim below the answer.
- **Reranking depends on the LLM.** Results were measured with `qwen2.5:7b`; another model may give a different Hit@1.

### Planned

- Clarifying questions for ambiguous queries (the `AMBIGUOUS` set is kept for this)
- Reading error messages from screenshots with a vision-capable model
- Query rewriting when the first search returns weak results
- A persistent vector store instead of re-embedding at every start

## Installation

### 1. Ollama and models
Install [Ollama](https://ollama.com/download), then pull the models:

```bash
ollama pull bge-m3
ollama pull qwen2.5:7b
```

The Ollama service must be running (it usually starts in the background after installation).

### 2. Python environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Running

Interactive assistant:

```bash
python rag.py
```

Documents are indexed at startup, then you can ask questions. Enter an empty line to quit.

Evaluation:

```bash
python eval.py
```

Missed questions are listed with the expected and the top-ranked file, followed by Hit@1 and Hit@4.

## Dataset

The data in `runbooks/` is **entirely fictional.** It was written for the support team of
*Siparion*, an imaginary e-commerce order management software. None of the product, company,
marketplace, shipping carrier, table or screen names belong to a real system. The SQL queries
are illustrative.

The set consists of 6 troubleshooting runbooks and 4 short knowledge notes:
- **Runbooks** follow the same template: Symptoms -> Affected module -> Check steps (read-only
  SQL) -> Possible causes -> When to escalate to a developer -> data-changing script
  (*ONLY after developer approval*).
- **Knowledge notes** are short, single-paragraph "where / how" answers. Long runbooks produce
  more chunks, which puts short notes at a disadvantage in search; this is one of the
  challenges deliberately kept in the set.

## Using your own data

You can keep your own documents in a separate folder and point to it with the `RAG_DATA_DIR`
environment variable. The folder should look like this:

```
my_data_folder/
    runbooks/     your .md files (README.md is not indexed)
    tests.py      TESTS and AMBIGUOUS lists (for eval.py)
```

If the variable is not set, the project's own folder is used (the fictional `runbooks/` and `tests.py`).

```
# Windows PowerShell
$env:RAG_DATA_DIR = "D:\my_data_folder"
python eval.py
Remove-Item Env:RAG_DATA_DIR      # back to default

# macOS / Linux
RAG_DATA_DIR=~/my_data_folder python eval.py
```

`rag.py` and `eval.py` read the same variable.

## Files

```
File               Description
----------------   ----------------------------------------------------------------
rag.py             Indexing, hybrid search, reranking, answer generation, validation
eval.py            Hit@1 / Hit@4 evaluation
tests.py           Test questions (TESTS) and ambiguous questions (AMBIGUOUS)
runbooks/          Fictional runbooks and knowledge notes
requirements.txt   Python dependencies
```
