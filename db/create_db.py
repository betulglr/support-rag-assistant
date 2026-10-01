"""Siparion runbook'ları için sahte (kurgusal) SQLite veritabanı oluşturur.

Çalıştırma:   python db/create_db.py
Çıktı:        db/siparion.db  (varsa silinir, sabit seed ile her seferinde aynısı oluşur)

- Yalnızca Python'un standart kütüphanesi (sqlite3) kullanılır.
- Tüm kişi, mağaza, pazaryeri, kargo firması ve ürün adları kurgusaldır.
- Veritabanının "şu an"ı SIMDI sabitidir (2026-09-30 15:00). Saatler yerel saattir.
- Runbook'lardaki sorunlara karşılık gelen senaryoların cevap anahtarı: db/SENARYOLAR.md
"""
import os
import random
import sqlite3
from datetime import datetime, timedelta

SEED = 20260928
SIMDI_METIN = "2026-09-30 15:00:00"   # araclar.py içindeki SIMDI ile aynı olmalı
SIMDI = datetime.fromisoformat(SIMDI_METIN)
BASLANGIC = datetime(2026, 7, 1)
DB_YOLU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "siparion.db")

rng = random.Random(SEED)


def saat(h):
    return timedelta(hours=h)


def dk(m):
    return timedelta(minutes=m)


def z(s):
    """'2026-09-30 15:00' -> datetime"""
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


def ts(d):
    return d.strftime("%Y-%m-%d %H:%M:%S") if d else None


# --------------------------------------------------------------------------------------
# Şema
# --------------------------------------------------------------------------------------
SEMA = """
CREATE TABLE Magaza (
    MagazaId            INTEGER PRIMARY KEY,
    MagazaKodu          TEXT NOT NULL UNIQUE,
    MagazaAdi           TEXT NOT NULL,
    PazaryeriKodu       TEXT NOT NULL,
    SaticiId            TEXT NOT NULL UNIQUE,
    Aktif               INTEGER NOT NULL,
    IadeKargoUcretiKes  INTEGER NOT NULL DEFAULT 0,   -- "İade kargo ücretini müşteriden kes"
    OlusturmaZamani     TEXT NOT NULL
);
CREATE TABLE Musteri (
    MusteriId     INTEGER PRIMARY KEY,
    AdSoyad       TEXT NOT NULL,
    Eposta        TEXT NOT NULL,
    Sehir         TEXT NOT NULL,
    KayitZamani   TEXT NOT NULL
);
CREATE TABLE KargoFirma (
    KargoFirmaId  INTEGER PRIMARY KEY,
    FirmaKodu     TEXT NOT NULL UNIQUE,
    FirmaAdi      TEXT NOT NULL,
    Aktif         INTEGER NOT NULL
);
CREATE TABLE Depo (
    DepoId    INTEGER PRIMARY KEY,
    DepoKodu  TEXT NOT NULL UNIQUE,
    DepoAdi   TEXT NOT NULL,
    Sehir     TEXT NOT NULL
);
CREATE TABLE Urun (
    UrunId           INTEGER PRIMARY KEY,
    UrunKodu         TEXT NOT NULL UNIQUE,
    UrunAdi          TEXT NOT NULL,
    Kategori         TEXT NOT NULL,
    SatisFiyati      REAL NOT NULL,
    Aktif            INTEGER NOT NULL,
    OlusturmaZamani  TEXT NOT NULL
);
CREATE TABLE UrunVaryant (
    VaryantId    INTEGER PRIMARY KEY,
    UrunId       INTEGER NOT NULL REFERENCES Urun(UrunId),
    VaryantKodu  TEXT NOT NULL UNIQUE,
    VaryantAdi   TEXT NOT NULL,
    Barkod       TEXT NOT NULL UNIQUE
);
CREATE TABLE Siparis (
    SiparisId           INTEGER PRIMARY KEY,
    SiparisNo           TEXT NOT NULL UNIQUE,
    PazaryeriSiparisNo  TEXT,
    MagazaId            INTEGER NOT NULL REFERENCES Magaza(MagazaId),
    MusteriId           INTEGER NOT NULL REFERENCES Musteri(MusteriId),
    DepoId              INTEGER REFERENCES Depo(DepoId),
    KargoFirmaId        INTEGER REFERENCES KargoFirma(KargoFirmaId),
    Durum               TEXT NOT NULL,   -- YENI, HAZIRLANIYOR, KARGOYA_HAZIR, KARGODA, TESLIM_EDILDI, IPTAL
    SiparisTarihi       TEXT NOT NULL,
    OnayZamani          TEXT,
    KargoTakipNo        TEXT,
    KargoyaVermeZamani  TEXT,
    TeslimZamani        TEXT,
    IptalZamani         TEXT,
    IndirimTutari       REAL NOT NULL DEFAULT 0,
    ToplamTutar         REAL NOT NULL
);
CREATE TABLE SiparisKalem (
    SiparisKalemId  INTEGER PRIMARY KEY,
    SiparisId       INTEGER NOT NULL REFERENCES Siparis(SiparisId),
    SiraNo          INTEGER NOT NULL,
    UrunId          INTEGER NOT NULL REFERENCES Urun(UrunId),
    UrunKodu        TEXT NOT NULL,
    VaryantKodu     TEXT NOT NULL,
    Adet            INTEGER NOT NULL,
    BirimFiyat      REAL NOT NULL,
    Tutar           REAL NOT NULL
);
CREATE TABLE KargoKuyruk (
    KuyrukId          INTEGER PRIMARY KEY,
    SiparisId         INTEGER NOT NULL REFERENCES Siparis(SiparisId),
    KargoFirmaId      INTEGER NOT NULL REFERENCES KargoFirma(KargoFirmaId),
    Durum             TEXT NOT NULL,   -- BEKLIYOR, GONDERILDI, HATA
    DenemeSayisi      INTEGER NOT NULL,
    SonHataMesaji     TEXT,
    OlusturmaZamani   TEXT NOT NULL,
    SonDenemeZamani   TEXT
);
CREATE TABLE Iade (
    IadeId                 INTEGER PRIMARY KEY,
    IadeNo                 TEXT NOT NULL UNIQUE,
    SiparisId              INTEGER NOT NULL REFERENCES Siparis(SiparisId),
    Durum                  TEXT NOT NULL,   -- ACIK, KAPANDI
    IadeNedeni             TEXT NOT NULL,
    OlusturmaZamani        TEXT NOT NULL,
    IadeKargoTeslimZamani  TEXT,            -- iade paketi depoya ulaştı (kargo firmasının bildirimi)
    KapanisZamani          TEXT,
    KargoKesintiTutari     REAL NOT NULL DEFAULT 0,
    GeriOdemeTutari        REAL
);
CREATE TABLE IadeKalem (
    IadeKalemId       INTEGER PRIMARY KEY,
    IadeId            INTEGER NOT NULL REFERENCES Iade(IadeId),
    SiraNo            INTEGER NOT NULL,
    SiparisKalemId    INTEGER NOT NULL REFERENCES SiparisKalem(SiparisKalemId),
    UrunKodu          TEXT NOT NULL,
    VaryantKodu       TEXT NOT NULL,
    IadeAdet          INTEGER NOT NULL,
    TeslimAlmaZamani  TEXT,                -- depo kabul zamanı
    Durum             TEXT NOT NULL         -- BEKLIYOR, KABUL_EDILDI
);
CREATE TABLE Kampanya (
    KampanyaId       INTEGER PRIMARY KEY,
    KampanyaAdi      TEXT NOT NULL,
    BaslangicTarihi  TEXT NOT NULL,
    BitisTarihi      TEXT NOT NULL,
    Aktif            INTEGER NOT NULL
);
CREATE TABLE Kupon (
    KuponId           INTEGER PRIMARY KEY,
    KuponKodu         TEXT NOT NULL,        -- bilerek UNIQUE değil (4.5 öncesi mükerrer kayıt hatası)
    KampanyaId        INTEGER NOT NULL REFERENCES Kampanya(KampanyaId),
    IndirimOrani      REAL NOT NULL,
    BaslangicTarihi   TEXT NOT NULL,
    BitisTarihi       TEXT NOT NULL,
    Aktif             INTEGER NOT NULL,
    OlusturmaZamani   TEXT NOT NULL,
    GuncellemeZamani  TEXT NOT NULL
);
CREATE TABLE KuponKullanim (
    KuponKullanimId  INTEGER PRIMARY KEY,
    KuponId          INTEGER NOT NULL REFERENCES Kupon(KuponId),
    SiparisId        INTEGER NOT NULL REFERENCES Siparis(SiparisId),
    IndirimTutari    REAL NOT NULL,
    KullanimZamani   TEXT NOT NULL
);
CREATE TABLE ToplamaIsi (
    ToplamaIsiId      INTEGER PRIMARY KEY,
    IsNo              TEXT NOT NULL UNIQUE,
    DepoId            INTEGER NOT NULL REFERENCES Depo(DepoId),
    SiparisId         INTEGER NOT NULL REFERENCES Siparis(SiparisId),
    TerminalKodu      TEXT NOT NULL,
    Durum             TEXT NOT NULL,   -- ACIK, TAMAMLANDI
    OlusturmaZamani   TEXT NOT NULL,
    TamamlanmaZamani  TEXT
);
CREATE TABLE ToplamaSatir (
    ToplamaSatirId  INTEGER PRIMARY KEY,
    ToplamaIsiId    INTEGER NOT NULL REFERENCES ToplamaIsi(ToplamaIsiId),
    UrunKodu        TEXT NOT NULL,
    VaryantKodu     TEXT NOT NULL,
    Barkod          TEXT NOT NULL,
    IstenenAdet     INTEGER NOT NULL,
    OkutulanAdet    INTEGER NOT NULL,
    OkutmaZamani    TEXT
);
CREATE TABLE TerminalSenkron (
    TerminalSenkronId  INTEGER PRIMARY KEY,
    DepoId             INTEGER NOT NULL REFERENCES Depo(DepoId),
    TerminalKodu       TEXT NOT NULL,
    Durum              TEXT NOT NULL,   -- TAMAMLANDI, BEKLIYOR, HATA
    KayitSayisi        INTEGER NOT NULL,
    GonderimZamani     TEXT NOT NULL,
    HataMesaji         TEXT
);
CREATE TABLE StokHareket (
    HareketId       INTEGER PRIMARY KEY,
    UrunId          INTEGER NOT NULL REFERENCES Urun(UrunId),
    VaryantKodu     TEXT NOT NULL,
    HareketTipi     TEXT NOT NULL,   -- MAL_KABUL, SATIS, IADE_GIRIS
    Miktar          INTEGER NOT NULL, -- giriş +, çıkış -
    HareketTarihi   TEXT NOT NULL,
    KaynakReferans  TEXT NOT NULL
);
CREATE TABLE StokBakiye (
    UrunId            INTEGER NOT NULL REFERENCES Urun(UrunId),
    VaryantKodu       TEXT NOT NULL,
    Bakiye            INTEGER NOT NULL,
    SonHareketZamani  TEXT,
    PRIMARY KEY (UrunId, VaryantKodu)
);
CREATE TABLE Kullanici (
    KullaniciId    INTEGER PRIMARY KEY,
    KullaniciAdi   TEXT NOT NULL UNIQUE,
    AdSoyad        TEXT NOT NULL,
    Eposta         TEXT NOT NULL,
    MagazaGrubu    TEXT NOT NULL,
    Aktif          INTEGER NOT NULL,
    AyrilmaTarihi  TEXT
);
CREATE TABLE Rol (
    RolId    INTEGER PRIMARY KEY,
    RolAdi   TEXT NOT NULL UNIQUE
);
CREATE TABLE Yetki (
    YetkiId    INTEGER PRIMARY KEY,
    YetkiKodu  TEXT NOT NULL UNIQUE,
    Aciklama   TEXT NOT NULL
);
CREATE TABLE RolYetki (
    RolId    INTEGER NOT NULL REFERENCES Rol(RolId),
    YetkiId  INTEGER NOT NULL REFERENCES Yetki(YetkiId),
    PRIMARY KEY (RolId, YetkiId)
);
CREATE TABLE KullaniciRol (
    KullaniciId  INTEGER NOT NULL REFERENCES Kullanici(KullaniciId),
    RolId        INTEGER NOT NULL REFERENCES Rol(RolId),
    PRIMARY KEY (KullaniciId, RolId)
);
CREATE TABLE FiyatTalep (
    FiyatTalepId          INTEGER PRIMARY KEY,
    TalepNo               TEXT NOT NULL UNIQUE,
    AkisKodu              TEXT NOT NULL,
    Aciklama              TEXT NOT NULL,
    UrunSayisi            INTEGER NOT NULL,
    OlusturanKullaniciId  INTEGER NOT NULL REFERENCES Kullanici(KullaniciId),
    Durum                 TEXT NOT NULL,   -- BEKLIYOR, YAYINDA, REDDEDILDI
    OlusturmaZamani       TEXT NOT NULL,
    YayinZamani           TEXT
);
CREATE TABLE FiyatOnayAdim (
    FiyatOnayAdimId    INTEGER PRIMARY KEY,
    FiyatTalepId       INTEGER NOT NULL REFERENCES FiyatTalep(FiyatTalepId),
    AdimSira           INTEGER NOT NULL,
    AdimAdi            TEXT NOT NULL,
    AtananKullaniciId  INTEGER REFERENCES Kullanici(KullaniciId),
    AdimDurum          TEXT NOT NULL,   -- SIRADA, BEKLIYOR, ONAYLANDI, REDDEDILDI, IPTAL
    IslemZamani        TEXT
);
CREATE INDEX IX_Siparis_Magaza ON Siparis(MagazaId, OnayZamani);
CREATE INDEX IX_KargoKuyruk_Siparis ON KargoKuyruk(SiparisId);
CREATE INDEX IX_StokHareket_Urun ON StokHareket(UrunId, VaryantKodu);
CREATE INDEX IX_Kupon_Kod ON Kupon(KuponKodu);
"""

# --------------------------------------------------------------------------------------
# Sabit tanımlar (kurgusal)
# --------------------------------------------------------------------------------------
MAGAZALAR = [
    # kod, ad, pazaryeri, satıcı id, aktif, iade kargo kesintisi, oluşturma
    ("MG-CRV-01", "Lavanta Tekstil - Çarşıvera", "CRV", "418230", 1, 0, "2025-11-03 10:15:00"),
    ("MG-TZG-01", "Lavanta Tekstil - Tezgahlı", "TZG", "TZ-77104", 1, 0, "2025-12-12 14:40:00"),
    ("MG-WEB-01", "Lavanta Online (web sitesi)", "WEB", "WEB-0001", 1, 0, "2025-10-01 09:00:00"),
    ("MG-KRV-01", "Lavanta Ev - Kervanpazar", "KRV", "KP-5523190", 1, 1, "2026-05-20 11:05:00"),
    ("MG-CRV-02", "Lavanta Outlet - Çarşıvera", "CRV", "418977", 0, 0, "2025-11-20 16:30:00"),
]
MAGAZA_ID = {m[0]: i + 1 for i, m in enumerate(MAGAZALAR)}
KRV_KESINTI = 39.90

KARGO_FIRMALARI = [("MNZ", "Menzilo Kargo"), ("PKT", "Paketra"), ("YKS", "Yolkuşu Kargo")]
MENZILO, PAKETRA, YOLKUSU = 1, 2, 3

DEPOLAR = [("DP-IST", "İstanbul Merkez Depo", "İstanbul"),
           ("DP-ANK", "Ankara Aktarma Depo", "Ankara"),
           ("DP-IZM", "İzmir Depo", "İzmir")]
DEPO_ID = {d[0]: i + 1 for i, d in enumerate(DEPOLAR)}
TERMINALLER = {"DP-IST": ["T-IST-01", "T-IST-02", "T-IST-03"],
               "DP-ANK": ["T-ANK-01", "T-ANK-02"],
               "DP-IZM": ["T-IZM-01", "T-IZM-02"]}

URUNLER = [
    # kod, ad, kategori, fiyat, varyantlar, oluşturma, seçilme ağırlığı
    ("TSH-1001", "Basic Pamuklu Tişört", "Giyim", 249.90, ["S", "M", "L", "XL"], "2026-03-01 10:00", 3),
    ("TSH-1002", "Oversize Baskılı Tişört", "Giyim", 329.90, ["S", "M", "L", "XL"], "2026-03-01 10:00", 3),
    ("TSH-1003", "V Yaka Tişört", "Giyim", 279.90, ["S", "M", "L"], "2026-03-01 10:00", 2),
    ("SWT-2101", "Kapüşonlu Sweatshirt", "Giyim", 599.90, ["S", "M", "L", "XL"], "2026-03-01 10:00", 2),
    ("SWT-2102", "Bisiklet Yaka Sweatshirt", "Giyim", 529.90, ["S", "M", "L"], "2026-03-01 10:00", 2),
    ("SWT-2105", "Fermuarlı Sweatshirt (Yeni Sezon)", "Giyim", 689.90, ["S", "M", "L"], "2026-09-16 12:00", 7),
    ("PJM-4001", "Pamuklu Pijama Takımı", "Giyim", 449.90, ["S", "M", "L"], "2026-03-01 10:00", 2),
    ("PJM-4002", "Kadife Pijama Takımı", "Giyim", 549.90, ["S", "M", "L"], "2026-03-01 10:00", 1),
    ("PJM-4003", "Çizgili Pijama Takımı", "Giyim", 399.90, ["S", "M", "L"], "2026-03-01 10:00", 2),
    ("HVL-3001", "Pamuk Banyo Havlusu 70x140", "Ev Tekstili", 189.90, ["BEYAZ", "GRI", "MAVI"], "2026-03-01 10:00", 3),
    ("HVL-3002", "El Havlusu 50x90", "Ev Tekstili", 99.90, ["BEYAZ", "GRI"], "2026-03-01 10:00", 2),
    ("HVL-3003", "Waffle Bornoz", "Ev Tekstili", 749.90, ["S", "M", "L"], "2026-03-01 10:00", 1),
    ("NVR-5001", "Ranforce Nevresim Takımı", "Ev Tekstili", 899.90, ["TEK", "CIFT"], "2026-03-01 10:00", 2),
    ("NVR-5002", "Saten Nevresim Takımı", "Ev Tekstili", 1299.90, ["CIFT"], "2026-03-01 10:00", 1),
    ("YST-7101", "Yastık Kılıfı 2'li", "Ev Tekstili", 159.90, ["BEYAZ", "GRI"], "2026-03-01 10:00", 2),
    ("ORT-7001", "Keten Masa Örtüsü 160x220", "Ev Tekstili", 349.90, ["STD"], "2026-03-01 10:00", 1),
    ("CRP-6001", "Spor Çorap 3'lü", "Aksesuar", 89.90, ["STD"], "2026-03-01 10:00", 3),
    ("CRP-6002", "Patik Çorap 5'li", "Aksesuar", 109.90, ["STD"], "2026-03-01 10:00", 2),
]
VARYANT = {}   # varyant kodu -> (urun_id, urun_kodu, fiyat, barkod)
for ui, u in enumerate(URUNLER, 1):
    for vi, v in enumerate(u[4], 1):
        VARYANT[f"{u[0]}-{v}"] = (ui, u[0], u[3], f"869{ui:05d}{vi:02d}{(ui * 7 + vi * 3) % 1000:03d}")

ADLAR = ["Aylin", "Barış", "Ceren", "Doğan", "Ebru", "Ferhat", "Gülsüm", "Halil", "İpek", "Kerem",
         "Leyla", "Mert", "Nazlı", "Orhan", "Pınar", "Rıza", "Sevda", "Tarık", "Ümran", "Volkan",
         "Yasemin", "Zafer", "Melis", "Taylan"]
SOYADLAR = ["Kuzeyli", "Akyazılı", "Bozdoğanlı", "Çamlıbelli", "Dereköylü", "Erenkaya", "Göktaşlı",
            "Ilgazlı", "Karaçamlı", "Narlıdereli", "Ovacıklı", "Pınarbaşlı", "Sarıçamlı", "Tepecikli",
            "Uluyazı", "Yeşilovalı"]
SEHIRLER = ["İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Eskişehir", "Konya", "Trabzon",
            "Kayseri", "Samsun"]

# Senaryo zamanları
TOKEN_BITIS = z("2026-09-29 16:20")       # Menzilo erişim anahtarı (Tezgahlı mağazası) bu andan sonra 401
PAKETRA_KESINTI = z("2026-09-30 08:50")   # Paketra servisi bu andan beri yanıt vermiyor
ANK02_KOPMA = z("2026-09-30 10:05")       # T-ANK-02 el terminali ağdan düştü

senaryo_log = []


def log(kod, metin):
    senaryo_log.append(f"{kod}: {metin}")


# --------------------------------------------------------------------------------------
# Siparişler (önce plan olarak üretilir, senaryolar plana uygulanır, sonra tablolar yazılır)
# --------------------------------------------------------------------------------------
def zaman_doldur(p, onay):
    p["onay"] = onay
    sla = rng.uniform(3, 40) if rng.random() < 0.86 else rng.uniform(48.5, 90)
    p["bas"] = onay + saat(sla * rng.uniform(0.15, 0.4))
    p["bit"] = p["bas"] + saat(min(rng.uniform(0.25, 1.5), 0.25 * sla))
    p["kuyruk"] = p["bit"] + dk(rng.uniform(3, 25))
    p["kargoya"] = onay + saat(sla)
    p["teslim"] = p["kargoya"] + saat(rng.uniform(18, 72))


def zaman_sabitle(p, onay, bas, bit, kuyruk=None, kargoya=None):
    p["siparis"] = onay - dk(rng.uniform(5, 40))
    p["onay"], p["bas"], p["bit"] = onay, bas, bit
    p["kuyruk"] = kuyruk or (bit + dk(9))
    p["kargoya"] = kargoya or (p["kuyruk"] + saat(5))
    p["teslim"] = p["kargoya"] + saat(30)


def kalem_sec(zaman):
    adaylar = [u for u in URUNLER if z(u[5]) <= zaman]
    agirlik = [u[6] for u in adaylar]
    n = rng.choices([1, 2, 3], weights=[60, 28, 12])[0]
    secilen, kalemler = set(), []
    while len(kalemler) < n:
        u = rng.choices(adaylar, weights=agirlik)[0]
        vk = f"{u[0]}-{rng.choice(u[4])}"
        if vk in secilen:
            continue
        secilen.add(vk)
        kalemler.append({"vk": vk, "adet": rng.choices([1, 2, 3], weights=[80, 15, 5])[0]})
    return kalemler


def siparis_planla():
    taslak = []
    gun = BASLANGIC
    while gun.date() <= SIMDI.date():
        for _ in range(rng.randint(5, 9)):
            t = gun + timedelta(seconds=rng.randint(8 * 3600, 23 * 3600 + 3540))
            if t <= SIMDI - dk(20):
                taslak.append(t)
        gun += timedelta(days=1)
    taslak.sort()

    planlar = []
    for i, t in enumerate(taslak, 1):
        mk = rng.choices(["MG-CRV-01", "MG-TZG-01", "MG-WEB-01", "MG-KRV-01"], weights=[40, 25, 25, 10])[0]
        firma = {
            "MG-CRV-01": lambda: rng.choices([MENZILO, PAKETRA], weights=[55, 45])[0],
            "MG-TZG-01": lambda: rng.choice([MENZILO, PAKETRA]),
            "MG-WEB-01": lambda: rng.choices([MENZILO, PAKETRA, YOLKUSU], weights=[40, 30, 30])[0],
            "MG-KRV-01": lambda: rng.choices([PAKETRA, YOLKUSU], weights=[70, 30])[0],
        }[mk]()
        depo = rng.choices(["DP-IST", "DP-ANK", "DP-IZM"], weights=[55, 25, 20])[0]
        p = {
            "id": i, "no": f"S26-{i:05d}", "magaza": mk, "musteri": rng.randint(1, 42),
            "depo": depo, "terminal": rng.choice(TERMINALLER[depo]), "firma": firma,
            "siparis": t, "onay": None, "iptal": None, "kalemler": kalem_sec(t),
            "bayrak": set(), "ikinci_hata": None, "yanlis_satir": None,
        }
        p["pzno"] = {"MG-CRV-01": f"CRV{rng.randint(10**8, 10**9 - 1)}",
                     "MG-TZG-01": f"TZ-{rng.randint(10**7, 10**8 - 1)}",
                     "MG-KRV-01": f"KRV-{rng.randint(10**6, 10**7 - 1)}-{rng.randint(1, 9)}",
                     "MG-WEB-01": None}[mk]
        if rng.random() < 0.03:
            p["iptal"] = t + dk(rng.uniform(10, 120))
        else:
            onay = t + dk(rng.uniform(2, 90))
            if onay <= SIMDI:
                zaman_doldur(p, onay)
        planlar.append(p)
    return planlar


planlar = siparis_planla()
kullanilan = set()


def siparis_sec(hedef, kosul=lambda p: True):
    adaylar = [p for p in planlar if p["id"] not in kullanilan and p["onay"] and not p["iptal"] and kosul(p)]
    p = min(adaylar, key=lambda p: abs((p["onay"] - hedef).total_seconds()))
    kullanilan.add(p["id"])
    return p


# ---- Runbook 01: Kargo takip numarası siparişe düşmüyor ----
p = siparis_sec(z("2026-09-29 14:10"))
p.update(magaza="MG-TZG-01", firma=MENZILO, depo="DP-IST", terminal="T-IST-01", pzno="TZ-60418827")
zaman_sabitle(p, z("2026-09-29 14:10"), z("2026-09-29 16:02"), z("2026-09-29 16:31"), z("2026-09-29 16:40"))
p["ikinci_hata"] = z("2026-09-30 10:15")   # kullanıcı "Kargoya Gönder"e tekrar basmış
S1A = p
p = siparis_sec(z("2026-09-30 08:30"))
p.update(magaza="MG-TZG-01", firma=MENZILO, depo="DP-IST", terminal="T-IST-03", pzno="TZ-60431152")
zaman_sabitle(p, z("2026-09-30 08:30"), z("2026-09-30 09:41"), z("2026-09-30 10:04"), z("2026-09-30 10:12"))
S1A2 = p
p = siparis_sec(z("2026-09-30 09:05"), lambda p: p["magaza"] == "MG-CRV-01")
p.update(firma=PAKETRA, depo="DP-IST", terminal="T-IST-02")
zaman_sabitle(p, z("2026-09-30 09:05"), z("2026-09-30 10:31"), z("2026-09-30 11:02"), z("2026-09-30 11:08"))
S1B = p
p = siparis_sec(z("2026-09-29 19:00"), lambda p: p["magaza"] == "MG-KRV-01")   # Paketra'nın son başarılı gönderimi
p.update(firma=PAKETRA, depo="DP-IST", terminal="T-IST-01")
zaman_sabitle(p, z("2026-09-29 19:12"), z("2026-09-30 08:06"), z("2026-09-30 08:27"), z("2026-09-30 08:34"),
              z("2026-09-30 13:40"))
S1B_KARSI = p
p = siparis_sec(z("2026-09-30 10:30"), lambda p: p["magaza"] == "MG-CRV-01")   # Menzilo hâlâ çalışıyor
p.update(firma=MENZILO, depo="DP-IST", terminal="T-IST-03")
zaman_sabitle(p, z("2026-09-30 10:30"), z("2026-09-30 13:18"), z("2026-09-30 13:49"), z("2026-09-30 13:57"),
              z("2026-09-30 18:30"))
S1_MENZILO_KARSI = p
p = siparis_sec(z("2026-09-29 11:20"), lambda p: p["magaza"] == "MG-WEB-01")
p.update(firma=None, depo="DP-IZM", terminal="T-IZM-02")
zaman_sabitle(p, z("2026-09-29 11:20"), z("2026-09-29 13:05"), z("2026-09-29 13:38"))
S1C = p

# ---- Runbook 04: Depo toplama işi tamamlandı ama açık görünüyor ----
p = siparis_sec(z("2026-09-30 09:10"), lambda p: p["magaza"] == "MG-CRV-01")
p.update(depo="DP-ANK", terminal="T-ANK-02", firma=MENZILO)
p["kalemler"] = [{"vk": "TSH-1002-M", "adet": 1}, {"vk": "CRP-6001-STD", "adet": 2}]
zaman_sabitle(p, z("2026-09-30 09:10"), z("2026-09-30 10:38"), z("2026-09-30 11:21"))
S4A = p
p = siparis_sec(z("2026-09-29 12:30"), lambda p: p["magaza"] == "MG-TZG-01")
p.update(depo="DP-IST", terminal="T-IST-02", firma=PAKETRA)
p["kalemler"] = [{"vk": "NVR-5001-CIFT", "adet": 1}, {"vk": "YST-7101-BEYAZ", "adet": 2}]
zaman_sabitle(p, z("2026-09-29 12:30"), z("2026-09-29 15:12"), z("2026-09-29 15:54"))
p["bayrak"].add("toplama_kapanmadi")
S4B = p
p = siparis_sec(z("2026-09-29 17:05"), lambda p: p["magaza"] == "MG-WEB-01")
p.update(depo="DP-IZM", terminal="T-IZM-01", firma=YOLKUSU)
p["kalemler"] = [{"vk": "TSH-1001-M", "adet": 1}, {"vk": "HVL-3001-BEYAZ", "adet": 2}, {"vk": "CRP-6002-STD", "adet": 1}]
zaman_sabitle(p, z("2026-09-29 17:05"), z("2026-09-30 09:14"), z("2026-09-30 09:47"))
p["bayrak"].add("yanlis_barkod")
p["yanlis_satir"] = (1, "HVL-3001-GRI")   # 2 adetlik beyaz havlunun biri gri barkodla okutuldu
S4C = p

# ---- Runbook 05: stok senaryoları için sipariş kalemleri ----
p = siparis_sec(z("2026-09-24 13:00"), lambda p: p["magaza"] == "MG-CRV-01" and p["teslim"] <= SIMDI)
p["kalemler"][0] = {"vk": "HVL-3002-GRI", "adet": 2}
p["bayrak"].add("mukerrer_satis")
S5A = p
p = siparis_sec(z("2026-09-21 16:00"), lambda p: p["magaza"] == "MG-TZG-01" and p["teslim"] <= SIMDI)
p["kalemler"][0] = {"vk": "PJM-4003-M", "adet": 1}
p["bayrak"].add("yanlis_varyant")
S5C = p

# ---- Runbook 02: iade senaryoları için siparişler ----
S2A = siparis_sec(z("2026-09-12 12:00"), lambda p: p["magaza"] == "MG-CRV-01" and p["teslim"] <= z("2026-09-19 00:00"))
S2A["kalemler"] = [{"vk": "SWT-2101-L", "adet": 1}, {"vk": "SWT-2102-M", "adet": 1}]
S2B = siparis_sec(z("2026-09-17 12:00"), lambda p: p["magaza"] == "MG-WEB-01" and p["teslim"] <= z("2026-09-24 00:00"))
S2B["kalemler"] = [{"vk": "PJM-4001-S", "adet": 1}]
S2C = siparis_sec(z("2026-09-08 12:00"), lambda p: p["magaza"] == "MG-KRV-01" and p["teslim"] <= z("2026-09-14 00:00"))
S2C["kalemler"] = [{"vk": "NVR-5001-TEK", "adet": 1}, {"vk": "HVL-3001-MAVI", "adet": 2}]
# Senaryo siparişlerinin zamanı değiştiği için numaralar sipariş tarihine göre yeniden verilir.
planlar.sort(key=lambda p: p["siparis"])
for i, p in enumerate(planlar, 1):
    p["id"], p["no"] = i, f"S26-{i:05d}"
SENARYO_SIPARIS = {S1A["id"], S1A2["id"], S1B["id"], S1C["id"], S4A["id"], S4B["id"], S4C["id"],
                   S5A["id"], S5C["id"], S2A["id"], S2B["id"], S2C["id"]}


def kesik_terminal(p, okutma):
    return p["terminal"] == "T-ANK-02" and okutma >= ANK02_KOPMA


def siparisleri_isle(p):
    """Planı tablolara yazılacak satırlara çevirir."""
    sonuc = {"toplama": None, "satirlar": [], "kuyruk": [], "takip": None, "kargoya": None,
             "teslim": None, "durum": None}
    if p["iptal"]:
        sonuc["durum"] = "IPTAL"
        return sonuc
    if not p["onay"]:
        sonuc["durum"] = "YENI"
        return sonuc

    # Toplama işi
    olus = p["onay"] + dk(5)
    n = len(p["kalemler"])
    hepsi_geldi = p["bit"] <= SIMDI
    for i, k in enumerate(p["kalemler"]):
        okutma = p["bas"] + (p["bit"] - p["bas"]) * (i + 1) / n
        geldi = okutma <= SIMDI and not kesik_terminal(p, okutma)
        okutulan = k["adet"] if geldi else 0
        if geldi and p["yanlis_satir"] and p["yanlis_satir"][0] == i:
            okutulan = k["adet"] - 1
        hepsi_geldi = hepsi_geldi and geldi and okutulan == k["adet"]
        sonuc["satirlar"].append((k, okutulan, okutma if okutulan else None))
    tamam = hepsi_geldi and "toplama_kapanmadi" not in p["bayrak"]
    sonuc["toplama"] = (olus, "TAMAMLANDI" if tamam else "ACIK", p["bit"] if tamam else None)

    # Kargo kuyruğu
    if tamam and p["firma"] and p["kuyruk"] <= SIMDI:
        kt = p["kuyruk"]
        if p["firma"] == PAKETRA and kt >= PAKETRA_KESINTI:
            deneme = 1 + int((SIMDI - kt) / dk(30))
            sonuc["kuyruk"].append(("BEKLIYOR", deneme, "503 Service Unavailable: Paketra servisi yanıt vermiyor, yeniden denenecek",
                                    kt, kt + dk(30) * (deneme - 1)))
        elif p["firma"] == MENZILO and p["magaza"] == "MG-TZG-01" and kt >= TOKEN_BITIS:
            sonuc["kuyruk"].append(("HATA", 5, "HTTP 401 Unauthorized - yetkisiz erişim: erişim anahtarı (token) süresi dolmuş",
                                    kt, kt + dk(20)))
            if p["ikinci_hata"]:
                t2 = p["ikinci_hata"]
                sonuc["kuyruk"].append(("HATA", 5, "HTTP 401 Unauthorized - yetkisiz erişim: erişim anahtarı (token) süresi dolmuş",
                                        t2, t2 + dk(20)))
        else:
            deneme = 2 if rng.random() < 0.05 else 1
            son = kt + (dk(5) if deneme == 2 else timedelta(seconds=rng.randint(4, 40)))
            sonuc["kuyruk"].append(("GONDERILDI", deneme, None, kt, son))
            on = {MENZILO: "MZ", PAKETRA: "PKT", YOLKUSU: "YK"}[p["firma"]]
            sonuc["takip"] = f"{on}{rng.randint(10**9, 10**10 - 1)}"
            if p["kargoya"] <= SIMDI:
                sonuc["kargoya"] = p["kargoya"]
                if p["teslim"] <= SIMDI:
                    sonuc["teslim"] = p["teslim"]

    if sonuc["teslim"]:
        sonuc["durum"] = "TESLIM_EDILDI"
    elif sonuc["kargoya"]:
        sonuc["durum"] = "KARGODA"
    elif sonuc["takip"]:
        sonuc["durum"] = "KARGOYA_HAZIR"
    else:
        sonuc["durum"] = "HAZIRLANIYOR"
    return sonuc


# --------------------------------------------------------------------------------------
# Kampanya ve kuponlar (Runbook 03)
# --------------------------------------------------------------------------------------
KAMPANYALAR = [
    ("Temmuz Kampanyası", "2026-07-01", "2026-07-31", 0),
    ("Yeni Müşteri Hoş Geldin", "2026-07-01", "2026-12-31", 1),
    ("Sadakat Programı", "2026-07-01", "2026-12-31", 1),
    ("Yaz Sonu İndirimi", "2026-08-01", "2026-08-31", 0),
    ("Okula Dönüş", "2026-08-20", "2026-09-15", 0),
    ("Güz Fırsatları", "2026-09-01", "2026-10-31", 1),
    ("Sonbahar Koleksiyonu", "2026-09-10", "2026-10-15", 1),
    ("Hafta Sonu Fırsatı", "2026-09-19", "2026-10-05", 1),
    ("Ev Tekstili Haftası", "2026-09-22", "2026-10-06", 1),
]
KUPONLAR = [
    # kod, kampanya, oran, başlangıç, bitiş, aktif, oluşturma, güncelleme, sipariş anında geçerli olduğu son gün
    ("TEMMUZ10", 1, 0.10, "2026-07-01", "2026-07-31", 0, "2026-06-28 11:20:00", "2026-08-01 09:00:00", "2026-07-31"),
    ("HOSGELDIN15", 2, 0.15, "2026-07-01", "2026-12-31", 1, "2026-06-30 16:05:00", "2026-06-30 16:05:00", "2026-12-31"),
    ("SADIK5", 3, 0.05, "2026-07-01", "2026-12-31", 1, "2026-07-02 10:40:00", "2026-07-02 10:40:00", "2026-12-31"),
    ("YAZ15", 4, 0.15, "2026-08-01", "2026-08-31", 0, "2026-07-29 14:15:00", "2026-09-01 09:00:00", "2026-08-31"),
    ("OKUL20", 5, 0.20, "2026-08-20", "2026-09-15", 1, "2026-08-18 09:55:00", "2026-08-18 09:55:00", "2026-09-15"),
    # S3-A: mükerrer kupon. Eski kayıt aktif kalmış, bitişi geçmiş.
    ("GUZ25", 6, 0.25, "2026-09-01", "2026-09-20", 1, "2026-08-28 15:30:00", "2026-08-28 15:30:00", "2026-09-20"),
    # S3-B: bitiş az önce uzatıldı (GuncellemeZamani), vitrin önbelleği henüz yenilenmedi.
    ("SONBAHAR15", 7, 0.15, "2026-09-10", "2026-10-15", 1, "2026-09-09 10:10:00", "2026-09-30 14:53:00", "2026-09-29"),
    # S3-C: kullanıcı uzattığını sanıyor ama kaydetmemiş, bitiş hâlâ eski.
    ("HAFTASONU20", 8, 0.20, "2026-09-19", "2026-09-28", 1, "2026-09-17 17:45:00", "2026-09-17 17:45:00", "2026-09-28"),
    # S3-A: uzatma işlemi aynı kodla yeni kayıt açmış (4.5 öncesi hata).
    ("GUZ25", 6, 0.25, "2026-09-01", "2026-10-31", 1, "2026-09-19 11:02:00", "2026-09-19 11:02:00", "2026-10-31"),
    ("EVTEKSTIL10", 9, 0.10, "2026-09-22", "2026-10-06", 1, "2026-09-21 13:25:00", "2026-09-21 13:25:00", "2026-10-06"),
]
# SONBAHAR15 (S3-B): bitiş 09-29'dan 10-15'e 14:53'te uzatıldı, vitrin önbelleği 15 dk içinde yenilenecek.
# HAFTASONU20 (S3-C): bitiş 2026-09-28'de kaldı; kampanya 10-05'e uzatılmış ama kupon kaydedilmemiş.


# --------------------------------------------------------------------------------------
# Kullanıcı, rol, yetki ve fiyat talepleri (Runbook 06, bilgi notu 09)
# --------------------------------------------------------------------------------------
ROLLER = ["YONETICI", "MAGAZA_YONETICISI", "KATALOG_UZMANI", "KATEGORI_SORUMLUSU", "FIYAT_ONAYCI",
          "DEPO_SORUMLUSU", "DESTEK"]
YETKILER = [
    ("SIPARIS_GORUNTULE", "Siparişleri görüntüleme"), ("SIPARIS_DUZENLE", "Sipariş düzenleme / kargoya gönderme"),
    ("IADE_YONET", "İade kabul ve kapanış"), ("GERI_ODEME", "Geri ödeme ekranı"),
    ("STOK_GORUNTULE", "Stok bakiye görüntüleme"), ("STOK_HAREKET_GIR", "Stok hareketi girme"),
    ("FIYAT_TALEP_OLUSTUR", "Fiyat talebi oluşturma"), ("FIYAT_ONAYLA", "Fiyat talebi onaylama"),
    ("KUPON_YONET", "Kampanya ve kupon yönetimi"), ("RAPOR_OPERASYON", "Operasyon raporları"),
    ("KULLANICI_YONET", "Kullanıcı ve rol yönetimi"), ("MAGAZA_TANIMLA", "Satış kanalı / mağaza tanımlama"),
    ("DEPO_TOPLAMA", "Toplama işleri ve el terminali"), ("BELGE_SABLONU", "Belge şablonları"),
    ("ONAY_AKISI_TANIMLA", "Onay akışı tanımları"),
]
ROL_YETKI = {
    "YONETICI": [y[0] for y in YETKILER],
    "MAGAZA_YONETICISI": ["SIPARIS_GORUNTULE", "SIPARIS_DUZENLE", "IADE_YONET", "GERI_ODEME", "STOK_GORUNTULE",
                          "FIYAT_ONAYLA", "KUPON_YONET", "RAPOR_OPERASYON", "ONAY_AKISI_TANIMLA"],
    "KATALOG_UZMANI": ["STOK_GORUNTULE", "FIYAT_TALEP_OLUSTUR", "KUPON_YONET"],
    "KATEGORI_SORUMLUSU": ["STOK_GORUNTULE", "FIYAT_TALEP_OLUSTUR", "FIYAT_ONAYLA", "RAPOR_OPERASYON"],
    "FIYAT_ONAYCI": ["FIYAT_ONAYLA", "RAPOR_OPERASYON"],
    "DEPO_SORUMLUSU": ["SIPARIS_GORUNTULE", "IADE_YONET", "STOK_GORUNTULE", "STOK_HAREKET_GIR", "DEPO_TOPLAMA"],
    "DESTEK": ["SIPARIS_GORUNTULE", "STOK_GORUNTULE", "RAPOR_OPERASYON"],
}
KULLANICILAR = [
    # kullanıcı adı, ad soyad, mağaza grubu, aktif, ayrılma, roller
    ("admin.lavanta", "Sistem Yöneticisi", "TUMU", 1, None, ["YONETICI"]),
    ("deniz.kaplanli", "Deniz Kaplanlı", "TUMU", 1, None, ["MAGAZA_YONETICISI", "FIYAT_ONAYCI"]),
    ("murat.ozdemirli", "Murat Özdemirli", "TUMU", 0, "2026-09-05", ["FIYAT_ONAYCI"]),
    ("ozan.cetinkaleli", "Ozan Çetinkaleli", "TUMU", 1, None, ["FIYAT_ONAYCI"]),
    ("selin.yavuzcan", "Selin Yavuzcan", "PAZARYERI", 1, None, ["KATALOG_UZMANI"]),
    ("ece.gurbuzlu", "Ece Gürbüzlü", "WEB", 1, None, ["KATALOG_UZMANI"]),
    ("cem.altinoluklu", "Cem Altınoluklu", "TUMU", 1, None, ["KATEGORI_SORUMLUSU"]),
    ("pelin.sarigollu", "Pelin Sarıgöllü", "TUMU", 1, None, ["KATEGORI_SORUMLUSU"]),
    ("kaan.demirtasli", "Kaan Demirtaşlı", "TUMU", 1, None, ["DEPO_SORUMLUSU"]),
    ("hande.yildirimli", "Hande Yıldırımlı", "TUMU", 1, None, ["DEPO_SORUMLUSU"]),
    ("tolga.erkoclu", "Tolga Erkoçlu", "TUMU", 1, None, ["DEPO_SORUMLUSU"]),
    ("gizem.akdoganli", "Gizem Akdoğanlı", "TUMU", 1, None, ["DESTEK"]),
    ("onur.basarli", "Onur Başarlı", "PAZARYERI", 1, None, ["DESTEK"]),
    ("sinan.kocabeyli", "Sinan Kocabeyli", "PAZARYERI", 0, "2026-03-31", ["KATALOG_UZMANI"]),
    ("irem.tuncali", "İrem Tunçalı", "WEB", 1, None, ["DESTEK", "KATALOG_UZMANI"]),
]
KID = {k[0]: i + 1 for i, k in enumerate(KULLANICILAR)}
MURAT_SON = z("2026-09-04 17:30")


def fiyat_talepleri():
    """Talepleri (oluşturma, akış, açıklama, ürün sayısı, oluşturan, [(adım adı, kullanıcı, durum, zaman)], durum, yayın)"""
    aciklamalar = {
        "TEKSTIL": ["Tişört grubu fiyat güncellemesi", "Sweatshirt sezon fiyatları", "Pijama grubu maliyet zammı",
                    "Pazaryeri komisyon farkı yansıtma", "Giyim kampanya sonrası fiyat dönüşü"],
        "EV_TEKSTILI": ["Havlu grubu fiyat güncellemesi", "Nevresim maliyet artışı", "Ev tekstili kur farkı",
                        "Yastık kılıfı fiyat düzeltmesi"],
        "OUTLET": ["Outlet ürünleri indirim listesi"],
    }
    talepler = []
    gunler = (SIMDI - saat(4) - BASLANGIC).days
    for _ in range(40):
        olus = BASLANGIC + timedelta(days=rng.randint(0, gunler), hours=rng.randint(9, 17), minutes=rng.randint(0, 59))
        if olus > SIMDI - saat(2):
            olus = SIMDI - saat(rng.uniform(2, 5))
        akis = rng.choices(["TEKSTIL", "EV_TEKSTILI", "OUTLET"], weights=[5, 4, 1])[0]
        if akis == "OUTLET" and olus >= z("2026-08-25 00:00"):
            akis = "EV_TEKSTILI"
        urun_sayisi = rng.randint(4, 140)
        olusturan = rng.choice(["selin.yavuzcan", "ece.gurbuzlu", "irem.tuncali"])
        adimlar = [("Kategori Onayı", "cem.altinoluklu" if akis == "TEKSTIL" else "pelin.sarigollu"),
                   ("Finans Onayı", "FINANS")]
        if akis == "OUTLET" or urun_sayisi > 80:
            adimlar.append(("Mağaza Yöneticisi Onayı", "deniz.kaplanli"))
        t, sonuc, durum, yayin = olus, [], "YAYINDA", None
        for adi, kim in adimlar:
            if durum != "YAYINDA":
                sonuc.append((adi, kim if kim != "FINANS" else None, "IPTAL" if durum == "REDDEDILDI" else "SIRADA", None))
                continue
            bitis = t + saat(rng.uniform(2, 30))
            if kim == "FINANS":
                kim = "murat.ozdemirli" if t < MURAT_SON else "ozan.cetinkaleli"
                if kim == "murat.ozdemirli" and bitis > MURAT_SON:
                    bitis = max(t + dk(30), min(bitis, MURAT_SON))
            if bitis > SIMDI:
                sonuc.append((adi, kim, "BEKLIYOR", None))
                durum = "BEKLIYOR"
            elif adi == "Finans Onayı" and rng.random() < 0.06:
                sonuc.append((adi, kim, "REDDEDILDI", bitis))
                durum = "REDDEDILDI"
            else:
                sonuc.append((adi, kim, "ONAYLANDI", bitis))
                t = bitis
        if durum == "YAYINDA":
            yayin = t + dk(10)
        talepler.append([olus, akis, rng.choice(aciklamalar[akis]), urun_sayisi, olusturan, sonuc, durum, yayin, None])

    # S6-A: onaylayıcı pasif (işten ayrılmış), OUTLET akışı güncellenmemiş
    talepler.append([z("2026-09-12 10:20"), "OUTLET", "Outlet ürünleri sezon sonu indirim listesi", 64, "selin.yavuzcan",
                     [("Kategori Onayı", "pelin.sarigollu", "ONAYLANDI", z("2026-09-12 16:45")),
                      ("Finans Onayı", "murat.ozdemirli", "BEKLIYOR", None),
                      ("Mağaza Yöneticisi Onayı", "deniz.kaplanli", "SIRADA", None)], "BEKLIYOR", None, "S6-A"])
    # S6-B: yeni KAMPANYA akışının 3. adımında onaylayıcı tanımlı değil
    talepler.append([z("2026-09-22 11:00"), "KAMPANYA", "Ev Tekstili Haftası kampanya fiyatları", 38, "ece.gurbuzlu",
                     [("Kategori Onayı", "cem.altinoluklu", "ONAYLANDI", z("2026-09-22 15:10")),
                      ("Finans Onayı", "ozan.cetinkaleli", "ONAYLANDI", z("2026-09-23 10:05")),
                      ("Kategori Direktörü Onayı", None, "BEKLIYOR", None)], "BEKLIYOR", None, "S6-B"])
    # S6-C: onaylayıcı aktif, talep listede var ama 30 günden eski (varsayılan filtre dışında)
    talepler.append([z("2026-08-18 14:30"), "TEKSTIL", "Okula dönüş tişört fiyat güncellemesi", 112, "irem.tuncali",
                     [("Kategori Onayı", "cem.altinoluklu", "ONAYLANDI", z("2026-08-19 09:40")),
                      ("Finans Onayı", "murat.ozdemirli", "ONAYLANDI", z("2026-08-20 11:15")),
                      ("Mağaza Yöneticisi Onayı", "deniz.kaplanli", "BEKLIYOR", None)], "BEKLIYOR", None, "S6-C"])
    talepler.sort(key=lambda x: x[0])
    return talepler


# --------------------------------------------------------------------------------------
# Yazma
# --------------------------------------------------------------------------------------
def main():
    if os.path.exists(DB_YOLU):
        os.remove(DB_YOLU)
    con = sqlite3.connect(DB_YOLU)
    con.executescript(SEMA)
    c = con.cursor()

    # --- Tanımlar ---
    c.executemany("INSERT INTO Magaza VALUES (?,?,?,?,?,?,?,?)", [(i + 1, *m) for i, m in enumerate(MAGAZALAR)])
    c.executemany("INSERT INTO KargoFirma VALUES (?,?,?,1)", [(i + 1, *f) for i, f in enumerate(KARGO_FIRMALARI)])
    c.executemany("INSERT INTO Depo VALUES (?,?,?,?)", [(i + 1, *d) for i, d in enumerate(DEPOLAR)])
    for ui, u in enumerate(URUNLER, 1):
        c.execute("INSERT INTO Urun VALUES (?,?,?,?,?,1,?)", (ui, u[0], u[1], u[2], u[3], u[5] + ":00"))
    for vk, (ui, uk, _, barkod) in VARYANT.items():
        c.execute("INSERT INTO UrunVaryant (UrunId, VaryantKodu, VaryantAdi, Barkod) VALUES (?,?,?,?)",
                  (ui, vk, vk.split("-")[-1], barkod))

    isimler = set()
    while len(isimler) < 42:
        isimler.add((rng.choice(ADLAR), rng.choice(SOYADLAR)))
    for mi, (ad, soyad) in enumerate(sorted(isimler), 1):
        eposta = f"{ad}.{soyad}{mi}@ornekposta.test".lower()
        for a, b in zip("çğıöşüİ", "cgiosui"):
            eposta = eposta.replace(a, b)
        kayit = datetime(2025, 1, 1) + timedelta(days=rng.randint(0, 540))
        c.execute("INSERT INTO Musteri VALUES (?,?,?,?,?)", (mi, f"{ad} {soyad}", eposta, rng.choice(SEHIRLER), ts(kayit)))

    for ri, r in enumerate(ROLLER, 1):
        c.execute("INSERT INTO Rol VALUES (?,?)", (ri, r))
    for yi, y in enumerate(YETKILER, 1):
        c.execute("INSERT INTO Yetki VALUES (?,?,?)", (yi, *y))
    yid = {y[0]: i + 1 for i, y in enumerate(YETKILER)}
    for r, ys in ROL_YETKI.items():
        for y in ys:
            c.execute("INSERT INTO RolYetki VALUES (?,?)", (ROLLER.index(r) + 1, yid[y]))
    for ki, k in enumerate(KULLANICILAR, 1):
        c.execute("INSERT INTO Kullanici VALUES (?,?,?,?,?,?,?)",
                  (ki, k[0], k[1], k[0] + "@lavanta-tekstil.test", k[2], k[3], k[4]))
        for r in k[5]:
            c.execute("INSERT INTO KullaniciRol VALUES (?,?)", (ki, ROLLER.index(r) + 1))

    # --- Siparişler ---
    sonuclar = {}
    kalem_id = 0
    kalem_kayit = {}   # (siparis id, sira) -> (kalem id, vk, adet, fiyat)
    toplama_no = 41000
    satis_hareketleri = []   # (zaman, vk, miktar, ref)
    for p in planlar:
        s = siparisleri_isle(p)
        sonuclar[p["id"]] = s
        tutar = 0.0
        for sira, k in enumerate(p["kalemler"], 1):
            ui, uk, fiyat, _ = VARYANT[k["vk"]]
            kalem_id += 1
            kalem_kayit[(p["id"], sira)] = (kalem_id, k["vk"], k["adet"], fiyat)
            tutar += k["adet"] * fiyat
            c.execute("INSERT INTO SiparisKalem VALUES (?,?,?,?,?,?,?,?,?)",
                      (kalem_id, p["id"], sira, ui, uk, k["vk"], k["adet"], fiyat, round(k["adet"] * fiyat, 2)))
            if p["onay"]:
                ref = f"{p['no']}/{sira}"
                vk_kayit = k["vk"]
                if "yanlis_varyant" in p["bayrak"] and sira == 1:
                    vk_kayit = "PJM-4003-L"   # M beden satışı L bedenden düşülmüş
                satis_hareketleri.append((p["onay"], vk_kayit, -k["adet"], ref))
                if "mukerrer_satis" in p["bayrak"] and sira == 1:
                    satis_hareketleri.append((p["onay"] + timedelta(seconds=3), vk_kayit, -k["adet"], ref))
        p["tutar"] = round(tutar, 2)
        c.execute("""INSERT INTO Siparis (SiparisId, SiparisNo, PazaryeriSiparisNo, MagazaId, MusteriId, DepoId,
                     KargoFirmaId, Durum, SiparisTarihi, OnayZamani, KargoTakipNo, KargoyaVermeZamani, TeslimZamani,
                     IptalZamani, IndirimTutari, ToplamTutar) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)""",
                  (p["id"], p["no"], p["pzno"], MAGAZA_ID[p["magaza"]], p["musteri"],
                   DEPO_ID[p["depo"]] if p["onay"] else None, p["firma"], s["durum"], ts(p["siparis"]),
                   ts(p["onay"]), s["takip"], ts(s["kargoya"]), ts(s["teslim"]), ts(p["iptal"]), p["tutar"]))

    # Toplama işleri (oluşturma sırasına göre)
    toplama_sirali = sorted([p for p in planlar if sonuclar[p["id"]]["toplama"]],
                            key=lambda p: sonuclar[p["id"]]["toplama"][0])
    for p in toplama_sirali:
        s = sonuclar[p["id"]]
        olus, durum, tamam = s["toplama"]
        toplama_no += rng.randint(1, 3)
        p["is_no"] = f"TPL-{toplama_no}"
        c.execute("INSERT INTO ToplamaIsi (IsNo, DepoId, SiparisId, TerminalKodu, Durum, OlusturmaZamani, TamamlanmaZamani)"
                  " VALUES (?,?,?,?,?,?,?)",
                  (p["is_no"], DEPO_ID[p["depo"]], p["id"], p["terminal"], durum, ts(olus), ts(tamam)))
        tid = c.lastrowid
        p["toplama_id"] = tid
        for k, okutulan, okutma in s["satirlar"]:
            c.execute("INSERT INTO ToplamaSatir (ToplamaIsiId, UrunKodu, VaryantKodu, Barkod, IstenenAdet, OkutulanAdet,"
                      " OkutmaZamani) VALUES (?,?,?,?,?,?,?)",
                      (tid, VARYANT[k["vk"]][1], k["vk"], VARYANT[k["vk"]][3], k["adet"], okutulan, ts(okutma)))

    # Kargo kuyruğu (oluşturma sırasına göre)
    kuyruk = []
    for p in planlar:
        for kayit in sonuclar[p["id"]]["kuyruk"]:
            kuyruk.append((kayit[3], p["id"], p["firma"], kayit))
    kuyruk.sort(key=lambda x: x[0])
    for _, sid, firma, (durum, deneme, hata, olus, son) in kuyruk:
        c.execute("INSERT INTO KargoKuyruk (SiparisId, KargoFirmaId, Durum, DenemeSayisi, SonHataMesaji, OlusturmaZamani,"
                  " SonDenemeZamani) VALUES (?,?,?,?,?,?,?)", (sid, firma, durum, deneme, hata, ts(olus), ts(son)))

    # --- Terminal senkron kayıtları (son 14 gün) ---
    senkron = []
    okutmalar = {}   # terminal -> [okutma zamanları]
    for p in planlar:
        s = sonuclar[p["id"]]
        for i, (k, _, _) in enumerate(s["satirlar"]):
            okutma = p["bas"] + (p["bit"] - p["bas"]) * (i + 1) / len(s["satirlar"])
            if okutma <= SIMDI:
                okutmalar.setdefault(p["terminal"], []).append(okutma)
    for depo, terminaller in TERMINALLER.items():
        for term in terminaller:
            gun = datetime(SIMDI.year, SIMDI.month, SIMDI.day) - timedelta(days=13)
            ilk_kopuk = True
            while gun <= SIMDI:
                t = gun + saat(8) + dk(rng.randint(0, 40))
                while t.hour < 21 and t <= SIMDI:
                    if term == "T-ANK-02" and t >= ANK02_KOPMA:
                        bekleyen = sum(1 for o in okutmalar.get(term, []) if ANK02_KOPMA <= o <= t)
                        if ilk_kopuk:
                            senkron.append((t, depo, term, "HATA", 0,
                                            "Bağlantı zaman aşımı: terminal sunucuya ulaşamadı (kablosuz ağ)"))
                            ilk_kopuk = False
                        else:
                            senkron.append((t, depo, term, "BEKLIYOR", bekleyen,
                                            "Terminal çevrimdışı; okutmalar cihazda gönderilmeyi bekliyor"))
                    elif rng.random() < 0.015:
                        senkron.append((t, depo, term, "HATA", 0, "Bağlantı koptu, sonraki denemede gönderilecek"))
                    else:
                        senkron.append((t, depo, term, "TAMAMLANDI", rng.randint(2, 36), None))
                    t += dk(rng.randint(50, 110))
                gun += timedelta(days=1)
    # T-ANK-02'nin kopmadan önceki son başarılı gönderimi tam 10:02 olsun
    senkron = [x for x in senkron if not (x[2] == "T-ANK-02" and z("2026-09-30 08:00") <= x[0] < ANK02_KOPMA)]
    senkron.append((z("2026-09-30 08:24"), "DP-ANK", "T-ANK-02", "TAMAMLANDI", 11, None))
    senkron.append((z("2026-09-30 10:02"), "DP-ANK", "T-ANK-02", "TAMAMLANDI", 7, None))
    # S4-C: yanlış barkod uyarısı, okutmadan hemen sonraki senkronda
    senkron = [x for x in senkron if not (x[2] == "T-IZM-01" and z("2026-09-30 09:40") <= x[0] <= z("2026-09-30 10:30"))]
    senkron.append((z("2026-09-30 09:52"), "DP-IZM", "T-IZM-01", "TAMAMLANDI", 9,
                    f"1 okutma eşleşmedi: barkod {VARYANT['HVL-3001-GRI'][3]} ({S4C['is_no']}) iş satırlarında yok"))
    senkron.sort(key=lambda x: x[0])
    for t, depo, term, durum, sayi, hata in senkron:
        c.execute("INSERT INTO TerminalSenkron (DepoId, TerminalKodu, Durum, KayitSayisi, GonderimZamani, HataMesaji)"
                  " VALUES (?,?,?,?,?,?)", (DEPO_ID[depo], term, durum, sayi, ts(t), hata))

    # --- İadeler (Runbook 02) ---
    nedenler = ["Beden uymadı", "Ürün hasarlı geldi", "Vazgeçtim", "Renk görseldekinden farklı", "Yanlış ürün gönderildi"]
    korunan_vk = {"HVL-3002-GRI", "PJM-4003-L", "PJM-4003-M", "SWT-2105-M"}
    iadeler = []   # (olusturma, siparis plan, neden, kalemler[(sira, iade adet, kabul)], varis, kapanis, senaryo)
    for p in planlar:
        s = sonuclar[p["id"]]
        if p["id"] in SENARYO_SIPARIS or s["durum"] != "TESLIM_EDILDI" or rng.random() >= 0.09:
            continue
        olus = s["teslim"] + saat(rng.uniform(20, 200))
        if olus > SIMDI - saat(2):
            continue
        sec = [i for i, k in enumerate(p["kalemler"], 1) if k["vk"] not in korunan_vk]
        if not sec:
            continue
        sec = sorted(rng.sample(sec, rng.randint(1, len(sec))))
        varis = olus + saat(rng.uniform(24, 96))
        kabul = varis + saat(rng.uniform(1, 20))
        kapanis = kabul + saat(rng.uniform(0.5, 30))
        kalemler = [(sira, rng.randint(1, p["kalemler"][sira - 1]["adet"]), kabul) for sira in sec]
        iadeler.append((olus, p, rng.choice(nedenler), kalemler, varis, kapanis, None))
    # S2-A: depo paketi teslim almış, ikinci kalemin kabulü girilmemiş
    t = sonuclar[S2A["id"]]["teslim"]
    iadeler.append((t + saat(44), S2A, "Beden uymadı",
                    [(1, 1, z("2026-09-24 15:32")), (2, 1, None)], z("2026-09-24 11:05"), None, "S2-A"))
    # S2-B: 1 adet satılmış, iade adedi 3 girilmiş
    t = sonuclar[S2B["id"]]["teslim"]
    iadeler.append((t + saat(30), S2B, "Vazgeçtim",
                    [(1, 3, z("2026-09-29 14:20"))], z("2026-09-29 10:10"), None, "S2-B"))
    # S2-C: Kervanpazar mağazasında "iade kargo ücretini müşteriden kes" açık
    t = sonuclar[S2C["id"]]["teslim"]
    iadeler.append((t + saat(50), S2C, "Ürün hasarlı geldi",
                    [(1, 1, z("2026-09-18 16:05")), (2, 2, z("2026-09-18 16:05"))], z("2026-09-18 10:40"),
                    z("2026-09-19 10:12"), "S2-C"))
    iadeler.sort(key=lambda x: x[0])
    iade_hareketleri = []
    for no, (olus, p, neden, kalemler, varis, kapanis, sen) in enumerate(iadeler, 1):
        iade_no = f"IAD-2026-{no + 140:05d}"
        kes = KRV_KESINTI if p["magaza"] == "MG-KRV-01" else 0.0
        kabul_olan = [(sira, adet, kabul) for sira, adet, kabul in kalemler if kabul and kabul <= SIMDI]
        varis_k = varis if varis <= SIMDI else None
        if kapanis and kapanis <= SIMDI and len(kabul_olan) == len(kalemler):
            durum, kap = "KAPANDI", kapanis
        else:
            durum, kap = "ACIK", None
        if kabul_olan:
            geri = round(sum(adet * kalem_kayit[(p["id"], sira)][3] for sira, adet, _ in kabul_olan) - kes, 2)
        else:
            geri = None
        c.execute("INSERT INTO Iade (IadeNo, SiparisId, Durum, IadeNedeni, OlusturmaZamani, IadeKargoTeslimZamani,"
                  " KapanisZamani, KargoKesintiTutari, GeriOdemeTutari) VALUES (?,?,?,?,?,?,?,?,?)",
                  (iade_no, p["id"], durum, neden, ts(olus), ts(varis_k), ts(kap), kes, geri))
        iid = c.lastrowid
        if sen:
            log(sen, f"IadeNo={iade_no} IadeId={iid} SiparisNo={p['no']} Durum={durum} GeriOdeme={geri}")
        for ks, (sira, adet, kabul) in enumerate(kalemler, 1):
            kid, vk, _, _ = kalem_kayit[(p["id"], sira)]
            kabul_k = kabul if kabul and kabul <= SIMDI else None
            c.execute("INSERT INTO IadeKalem (IadeId, SiraNo, SiparisKalemId, UrunKodu, VaryantKodu, IadeAdet,"
                      " TeslimAlmaZamani, Durum) VALUES (?,?,?,?,?,?,?,?)",
                      (iid, ks, kid, VARYANT[vk][1], vk, adet, ts(kabul_k), "KABUL_EDILDI" if kabul_k else "BEKLIYOR"))
            if kabul_k:
                iade_hareketleri.append((kabul_k, vk, adet, f"{iade_no}/{ks}"))

    # --- Kuponlar (Runbook 03) ---
    for ki, k in enumerate(KAMPANYALAR, 1):
        c.execute("INSERT INTO Kampanya VALUES (?,?,?,?,?)", (ki, *k))
    for kid_, k in enumerate(KUPONLAR, 1):
        c.execute("INSERT INTO Kupon VALUES (?,?,?,?,?,?,?,?,?)", (kid_, k[0], k[1], k[2], k[3], k[4], k[5], k[6], k[7]))
    for p in planlar:
        if p["magaza"] != "MG-WEB-01" or not p["onay"] or rng.random() >= 0.35:
            continue
        gun = p["siparis"].strftime("%Y-%m-%d")
        gecerli = [(i, k) for i, k in enumerate(KUPONLAR, 1)
                   if k[3] <= gun <= k[8] and k[6] <= ts(p["siparis"])]
        if gun > "2026-09-20":   # doğrulama eski GUZ25 kaydını bulduğu için çoğu müşteride çalışmıyor
            gecerli = [(i, k) for i, k in gecerli if not (k[0] == "GUZ25" and rng.random() < 0.6)]
        if not gecerli:
            continue
        guz = [x for x in gecerli if x[1][0] == "GUZ25"]
        i, k = rng.choice(guz) if guz and rng.random() < 0.5 else rng.choice(gecerli)
        indirim = round(p["tutar"] * k[2], 2)
        c.execute("INSERT INTO KuponKullanim (KuponId, SiparisId, IndirimTutari, KullanimZamani) VALUES (?,?,?,?)",
                  (i, p["id"], indirim, ts(p["siparis"])))
        c.execute("UPDATE Siparis SET IndirimTutari = ?, ToplamTutar = ? WHERE SiparisId = ?",
                  (indirim, round(p["tutar"] - indirim, 2), p["id"]))

    # --- Stok (Runbook 05) ---
    hedef_bakiye = {"HVL-3002-GRI": 1, "PJM-4003-L": 0}   # anomali öncesi bakiye
    mal_kabul_yok = {"SWT-2105-M"}
    hareketler = [(t, vk, m, "SATIS", ref) for t, vk, m, ref in satis_hareketleri]
    hareketler += [(t, vk, m, "IADE_GIRIS", ref) for t, vk, m, ref in iade_hareketleri]
    mk1, mk2, mk3 = z("2026-06-20 09:30"), z("2026-08-14 10:15"), z("2026-09-16 10:20")
    for vk in VARYANT:
        olaylar = [h for h in hareketler if h[1] == vk]
        satis_gercek = -sum(h[2] for h in olaylar if h[3] == "SATIS")
        iade = sum(h[2] for h in olaylar if h[3] == "IADE_GIRIS")
        if vk in hedef_bakiye:   # anomali hareketlerini çıkarıp hesapla
            if vk == "HVL-3002-GRI":
                satis_gercek -= 2
            if vk == "PJM-4003-L":
                satis_gercek -= 1
        if vk.startswith("SWT-2105"):
            if vk not in mal_kabul_yok:
                hareketler.append((mk3, vk, satis_gercek + rng.randint(8, 20), "MAL_KABUL", "MKB-2026-0058"))
            continue
        if vk in hedef_bakiye:   # tek mal kabul; anomali öncesi bakiye tam hedefte kalır
            hareketler.append((mk1, vk, hedef_bakiye[vk] + satis_gercek - iade, "MAL_KABUL", "MKB-2026-0031"))
            continue
        erken = -sum(h[2] for h in olaylar if h[3] == "SATIS" and h[0] < mk2)
        r1 = erken + rng.randint(5, 25)
        hedef = rng.randint(6, 45)
        r2 = hedef - (r1 - satis_gercek + iade)
        hareketler.append((mk1, vk, r1, "MAL_KABUL", "MKB-2026-0031"))
        if r2 > 0:
            hareketler.append((mk2, vk, r2, "MAL_KABUL", "MKB-2026-0047"))
    hareketler.sort(key=lambda h: (h[0], h[4]))
    for t, vk, m, tip, ref in hareketler:
        c.execute("INSERT INTO StokHareket (UrunId, VaryantKodu, HareketTipi, Miktar, HareketTarihi, KaynakReferans)"
                  " VALUES (?,?,?,?,?,?)", (VARYANT[vk][0], vk, tip, m, ts(t), ref))
    c.execute("""INSERT INTO StokBakiye (UrunId, VaryantKodu, Bakiye, SonHareketZamani)
                 SELECT v.UrunId, v.VaryantKodu, COALESCE(SUM(sh.Miktar), 0), MAX(sh.HareketTarihi)
                 FROM UrunVaryant v LEFT JOIN StokHareket sh ON sh.VaryantKodu = v.VaryantKodu
                 GROUP BY v.UrunId, v.VaryantKodu""")

    # --- Fiyat talepleri (Runbook 06) ---
    for no, (olus, akis, aciklama, urun_sayisi, olusturan, adimlar, durum, yayin, sen) in enumerate(fiyat_talepleri(), 1):
        talep_no = f"FT-2026-{no + 100:04d}"
        c.execute("INSERT INTO FiyatTalep (TalepNo, AkisKodu, Aciklama, UrunSayisi, OlusturanKullaniciId, Durum,"
                  " OlusturmaZamani, YayinZamani) VALUES (?,?,?,?,?,?,?,?)",
                  (talep_no, akis, aciklama, urun_sayisi, KID[olusturan], durum, ts(olus), ts(yayin)))
        fid = c.lastrowid
        if sen:
            log(sen, f"TalepNo={talep_no} FiyatTalepId={fid}")
        for sira, (adi, kim, adurum, zaman) in enumerate(adimlar, 1):
            c.execute("INSERT INTO FiyatOnayAdim (FiyatTalepId, AdimSira, AdimAdi, AtananKullaniciId, AdimDurum,"
                      " IslemZamani) VALUES (?,?,?,?,?,?)", (fid, sira, adi, KID.get(kim), adurum, ts(zaman)))

    con.commit()

    # --- Senaryo kayıtlarının özeti ---
    for kod, p in [("S1-A", S1A), ("S1-A", S1A2), ("S1-B", S1B), ("S1-B (karşılaştırma)", S1B_KARSI),
                   ("S1 (Menzilo karşılaştırma)", S1_MENZILO_KARSI), ("S1-C", S1C),
                   ("S4-A", S4A), ("S4-B", S4B), ("S4-C", S4C), ("S5-A", S5A), ("S5-C", S5C)]:
        log(kod, f"SiparisNo={p['no']} SiparisId={p['id']} Magaza={p['magaza']} Durum={sonuclar[p['id']]['durum']}"
                 f" IsNo={p.get('is_no')} Depo={p['depo']} Terminal={p['terminal']}")
    print("Tablolar:")
    for (ad,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        print(f"  {ad:<16} {con.execute(f'SELECT COUNT(*) FROM {ad}').fetchone()[0]:>6}")
    print("\nSenaryo kayıtları:")
    for satir in senaryo_log:
        print("  " + satir)
    con.close()
    print(f"\nOluşturuldu: {DB_YOLU}")


if __name__ == "__main__":
    main()
