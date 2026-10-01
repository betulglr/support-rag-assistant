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
Experiment                                                   Hit@1         Hit@4
----------------------------------------------------------   -----------   ------------
Embedding only                                               24/30 (80%)   27/30 (90%)
Hybrid search                                                24/30 (80%)   30/30 (100%)
Hybrid + reranking                                           28/30 (93%)   30/30 (100%)
Hybrid + reranking (diagnostic steps added to 02 and 05)     26/30 (86%)   29/30 (96%)
```

- Hybrid search always gets the correct file into the top 4 (Hit@4 100%). BM25 catches the
  typo-heavy, keyword-driven questions that embeddings miss.
- Reranking lifts the correct candidate to the top, raising Hit@1 from 80% to 93%.
- **Last row:** a diagnostic step was added to runbook 02 (refund amount and the store's
  return-shipping deduction setting) and to runbook 05 (size/variant mix-up). The runbooks are
  more accurate now, but the new SQL content affected some questions in search. On this small
  test set the difference is 2 questions: two 06 questions (price change approval) were missed.
  This drop was accepted on purpose.

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

### 3. Diagnostic database

Create the fictional SQLite database used by the diagnostic tools (standard library only, no
extra packages):

```bash
python db/create_db.py
```

`db/siparion.db` is deleted and rebuilt with the same content on every run. The file is in
`.gitignore`. The RAG assistant (`rag.py`, `eval.py`) does not use this database.

### 4. Running

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

## Diagnostic tools (in development)

Right now the assistant finds the right runbook and shows its check queries. Running those
queries and interpreting the results is still up to the support team. The tools in this section
are the groundwork for an agent that will do that work. Everything runs on fictional data.

- **`db/create_db.py`:** builds a fictional SQLite database (`db/siparion.db`) with the tables
  used in the runbook queries. It holds hundreds of orders, returns, coupons, picking jobs,
  stock movements and price change requests. The seed is fixed, so every run produces the same
  database. The database's "now" is fixed as well: `2026-09-30 15:00:00`. For each cause of the
  six troubleshooting runbooks, one problem scenario is placed among the normal records
  (18 scenarios in total).
- **`db/SENARYOLAR.md`:** the answer key. For each scenario: how the support team would ask,
  the related records, the expected runbook and the expected cause.
- **`db/sorgular_sqlite.md`:** SQLite equivalents of the runbooks' SQL Server queries. The
  runbooks stay in SQL Server syntax.
- **`araclar.py`:** 14 read-only tools. Each read query in the runbooks is a separate function,
  all collected in the `ARACLAR` dictionary. The database is opened read-only and parameters
  are passed with `?`. Data-changing scripts are deliberately not tools. The docstrings state
  which runbook step a tool belongs to, its parameters and how to read the result. They will
  later serve as tool descriptions.
- **`db/test_araclar.py`:** runs the relevant tools for each scenario and checks whether the
  output contains evidence of the expected cause. Result: in 17 scenarios the cause is directly
  visible in the tool output. In the remaining one, S6-C, the cause is the user's list filter.
  That is not stored in the database, so the agent is expected to ask the user.

```bash
python db/create_db.py      # build the database
python db/test_araclar.py   # run the tools against the scenarios
```

**Next step:** expose these tools through an MCP server and build an agent. The agent will find
the runbook with RAG, run the check steps with the tools, and interpret the results using the
runbook's "read the result" rules.

## Files

```
File                   Description
--------------------   ----------------------------------------------------------------
rag.py                 Indexing, hybrid search, reranking, answer generation, validation
eval.py                Hit@1 / Hit@4 evaluation
tests.py               Test questions (TESTS) and ambiguous questions (AMBIGUOUS)
runbooks/              Fictional runbooks and knowledge notes
araclar.py             Read-only diagnostic tools (14 tools, ARACLAR dictionary)
db/create_db.py        Builds the fictional SQLite database
db/SENARYOLAR.md       Answer key for the scenarios
db/sorgular_sqlite.md  SQLite equivalents of the runbook queries
db/test_araclar.py     Runs the tools against the scenarios
requirements.txt       Python dependencies
```
