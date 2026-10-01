# Senaryolar — cevap anahtarı

`db/siparion.db` içine yerleştirilen sorunlu senaryolar. Veritabanı `python db/create_db.py` ile
sabit seed kullanılarak oluşturulur, bu yüzden aşağıdaki numaralar her çalıştırmada aynıdır.

- Veritabanının "şu an"ı: **2026-09-30 15:00**. "Dün", "sabahtan beri" gibi ifadeler bu ana göredir.
- Sorunlu kayıtlar normal kayıtlarla karışık durur: aynı tablolarda aynı numaralandırmayla yer alır.
- Sorgular için `db/sorgular_sqlite.md` dosyasına bakın. Aşağıda geçen sorgu numaraları (01-1 vb.)
  o dosyadaki numaralardır.
- Bilgi notlarında (07–10) "Olası nedenler" bölümü olmadığı için senaryo yok. Bu notların
  sorgularının kullandığı veriler (mağaza, SLA süreleri, kullanıcı rolleri) veritabanında var.

## Özet

```
Kod    Runbook                                Beklenen neden
----   ------------------------------------   -----------------------------------------------------
S1-A   01-kargo-takip-no-dusmuyor.md          Kargo firmasının erişim anahtarı süresi dolmuş
S1-B   01-kargo-takip-no-dusmuyor.md          Kargo firmasının servisinde geçici kesinti
S1-C   01-kargo-takip-no-dusmuyor.md          Siparişte kargo firması seçilmemiş
S2-A   02-iade-kapanmiyor-tutar-yanlis.md     Depo paketi teslim almış, kabulü sisteme girmemiş
S2-B   02-iade-kapanmiyor-tutar-yanlis.md     İade adedi satılan adetten fazla girilmiş
S2-C   02-iade-kapanmiyor-tutar-yanlis.md     "İade kargo ücretini müşteriden kes" ayarı açık
S3-A   03-kupon-suresi-dolmus-gorunuyor.md    Uzatma aynı kodla yeni kupon açmış, eski kayıt aktif
S3-B   03-kupon-suresi-dolmus-gorunuyor.md    Vitrin önbelleği yenilenmemiş
S3-C   03-kupon-suresi-dolmus-gorunuyor.md    Kullanıcı uzatmayı yapmış ama kaydetmemiş
S4-A   04-toplama-isi-acik-gorunuyor.md       El terminali ağdan düşmüş, okutmalar cihazda
S4-B   04-toplama-isi-acik-gorunuyor.md       Okutmalar gelmiş ama iş otomatik kapanmamış
S4-C   04-toplama-isi-acik-gorunuyor.md       Ürün yanlış barkodla okutulmuş, satır eksik
S5-A   05-urun-stok-negatif.md                Pazaryeri bildirimi iki kez işlenmiş (mükerrer satış)
S5-B   05-urun-stok-negatif.md                Mal kabul kaydı hiç girilmemiş
S5-C   05-urun-stok-negatif.md                Beden karışıklığı: satış yanlış bedenden düşülmüş
S6-A   06-fiyat-talebi-onay-akisi-takili.md   Onaylayıcı kullanıcı pasife alınmış / ayrılmış
S6-B   06-fiyat-talebi-onay-akisi-takili.md   O adımda onaylayıcı tanımlı değil
S6-C   06-fiyat-talebi-onay-akisi-takili.md   Onaylayıcı yanlış filtre kullanıyor, talep listede var *
```

Toplam 18 senaryo: 6 runbook × 3 neden.

\* S6-C veritabanından teşhis edilemez. Agent kullanıcıya hangi filtreyi kullandığını sormalıdır.
Diğer 17 senaryonun nedeni araç çıktısında doğrudan görünür (`python db/test_araclar.py`).

---

## 01 — Kargo takip numarası siparişe düşmüyor

### S1-A
- **Soru:** "Tezgahlı siparişleri dünden beri hazırlanıyorda kalıyor, S26-00655 ile S26-00659'a hâlâ kargo kodu gelmedi."
- **İlgili kayıtlar:**
  - Siparis `S26-00655` (SiparisId 655, MG-TZG-01, Menzilo Kargo), Durum `HAZIRLANIYOR`, takip no boş.
    KargoKuyruk 637 ve 641 `HATA`. 641, kullanıcının 09-30 10:15'te "Kargoya Gönder"e yeniden basmasıyla oluştu.
  - Siparis `S26-00659` (SiparisId 659, MG-TZG-01, Menzilo Kargo). KargoKuyruk 640 `HATA`.
  - `SonHataMesaji`: "HTTP 401 Unauthorized - yetkisiz erişim: erişim anahtarı (token) süresi dolmuş".
  - Menzilo diğer mağazalarda çalışıyor. 01-2 sorgusunda son başarılı yanıt 09-30 13:57 (S26-00663, Çarşıvera).
- **Beklenen runbook:** 01-kargo-takip-no-dusmuyor.md
- **Beklenen neden:** Kargo firmasının erişim anahtarı süresi dolmuş. Hata Tezgahlı mağazasının
  Menzilo bağlantısında, 2026-09-29 16:20'den beri sürüyor.
- **Script için:** S26-00655 → `@BeklenenSayi = 2` (SiparisId 655). S26-00659 → `@BeklenenSayi = 1` (SiparisId 659).

### S1-B
- **Soru:** "Çarşıvera'daki S26-00660 sabahtan beri Paketra'ya gitmedi, takip numarası hâlâ boş."
- **İlgili kayıtlar:**
  - Siparis `S26-00660` (SiparisId 660, MG-CRV-01, Paketra). KargoKuyruk 642 `BEKLIYOR`,
    DenemeSayisi 8, mesaj "503 Service Unavailable: Paketra servisi yanıt vermiyor...".
  - 01-2 sorgusu: Paketra'nın son başarılı yanıtı **2026-09-30 08:34** (S26-00657, Kervanpazar). Menzilo
    ve Yolkuşu öğleden sonra da yanıt veriyor.
- **Beklenen runbook:** 01-kargo-takip-no-dusmuyor.md
- **Beklenen neden:** Kargo firmasının servisinde geçici kesinti (Paketra, 08:50'den beri).
  Script gerekmez, kayıt kesinti bitince otomatik gönderilir.

### S1-C
- **Soru:** "Web sitesinden gelen S26-00653 dün paketlendi ama kargo barkodu hiç oluşmadı."
- **İlgili kayıtlar:**
  - Siparis `S26-00653` (SiparisId 653, MG-WEB-01), `KargoFirmaId` NULL, Durum `HAZIRLANIYOR`.
  - Toplama işi TPL-42283 `TAMAMLANDI`. KargoKuyruk'ta bu siparişe ait **hiç kayıt yok** (01-1 sorgusu 0 satır döner).
- **Beklenen runbook:** 01-kargo-takip-no-dusmuyor.md
- **Beklenen neden:** Siparişte kargo firması seçilmemiş. Script gerekmez.

## 02 — İade kaydı kapanmıyor / iade tutarı yanlış hesaplanıyor

### S2-A
- **Soru:** "IAD-2026-00177'deki iki sweatshirt de depoya ulaştı ama iadeyi tamamla deyince teslim alınmamış kalem var diyor, geri ödeme de yarım çıkıyor."
- **İlgili kayıtlar:**
  - Iade `IAD-2026-00177` (IadeId 37, sipariş S26-00528, Çarşıvera), Durum `ACIK`.
    IadeKargoTeslimZamani 2026-09-24 11:05, yani paket depoya ulaşmış.
  - IadeKalem 44 (SWT-2101-L): kabul 2026-09-24 15:32.
  - IadeKalem 45 (SWT-2102-M): `TeslimAlmaZamani` **NULL**, Durum `BEKLIYOR`.
  - GeriOdemeTutari 599,90. Doğrusu 599,90 + 529,90 = 1.129,80.
- **Beklenen runbook:** 02-iade-kapanmiyor-tutar-yanlis.md
- **Beklenen neden:** Depo paketi teslim aldığı halde kabul işlemini sisteme girmemiş.
- **Script için:** `@BeklenenSayi = 1`, `@IadeId = 37`.
- **Karıştırılmaması gereken:** IAD-2026-00185'in paketi depoya bugün 08:09'da ulaştı ve henüz kabul
  edilmedi. Bu normal bekleme süresidir. IAD-2026-00186'nın paketi ise henüz depoya gelmedi.

### S2-B
- **Soru:** "IAD-2026-00180'de müşteri tek pijama almış ama geri ödeme 1.349,70 TL çıkıyor, bu nasıl olur?"
- **İlgili kayıtlar:**
  - Iade `IAD-2026-00180` (IadeId 40, sipariş S26-00565, web mağaza), Durum `ACIK`.
  - IadeKalem 48 (PJM-4001-S): `IadeAdet = 3`, `SatisAdet = 1`. Kabul zamanı dolu.
  - GeriOdemeTutari 1.349,70 (3 × 449,90). Doğrusu 449,90.
- **Beklenen runbook:** 02-iade-kapanmiyor-tutar-yanlis.md
- **Beklenen neden:** İade adedi satılan adetten fazla girilmiş. Kullanıcı adedi düzeltmeli, script gerekmez.

### S2-C
- **Soru:** "Kervanpazar'daki IAD-2026-00176 için müşteri 39,90 TL eksik geri ödeme aldığını söylüyor."
- **İlgili kayıtlar:**
  - Iade `IAD-2026-00176` (IadeId 36, sipariş S26-00508, MG-KRV-01), Durum `KAPANDI`.
  - İki kalem de kabul edilmiş, adetler tutarlı: NVR-5001-TEK 1 adet, HVL-3001-MAVI 2 adet.
  - Kalem toplamı 1.279,70. KargoKesintiTutari 39,90. GeriOdemeTutari 1.239,80.
  - Magaza `MG-KRV-01`: `IadeKargoUcretiKes = 1`. Diğer Kervanpazar iadelerinde de aynı kesinti var.
  - 02-2 sorgusu (runbook 02, adım 3; araç `iade_tutar_ozeti`): `IadeKargoUcretiKes = 1`,
    `KalemToplami` 1.279,70, `KargoKesintiTutari` 39,90, `GeriOdemeTutari` 1.239,80 = 1.279,70 - 39,90.
- **Beklenen runbook:** 02-iade-kapanmiyor-tutar-yanlis.md
- **Beklenen neden:** Mağaza ayarlarında "İade kargo ücretini müşteriden kes" açık. Tutar doğru.

## 03 — Kampanya kuponu süresi dolmuş görünüyor

### S3-A
- **Soru:** "GUZ25 kodunu ekim sonuna kadar uzattık ama bazı müşterilerde hâlâ süresi doldu diyor."
- **İlgili kayıtlar:**
  - Kupon 6: GUZ25, bitiş 2026-09-20, `Aktif = 1`, oluşturma 2026-08-28. Eski kayıt.
  - Kupon 9: GUZ25, bitiş 2026-10-31, `Aktif = 1`, oluşturma 2026-09-19. Uzatmanın açtığı yeni kayıt.
  - KuponKullanim: 09-16'ya kadarki kullanımlar kupon 6 ile yapılmış. Sonra yalnızca kupon 9 ile
    2 kullanım var (09-19 ve 09-29). Kod bazı müşterilerde çalışıyor, çoğunda çalışmıyor.
- **Beklenen runbook:** 03-kupon-suresi-dolmus-gorunuyor.md
- **Beklenen neden:** Uzatma işlemi aynı kodla yeni kupon açmış, eski kayıt aktif kalmış.
- **Script için:** `@BeklenenSayi = 1`, `@KuponKodu = 'GUZ25'`. Script kupon 6'yı pasife alır.

### S3-B
- **Soru:** "SONBAHAR15'in bitişini az önce ekim ortasına çektim ama sepette hâlâ süresi dolmuş diyor."
- **İlgili kayıtlar:**
  - Kupon 7: SONBAHAR15, tek kayıt, bitiş **2026-10-15** (doğru). `GuncellemeZamani` 2026-09-30 14:53,
    yani 7 dakika önce. Önceki bitiş 2026-09-29'du.
- **Beklenen runbook:** 03-kupon-suresi-dolmus-gorunuyor.md
- **Beklenen neden:** Vitrin önbelleği yenilenmemiş (15 dakika). Script gerekmez.
- **Not:** `GuncellemeZamani` runbook sorgusunda yok. Runbook'a göre ayırt edici bilgi şu: tek kayıt
  var ve bitiş tarihi doğru.

### S3-C
- **Soru:** "Hafta Sonu Fırsatı kampanyasını 5 Ekim'e uzattık ama HAFTASONU20 kodu artık hiç kabul edilmiyor."
- **İlgili kayıtlar:**
  - Kupon 8: HAFTASONU20, tek kayıt, bitiş hâlâ **2026-09-28**. `GuncellemeZamani` oluşturma ile aynı
    (2026-09-17), yani kupon hiç güncellenmemiş.
  - Kampanya 8 (Hafta Sonu Fırsatı) bitişi 2026-10-05. Kampanya uzatılmış, kupon uzatılmamış.
- **Beklenen runbook:** 03-kupon-suresi-dolmus-gorunuyor.md
- **Beklenen neden:** Kullanıcı uzatmayı yapmış ama "Kaydet" dememiş. Script gerekmez.
- **Karıştırılmaması gereken:** OKUL20'nin bitişi de geçmiş (2026-09-15) ama kampanya normal
  şekilde sona erdi. Kimse uzatmadı.

## 04 — Depo toplama işi tamamlandı ama açık görünüyor

### S4-A
- **Soru:** "Ankara depoda T-ANK-02 ile topladığımız TPL-42301 sabahtan beri açık görünüyor, okuttuklarımız panele gelmedi."
- **İlgili kayıtlar:**
  - ToplamaIsi `TPL-42301` (ToplamaIsiId 646, DP-ANK, terminal T-ANK-02, sipariş S26-00662), `ACIK`.
    İki satırda da `OkutulanAdet = 0`, `OkutmaZamani` NULL.
  - TerminalSenkron (DP-ANK): T-ANK-02'nin son `TAMAMLANDI` kaydı 09-30 10:02. Sonra 10:56'da `HATA`
    ("Bağlantı zaman aşımı...") ve 12:15 ile 13:30'da `BEKLIYOR` ("okutmalar cihazda gönderilmeyi bekliyor").
- **Beklenen runbook:** 04-toplama-isi-acik-gorunuyor.md
- **Beklenen neden:** El terminali ağdan düşmüş, okutmalar cihazda bekliyor. Script gerekmez,
  terminalde "Senkronize Et" yapılmalı.
- **Karıştırılmaması gereken:** DP-ANK'teki TPL-42298 (T-ANK-01) ve diğer depolardaki bazı açık
  işler henüz toplanmaya başlanmamış, normal işler.

### S4-B
- **Soru:** "İstanbul depoda TPL-42285'in tüm ürünleri dün okutuldu ama iş hâlâ toplanıyor görünüyor, sipariş paketlemeye geçmedi."
- **İlgili kayıtlar:**
  - ToplamaIsi `TPL-42285` (ToplamaIsiId 638, DP-IST, T-IST-02, sipariş S26-00654), `ACIK`,
    TamamlanmaZamani NULL.
  - Satırlar: NVR-5001 1/1, YST-7101 2/2. Okutmalar 2026-09-29 15:33 ve 15:54'te merkeze ulaşmış.
  - T-IST-02 senkron kayıtları normal (`TAMAMLANDI`).
- **Beklenen runbook:** 04-toplama-isi-acik-gorunuyor.md
- **Beklenen neden:** Okutmalar gelmiş ama iş durumu otomatik kapanmamış.
- **Script için:** `@BeklenenSayi = 1`, `@ToplamaIsiId = 638`.

### S4-C
- **Soru:** "İzmir depoda TPL-42289'u toplamışlar ama iş kapanmıyor, beyaz havlu bir eksik görünüyor."
- **İlgili kayıtlar:**
  - ToplamaIsi `TPL-42289` (ToplamaIsiId 640, DP-IZM, T-IZM-01, sipariş S26-00656), `ACIK`.
  - Satırlar: TSH-1001 1/1, **HVL-3001 (BEYAZ) 1/2**, CRP-6002 1/1.
  - TerminalSenkron 924 (T-IZM-01, 09-30 09:52, `TAMAMLANDI`). HataMesaji: "1 okutma eşleşmedi: barkod
    8690001002076 (TPL-42289) iş satırlarında yok". Bu barkod HVL-3001-GRI'ye ait.
- **Beklenen runbook:** 04-toplama-isi-acik-gorunuyor.md
- **Beklenen neden:** Bir ürün yanlış barkodla okutulmuş, satır eksik görünüyor. Kapatma scripti bu
  iş için 0 satır günceller (eksik satır olduğu için `NOT EXISTS` koşulu engeller). Doğru çözüm terminalde
  doğru barkodla tekrar okutmak.

## 05 — Ürün stoğu negatif çıkıyor

### S5-A
- **Soru:** "Gri el havlusu eksi 1 görünüyor, Çarşıvera'dan gelen bir sipariş iki kere düşmüş olabilir mi?"
- **İlgili kayıtlar:**
  - StokBakiye: HVL-3002 / HVL-3002-GRI = **-1**.
  - StokHareket 1010 ve 1011: `SATIS`, -2, KaynakReferans `S26-00624/1`. Aralarında 3 saniye var
    (2026-09-24 12:44). Sipariş S26-00624 (Çarşıvera, CRV289820366) için 2 adet satılmış.
  - 05-2 sorgusu (UrunKodu HVL-3002) 1 satır döner: Adet = 2.
- **Beklenen runbook:** 05-urun-stok-negatif.md
- **Beklenen neden:** Aynı pazaryeri sipariş bildirimi iki kez işlenmiş, satış mükerrer düşülmüş.
- **Script için:** `@BeklenenSayi = 1`, `@KaynakReferans = 'S26-00624/1'`, `@VaryantKodu = 'HVL-3002-GRI'`.
  Hareket 1011 silinir, bakiye +1 olur.

### S5-B
- **Soru:** "Yeni sezon fermuarlı sweatshirt M beden eksi 10 görünüyor, depoda koli dolu duruyor."
- **İlgili kayıtlar:**
  - StokBakiye: SWT-2105 / SWT-2105-M = **-10**.
  - SWT-2105-M için yalnızca 7 `SATIS` hareketi var, **hiç `MAL_KABUL` yok**.
  - Aynı ürünün S ve L bedenleri 2026-09-16 10:20'de MKB-2026-0058 ile mal kabul görmüş
    (StokHareket 914, 915). M beden o belgeye girilmemiş.
  - 05-2 sorgusu 0 satır döner (mükerrer yok).
- **Beklenen runbook:** 05-urun-stok-negatif.md
- **Beklenen neden:** Mal kabul kaydı hiç girilmemiş, sadece satışlar işlenmiş. Script gerekmez,
  kullanıcı mal kabulü girmeli.

### S5-C
- **Soru:** "Çizgili pijamanın L bedeni eksi 1 görünüyor, M bedeni ise raftakinden bir fazla."
- **İlgili kayıtlar:**
  - StokBakiye: PJM-4003-L = **-1**, PJM-4003-M = 14 (raftaki gerçek sayı 13).
  - StokHareket 978: `SATIS`, -1, VaryantKodu **PJM-4003-L**, KaynakReferans `S26-00603/1`.
    Siparis S26-00603 (Tezgahlı) kalem 1'in VaryantKodu ise **PJM-4003-M**.
  - 05-2 sorgusu 0 satır döner (mükerrer yok).
  - 05-3 sorgusu (runbook 05, adım 4; araç `stok_varyant_uyusmazligi`, UrunKodu PJM-4003) 1 satır döner:
    HareketId 978, `DusulenVaryant` PJM-4003-L, `SiparisVaryant` PJM-4003-M.
- **Beklenen runbook:** 05-urun-stok-negatif.md
- **Beklenen neden:** Beden/varyant karışıklığı: M beden satışı L bedenden düşülmüş. Kullanıcı hareketin
  varyantını sipariş kalemindeki bedene (M) düzeltmeli. Ekrandan düzeltilemiyorsa geliştiriciye iletilir.

## 06 — Toplu fiyat değişikliği talebi onay akışında takılı

### S6-A
- **Soru:** "FT-2026-0133 outlet indirim listesi iki haftadır finans onayında duruyor, kimsenin ekranına düşmemiş."
- **İlgili kayıtlar:**
  - FiyatTalep `FT-2026-0133` (FiyatTalepId 33, akış OUTLET), Durum `BEKLIYOR`.
  - Adım 1 `ONAYLANDI` (pelin.sarigollu). Adım 2 Finans Onayı `BEKLIYOR`, atanan **murat.ozdemirli**,
    `Aktif = 0`, 2026-09-05'te ayrılmış. Adım 3 `SIRADA`.
  - Diğer akışlarda finans onayı 09-05'ten sonra ozan.cetinkaleli'ye geçmiş. OUTLET akışı güncellenmemiş.
- **Beklenen runbook:** 06-fiyat-talebi-onay-akisi-takili.md
- **Beklenen neden:** Onaylayıcı kullanıcı pasife alınmış / işten ayrılmış.
- **Script için:** `@BeklenenSayi = 1`, `@FiyatTalepId = 33`, `@YeniKullaniciId = 4` (ozan.cetinkaleli).

### S6-B
- **Soru:** "FT-2026-0139 kampanya fiyatları finanstan geçti ama son adımda takıldı, kimin onaylayacağı belli değil."
- **İlgili kayıtlar:**
  - FiyatTalep `FT-2026-0139` (FiyatTalepId 39, akış KAMPANYA), Durum `BEKLIYOR`.
  - Adım 1 ve 2 `ONAYLANDI`. Adım 3 "Kategori Direktörü Onayı" `BEKLIYOR` ve `AtananKullaniciId` **NULL**.
    06-1 sorgusunda KullaniciAdi ve OnaylayiciAktif boş gelir.
- **Beklenen runbook:** 06-fiyat-talebi-onay-akisi-takili.md
- **Beklenen neden:** O adımda hiç onaylayıcı tanımlı değil (akış eksik kurulmuş). Yönetici akış
  tanımını tamamlamalı.

### S6-C
- **Soru:** "Deniz Kaplanlı, FT-2026-0120'yi onay listesinde bulamadığını söylüyor, talep ağustostan beri bekliyor."
- **İlgili kayıtlar:**
  - FiyatTalep `FT-2026-0120` (FiyatTalepId 20, akış TEKSTIL, oluşturma 2026-08-18), Durum `BEKLIYOR`.
  - Adım 3 Mağaza Yöneticisi Onayı `BEKLIYOR`, atanan **deniz.kaplanli**, `Aktif = 1`.
  - Talep 30 günden eski. Senaryo kurgusunda kullanıcı "Bana Atananlar" listesine son 30 günü gösteren
    varsayılan tarih filtresiyle bakıyor. Bu bilgi veritabanında **yok**.
- **Beklenen runbook:** 06-fiyat-talebi-onay-akisi-takili.md
- **Beklenen neden:** Onaylayıcı yanlış filtre/görünüm kullanıyor, talep aslında listede var.
- **Beklenen davranış:** Veritabanından teşhis edilemez; agent kullanıcıya hangi filtreyi
  kullandığını sormalı. Veritabanı yalnızca diğer iki nedeni eler: bekleyen adımda onaylayıcı tanımlı
  ve aktif. Agent kesin bir neden söylememeli. Kullanıcıya "Bana Atananlar" filtresini ve tarih
  aralığını sormalı. `db/test_araclar.py` bu senaryoyu `KULLANICIYA_SOR` olarak işaretler.
- **Dikkat:** 06-1 sonucunda adım 2'de pasif kullanıcı (murat.ozdemirli) görünür. Ama o adım
  `ONAYLANDI` durumunda. Bekleyen adımın onaylayıcısı aktif, bu yüzden bu S6-A değildir.
