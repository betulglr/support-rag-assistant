import os
import importlib.util
from rag import retrieve, CANDIDATES, RERANK, DATA_DIR

# tests.py, runbook'larla aynı veri klasöründen yüklenir
TESTS_FILE = os.path.join(DATA_DIR, "tests.py")
if not os.path.exists(TESTS_FILE):
    raise SystemExit(f"{TESTS_FILE} bulunamadı.")
spec = importlib.util.spec_from_file_location("tests", TESTS_FILE)
tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tests)
TESTS, AMBIGUOUS = tests.TESTS, tests.AMBIGUOUS

print(f"Yeniden sıralama: {'AÇIK' if RERANK else 'KAPALI'}\n")

hit1 = hitk = 0
n = len(TESTS)
for i, (question, expected) in enumerate(TESTS, 1):
    print(f"{i}/{n}", end="\r")
    files, _ = retrieve(question)
    if files[0] == expected:
        hit1 += 1
    else:
        print(f"KAÇTI: '{question}'\n   beklenen: {expected}\n   ilk sırada: {files[0]}")
    if expected in files:
        hitk += 1

print(f"\nHit@1: {hit1}/{n} (%{100 * hit1 // n})")
print(f"Hit@{CANDIDATES}: {hitk}/{n} (%{100 * hitk // n})")