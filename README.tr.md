# Destek Ekibi RAG Asistanı

Yazılım destek ekibinin sorularını runbook (sorun çözüm rehberi) ve bilgi notlarına dayanarak
cevaplayan, **tamamen yerel çalışan** bir RAG (retrieval-augmented generation) asistanı.
Embedding ve dil modeli [Ollama](https://ollama.com) üzerinden bilgisayarınızda çalışır;
hiçbir veri dışarı gönderilmez.

Destek ekibinden biri sorunu günlük dille yazar (ör. *"müşteri paketim nerde diyo ama sistemde gönderi kodu boş"*). Asistan:

1. En uygun runbook'u bulur,
2. Türkçe, kısa bir eylem planı yazar: hangi runbook, önce hangi adım kontrol edilecek,
   sonuca göre olası nedenler, ne zaman geliştiriciye iletilecek,
3. Cevabın altına runbook'un kendisini **kod tarafından, değiştirilmeden** ekler. SQL
   sorguları her zaman kaynaktan gelir, modelden gelmez.

## Mimari

```
soru -> hibrit arama (bge-m3 + BM25, RRF) -> aday dosyalar -> LLM ile yeniden sıralama
     -> en fazla 2 dosya bağlam olarak -> LLM cevabı -> çıktı doğrulama -> cevap + runbook
```

### İndeksleme
- `runbooks/` altındaki `.md` dosyaları okunur (`README.md` hariç).
- **Geliştirici onayı bölümleri indekse alınmaz.** Başlığında
  `SADECE geliştirici onayından sonra` geçen bölümler (veri değiştiren UPDATE/DELETE
  script'leri) okuma sırasında metinden çıkarılır ve yerine
  *"Bu durumda veri değiştiren bir işlem gerekiyor. Geliştiriciye başvurun."* notu konur.
  Böylece bu script'ler ne aramada eşleşir ne de modele bağlam olarak gider.
- Metin 800 karakterlik, 150 karakter örtüşen parçalara bölünür.

### Hibrit arama
- **Embedding:** `bge-m3` (çok dilli), vektörler normalize edilip kosinüs benzerliği hesaplanır.
- **BM25:** `rank-bm25` ile anahtar kelime araması. Tokenizer Türkçe'ye göre ayarlıdır:
  - **Türkçe karakter normalizasyonu:** `ç ğ ı ö ş ü â î` -> `c g i o s u a i`, `İ` -> `i`.
    Böylece *"yazdırdığım"* ile *"yazdirdigim"* aynı şekilde eşleşir.
  - **5 harf kök kesme:** Her kelimenin ilk 5 harfi alınır (*"siparişleri"* -> `sipar`).
    Türkçe'nin eklemeli yapısı için basit ama etkili bir kök bulma yöntemi.
- **RRF (Reciprocal Rank Fusion):** İki sıralama `1 / (60 + sıra)` puanlarıyla birleştirilir.
  Skorların ölçeği farklı olduğu için değerler yerine sıralar kullanılır.

### LLM ile yeniden sıralama
Arama sonucundaki ilk 4 farklı dosyanın başı (başlık, belirti, "nasıl soruluyor" kısmı)
soruyla birlikte LLM'e verilir ve model en uygun dokümanın numarasını seçer. Model geçersiz
bir cevap verirse arama sırası korunur.

### Cevap üretimi ve çıktı doğrulama
- Model yalnızca verilen kaynaklara dayanarak Türkçe, 3–6 cümlelik bir plan yazar ve SQL yazmaz.
- **SQL doğrulama:** Model yine de SQL yazdıysa, her SQL bloğu kaynak metinde (boşluklar
  normalize edilerek) birebir aranır. Bulunamazsa cevaba uyarı eklenir.
- **Dil karışması kontrolü:** Cevapta Çince karakter varsa (küçük çok dilli modellerde görülen
  bir hata) uyarı eklenir ve kullanıcı runbook'un kendisine yönlendirilir.

### Cevaplanamayan soruların kaydı
Kaynaklar soruyla ilgili değilse model sabit bir cümleyle cevap verir:
*"Kaynaklarda bulamadım, geliştiriciye sorun."* Bu sorular tarih ve saatle birlikte
`bulunamayan_sorular.txt` dosyasına yazılır. Böylece hangi konularda runbook eksik olduğu görülebilir.

## Değerlendirme

`eval.py`, `tests.py` içindeki `(soru, doğru dosya)` çiftleriyle yalnızca **arama ve yeniden
sıralama** adımını ölçer, cevap metnini değerlendirmez.

- **Hit@1:** Doğru dosya ilk sırada mı? Modele en güvenilir bağlam ilk dosyadır.
- **Hit@4:** Doğru dosya yeniden sıralamaya giren 4 aday arasında mı? Aramanın doğru dosyayı
  hiç bulamadığı durumları, yeniden sıralamanın yanlış seçtiği durumlardan ayırır.

Test soruları gerçek destek ekibi dilini taklit edecek şekilde yazıldı: doküman başlıklarındaki
kelimeler kullanılmadı, günlük dil ve yazım hataları var (*"gorunuyo"*, *"atcam"*), bazı sorular
birbirine benzeyen konuları bilerek karıştırıyor (kargo entegrasyonu ↔ depo el terminali, iade ↔ stok).

**`AMBIGUOUS` sorular ayrı tutulur.** Bunlar tek başına okunduğunda birden fazla dosyaya
uyabilecek, bilerek belirsiz yazılmış sorulardır (ör. *"her şeyi yaptık ama hâlâ bekliyor"*).
Bir insan bile ek bilgi olmadan doğru dosyayı seçemez. Bu yüzden skora dahil edilmezler: skoru
anlamsız biçimde düşürür ve arama kalitesindeki gerçek değişimleri gizlerlerdi. İleride
netleştirme sorusu ("hangisini kastettiniz?") özelliğini test etmek için saklanıyorlar.

### Sonuçlar

```
Deney                                                   Hit@1         Hit@4
-----------------------------------------------------   -----------   ------------
Sadece embedding                                        24/30 (%80)   27/30 (%90)
Hibrit arama                                            24/30 (%80)   30/30 (%100)
Hibrit + yeniden sıralama                               28/30 (%93)   30/30 (%100)
Hibrit + yeniden sıralama (02/05'e teşhis adımları)     26/30 (%86)   29/30 (%96)
```

- Hibrit arama doğru dosyayı her zaman ilk 4'e sokuyor (Hit@4 %100). Embedding'in kaçırdığı
  yazım hatalı ve anahtar kelimeye dayalı soruları BM25 yakalıyor.
- Yeniden sıralama, adaylar arasında doğru olanı öne çıkararak Hit@1'i %80'den %93'e taşıyor.
- **Son satır:** Runbook 02'ye (iade tutarı ve mağaza kesinti ayarı) ve 05'e (beden/varyant
  karışıklığı) birer teşhis adımı eklendi. Runbook'lar daha doğru hale geldi, ama yeni SQL
  içerikleri aramada bazı soruları etkiledi. Küçük test setinde fark 2 soru: iki 06 sorusu
  (fiyat talebi onayı) kaçtı. Bu düşüş bilerek kabul edildi.

**Kullanılan model:** Deneylerde LLM olarak `qwen2.5:7b` kullanıldı (`rag.py` içindeki
`LLM_MODEL`). Yeniden sıralama adımı bu modelin kararına dayandığı için "Hibrit + yeniden
sıralama" satırı modele bağlıdır; farklı bir modelle Hit@1 değişebilir. İlk iki satır yalnızca
`bge-m3` ve BM25'e bağlıdır.

Deneyleri tekrarlamak için `rag.py` başındaki ayarlar kullanılır:

```
Deney                       HYBRID   RERANK
-------------------------   ------   ------
Sadece embedding            False    False
Hibrit arama                True     False
Hibrit + yeniden sıralama   True     True
```

## Kurulum

### 1. Ollama ve modeller
[Ollama](https://ollama.com/download)'yı kurun, ardından modelleri indirin:

```bash
ollama pull bge-m3
ollama pull qwen2.5:7b
```

Ollama servisinin çalışıyor olması gerekir (kurulumdan sonra genelde arka planda otomatik başlar).

### 2. Python ortamı

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Teşhis veritabanı

Teşhis araçları için kurgusal SQLite veritabanını oluşturun (yalnızca standart kütüphane
kullanır, ek paket gerekmez):

```bash
python db/create_db.py
```

`db/siparion.db` her çalıştırmada silinip aynı içerikle yeniden oluşturulur. Dosya
`.gitignore` içindedir. RAG asistanı (`rag.py`, `eval.py`) bu veritabanını kullanmaz.

### 4. Çalıştırma

Etkileşimli asistan:

```bash
python rag.py
```

Açılışta dokümanlar indekslenir, ardından soru sorulur. Çıkmak için boş satır girin.

Değerlendirme:

```bash
python eval.py
```

Kaçırılan sorular beklenen ve ilk sıradaki dosyayla birlikte listelenir, sonunda Hit@1 ve
Hit@4 yazdırılır.

## Veri seti

`runbooks/` klasöründeki veri **tamamen kurgusaldır.** Bu veri, *Siparion* adlı hayali bir
e-ticaret sipariş yönetim yazılımının destek ekibi için hazırlandı. Ürün, firma, pazaryeri,
kargo firması, tablo ve ekran adlarının hiçbiri gerçek bir sisteme ait değildir. SQL
sorguları örnek amaçlıdır.

Set, 6 sorun runbook'u ve 4 kısa bilgi notundan oluşur:
- **Runbook'lar** aynı şablonu izler: Belirti -> Etkilenen modül -> Kontrol adımları (salt okunur
  SQL) -> Olası nedenler -> Ne zaman geliştiriciye iletilir -> veri değiştiren script
  (*SADECE geliştirici onayından sonra*).
- **Bilgi notları** kısa, tek paragraflık "nerede / nasıl" cevaplarıdır. Uzun runbook'ların
  daha fazla parça üretmesi, kısa notları aramada dezavantajlı hale getirir. Bu da setin
  bilerek korunan zorluklarından biridir.

## Kendi verinizle kullanmak

Kendi dokümanlarınızı ayrı bir klasörde tutup `RAG_DATA_DIR` ortam değişkeniyle o klasörü
gösterebilirsiniz. Klasörün yapısı şöyle olmalı:

```
veri_klasorum/
    runbooks/     .md dosyalarınız (README.md indekse alınmaz)
    tests.py      TESTS ve AMBIGUOUS listeleri (eval.py için)
```

Değişken tanımlı değilse projenin kendi klasörü kullanılır (kurgusal `runbooks/` ve `tests.py`).

```
# Windows PowerShell
$env:RAG_DATA_DIR = "D:\veri_klasorum"
python eval.py
Remove-Item Env:RAG_DATA_DIR      # varsayılana dön

# macOS / Linux
RAG_DATA_DIR=~/veri_klasorum python eval.py
```

`rag.py` ve `eval.py` aynı değişkeni okur.

## Teşhis araçları (geliştirme aşamasında)

Asistan şu an doğru runbook'u bulup kontrol sorgularını gösteriyor. Sorguları çalıştırmak ve
sonucu yorumlamak hâlâ destek ekibinin işi. Bu bölümdeki araçlar, bu işi yapacak bir agent'ın
altyapısıdır. Hepsi kurgusal veri üzerinde çalışır.

- **`db/create_db.py`:** Runbook sorgularında geçen tablolarla kurgusal bir SQLite veritabanı
  (`db/siparion.db`) oluşturur. Veritabanında yüzlerce sipariş, iade, kupon, toplama işi, stok
  hareketi ve fiyat talebi var. Seed sabit olduğu için her çalıştırmada aynı veritabanı oluşur.
  Veritabanının "şu an"ı da sabittir: `2026-09-30 15:00:00`. Altı sorun runbook'unun her
  nedeni için bir sorunlu senaryo, normal kayıtların arasına dağıtılarak yerleştirildi
  (toplam 18 senaryo).
- **`db/SENARYOLAR.md`:** Cevap anahtarı. Her senaryo için: destek ekibinin soruyu nasıl
  soracağı, ilgili kayıtlar, beklenen runbook ve beklenen neden.
- **`db/sorgular_sqlite.md`:** Runbook'lardaki SQL Server sorgularının SQLite karşılıkları.
  Runbook'lar SQL Server sözdiziminde kalır.
- **`araclar.py`:** 14 salt okunur araç. Runbook'lardaki her okuma sorgusu ayrı bir
  fonksiyondur ve hepsi `ARACLAR` sözlüğünde toplanır. Veritabanı salt okunur açılır,
  parametreler `?` ile verilir. Veri değiştiren script'ler bilerek araç yapılmadı.
  Docstring'lerde aracın hangi runbook adımında kullanılacağı, parametreleri ve sonucun
  nasıl okunacağı yazar. Bunlar ileride araç açıklaması olarak kullanılacak.
- **`db/test_araclar.py`:** Her senaryoda ilgili araçları çalıştırır ve beklenen nedenin
  kanıtı çıktıda var mı diye kontrol eder. Sonuç: 17 senaryoda neden araç çıktısında
  doğrudan görünüyor. Kalan S6-C'de neden, kullanıcının liste filtresi. Bu bilgi
  veritabanında olmadığı için agent'ın kullanıcıya sorması gerekir.

```bash
python db/create_db.py      # veritabanını oluştur
python db/test_araclar.py   # araçları senaryolarla dene
```

**Sonraki adım:** Bu araçları bir MCP server üzerinden sunmak ve bir agent kurmak. Agent
runbook'u RAG ile bulacak, kontrol adımlarını araçlarla çalıştıracak ve sonucu runbook'un
"Sonucu okuyun" kurallarıyla yorumlayacak.

## Dosyalar

```
Dosya                  Açıklama
--------------------   ----------------------------------------------------------------------
rag.py                 İndeksleme, hibrit arama, yeniden sıralama, cevap üretimi ve doğrulama
eval.py                Hit@1 / Hit@4 değerlendirmesi
tests.py               Test soruları (TESTS) ve belirsiz sorular (AMBIGUOUS)
runbooks/              Kurgusal runbook ve bilgi notları
araclar.py             Salt okunur teşhis araçları (14 araç, ARACLAR sözlüğü)
db/create_db.py        Kurgusal SQLite veritabanını oluşturur
db/SENARYOLAR.md       Senaryoların cevap anahtarı
db/sorgular_sqlite.md  Runbook sorgularının SQLite karşılıkları
db/test_araclar.py     Araçları senaryolarla dener
requirements.txt       Python bağımlılıkları
```
