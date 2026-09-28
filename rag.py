import os, glob, re
from datetime import datetime
import numpy as np
import ollama
from rank_bm25 import BM25Okapi

# RAG_DATA_DIR: içinde runbooks/ ve tests.py olan klasör (yoksa projenin kendi klasörü)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.environ.get("RAG_DATA_DIR") or BASE_DIR)
DOCS_DIR = os.path.join(DATA_DIR, "runbooks")
CHUNK_SIZE = 800
OVERLAP = 150
TOP_K = 4
HYBRID = True    # test daha iyi sonuc verdi degistirme
RERANK = True     # False yaparsan yeniden sıralama kapanır
POOL = 8          # aday toplamak için kaç parçaya bakılacak
CANDIDATES = 4    # yeniden sıralamaya kaç dosya girecek
RRF_K = 60       # sıralamaları birleştirme sabiti (standart değer)
MAX_FILES = 2        # modele en fazla kaç dosya verilecek
LLM_MODEL = "qwen2.5:7b"
EMBED_MODEL = "bge-m3"
UNANSWERED_FILE = "bulunamayan_sorular.txt"
NOT_FOUND = "Kaynaklarda bulamadım, geliştiriciye sorun."

DEV_SECTION = re.compile(
    r"###[^\n]*SADECE geliştirici onayından sonra.*?(?=\n## |\Z)", re.S
)
SQL_BLOCK = re.compile(r"```sql\s*(.*?)```", re.S | re.I)
LABEL_LINE = re.compile(r"\n(?=[A-ZÇĞİÖŞÜ][^\n:]{2,30}:)")
SKIP = ("## Son güncelleme", "Son güncelleme")

CJK = re.compile(r"[\u4e00-\u9fff]")

# --- 1) Notları oku ve temizle ---
def load_docs():
    docs = {}
    for path in glob.glob(os.path.join(DOCS_DIR, "**", "*.md"), recursive=True):
        if os.path.basename(path).lower() == "readme.md":
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = DEV_SECTION.sub(
            "\n[Bu durumda veri değiştiren bir işlem gerekiyor. Geliştiriciye başvurun.]\n",
            text,
        )
        docs[os.path.relpath(path, DOCS_DIR)] = text
    return docs

def chunk(text):
    parts, start = [], 0
    while start < len(text):
        parts.append(text[start:start + CHUNK_SIZE])
        start += CHUNK_SIZE - OVERLAP
    return parts

docs = load_docs()
chunks = []  # (dosya adı, parça metni) — sadece arama içn
for name, text in docs.items():
    for c in chunk(text):
        chunks.append((name, c))

if not chunks:
    raise SystemExit(f"{DOCS_DIR} klasöründe .md dosyası yok.")

# --- 2) Embedding ---
def embed(texts, batch_size=16):
    all_vecs = []
    for i in range(0, len(texts), batch_size):
        resp = ollama.embed(model=EMBED_MODEL, input=texts[i:i + batch_size])
        all_vecs.extend(resp["embeddings"])
    v = np.array(all_vecs, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)

vectors = embed([c[1] for c in chunks])

TR_MAP = str.maketrans("çğıöşüâî", "cgiosuai")

def tokenize(text):
    text = text.replace("İ", "i").lower().translate(TR_MAP)
    words = re.findall(r"\w+", text)
    return [w[:5] for w in words if len(w) > 1]

bm25 = BM25Okapi([tokenize(c[1]) for c in chunks])

print(f"{len(docs)} dosyadan {len(chunks)} parça indekslendi.")

# --- 3) Retrieval: parçalarla ara, en iyi dosyaları seç ---
def search(question, k=TOP_K):
    qv = embed([question])[0]
    emb_scores = vectors @ qv
    if HYBRID:
        bm_scores = bm25.get_scores(tokenize(question))
        fused = np.zeros(len(chunks))
        for r, i in enumerate(np.argsort(emb_scores)[::-1]):
            fused[i] += 1 / (RRF_K + r + 1)
        for r, i in enumerate(np.argsort(bm_scores)[::-1]):
            fused[i] += 1 / (RRF_K + r + 1)
        order = np.argsort(fused)[::-1]
    else:
        order = np.argsort(emb_scores)[::-1]
    top = order[:k]
    # sıralama hibrit, ekranda gösterilen skor embedding benzerliği
    return [(chunks[i][0], float(emb_scores[i])) for i in top]

def pick_files(hits):
    files, first_score = [], None
    for name, score in hits:
        if name in files:
            continue
        if first_score is None:
            first_score = score
        elif score < first_score - 0.1:
            continue
        files.append(name)
        if len(files) == MAX_FILES:
            break
    return files

RERANK_PROMPT = """Aşağıda bir destek ekibi sorusu ve aday dokümanlar var.
Soruyu dikkatle oku ve soruya EN UYGUN dokümanın numarasını seç.
Sadece numarayı yaz, başka hiçbir şey yazma."""

def profile(name, n=700):
    # dokümanın başı: başlık, belirti, nasıl soruluyor
    return docs[name][:n].strip()

def rerank(question, files):
    if len(files) < 2:
        return files
    listing = "\n\n".join(f"[{i + 1}]\n{profile(n)}" for i, n in enumerate(files))
    resp = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": RERANK_PROMPT},
            {"role": "user", "content": f"SORU: {question}\n\nADAYLAR:\n{listing}\n\nEn uygun dokümanın numarası:"},
        ],
        options={"num_ctx": 8192, "temperature": 0},
    )
    m = re.search(r"\d+", resp["message"]["content"])
    if not m:
        return files  # model saçmaladıysa arama sırasını koru
    idx = int(m.group()) - 1
    if not 0 <= idx < len(files):
        return files
    return [files[idx]] + [f for i, f in enumerate(files) if i != idx]

def retrieve(question):
    hits = search(question, POOL)
    files = []
    for name, _ in hits:
        if name not in files:
            files.append(name)
        if len(files) == CANDIDATES:
            break
    if RERANK:
        files = rerank(question, files)
    return files, hits


# --- 4) Doğrulama: cevaptaki SQL kaynakta birebir var mı? ---
def norm(s):
    return " ".join(s.split()).lower()

def invalid_sql(answer_text, source_text):
    src = norm(source_text)
    return [b for b in SQL_BLOCK.findall(answer_text) if norm(b) not in src]

# --- 5) Generation ---
SYSTEM = f"""You are an assistant helping a software company's support team.
Your task: read the question and give the support team a short action plan based ONLY on the runbook in SOURCES.

Rules:
- ALWAYS answer in Turkish. Use simple language, no developer jargon.
- 3 to 6 sentences. Cover:
  1. Which runbook this problem matches,
  2. What to check first, with step numbers (e.g. "runbook'taki 2. ve 3. adımdaki sorguları çalıştırın"),
  3. The most likely causes depending on the result, and what to do,
  4. When to escalate to a developer.
- Do NOT write or copy any SQL. The full runbook with its queries will be shown below your answer.
- Use ONLY information from SOURCES. Never guess.
- If SOURCES are not related to the question, reply with ONLY this exact sentence: "{NOT_FOUND}"
- If SOURCES are related, never use that sentence."""

def log_unanswered(question):
    with open(UNANSWERED_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M}\t{question}\n")

def answer(question):
    files, hits = retrieve(question)
    print("\n--- Aday dosyalar (yeniden sıralanmış) ---")
    for i, name in enumerate(files, 1):
        print(f"{i}. {name}")

    files = files[:MAX_FILES]
    context = "\n\n".join(f"[{n}]\n{docs[n]}" for n in files)

    resp = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"KAYNAKLAR:\n{context}\n\nSORU: {question}"},
        ],
        options={"num_ctx": 8192},
    )
    text = resp["message"]["content"].strip()

    if text.startswith("Kaynaklarda bulamadım"):
        log_unanswered(question)
        return text

    if text.endswith(NOT_FOUND):
        text = text[: -len(NOT_FOUND)].strip()

    out = text
    if re.search(r"[\u4e00-\u9fff]", text):
        out += "\n\n⚠ UYARI: Özette hatalı dil karışması var. Aşağıdaki runbook'u esas alın."

    # Model yine de SQL yazdıysa ve kaynakla uyuşmuyorsa uyar
    if invalid_sql(text, context):
        out += ("\n\n⚠ UYARI: Yukarıdaki SQL runbook'takiyle birebir aynı değil. "
                "Aşağıdaki runbook'taki sorguyu kullanın.")

    # Runbook'un kendisini kod gösterir, model değil
    for n in files:
        out += "\n\n" + "=" * 70 + f"\nRUNBOOK: {n}\n" + "=" * 70 + "\n" + docs[n]
    return out

if __name__ == "__main__":
    while True:
        q = input("\nSoru (çıkmak için boş bırak): ").strip()
        if not q:
            break
        print("\n--- Cevap ---\n" + answer(q))