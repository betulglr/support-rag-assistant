"""araclar.py içindeki teşhis araçlarını SENARYOLAR.md'deki senaryolarla dener.

Çalıştırma:  python db/test_araclar.py      (önce: python db/create_db.py)

Her senaryo için ilgili araçlar senaryo parametreleriyle çalıştırılır ve sonuçların, cevap
anahtarındaki beklenen nedeni gösteren kanıtı içerip içermediği kontrol edilir. Kanıt seviyeleri:

  DOGRUDAN  Nedeni gösteren veri araç çıktısında açıkça görünüyor (ör. 401 hatası, boş kabul zamanı).
  ELEME     Nedenin kendisi araçlarla görünmüyor. Runbook'un kuralına göre diğer nedenler
            elendiği için bu nedene varılıyor.
  YOK       Araç çıktısı beklenen nedeni göstermiyor.
  KULLANICIYA_SOR
            Neden veritabanında tutulmuyor, teşhis edilemez. Araçlar yalnızca diğer nedenleri
            eler; agent kullanıcıya soru sormalıdır (ör. hangi filtreyi kullandığı).

Her senaryo için beklenen bir kanıt seviyesi tanımlıdır. Bulunan seviye beklenenden farklıysa
test başarısız sayılır ve çıkış kodu 1 olur.

Ayrıca şunlar kontrol edilir:
- Araçların SQL'i, sorgular_sqlite.md'deki salt okuma sorgularıyla birebir aynı mı (:Ad yerine ?).
- Her salt okuma sorgusunun bir aracı var mı, veri değiştiren hiçbir sorgu araç olmuş mu.
- Bağlantı gerçekten salt okunur mu.
- SIMDI sabiti araclar.py ve create_db.py'de aynı mı.
- iade_tutar_ozeti ve stok_varyant_uyusmazligi ilgisiz senaryolarda yanlış alarm veriyor mu.
"""
import inspect
import re
import sqlite3
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
sys.stdout.reconfigure(errors="replace")

import araclar  # noqa: E402
from araclar import ARACLAR, SIMDI  # noqa: E402

BUGUN = SIMDI[:10]
hatalar = []


def saat_farki(once, sonra):
    from datetime import datetime
    return (datetime.fromisoformat(sonra) - datetime.fromisoformat(once)).total_seconds() / 3600


# ---------------------------------------------------------------------------------------
# 1) Yapısal kontroller
# ---------------------------------------------------------------------------------------
def normalize(sql):
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r":[A-Za-z]\w*", "?", sql)
    return " ".join(sql.replace(";", " ").split())


def yapisal_kontroller():
    print("=" * 78)
    print("YAPISAL KONTROLLER")
    print("=" * 78)

    # SIMDI aynı mı
    m = re.search(r'SIMDI_METIN\s*=\s*"([^"]+)"', (KOK / "db" / "create_db.py").read_text(encoding="utf-8"))
    ayni = bool(m) and m.group(1) == SIMDI
    print(f"SIMDI araclar.py = create_db.py ({SIMDI}): {'EVET' if ayni else 'HAYIR'}")
    if not ayni:
        hatalar.append("SIMDI sabitleri farklı")

    # md'deki sorgular
    md = (KOK / "db" / "sorgular_sqlite.md").read_text(encoding="utf-8")
    bloklar = re.findall(r"```sql\n(.*?)```", md, re.S)
    gercek_saat = re.compile(r"'now'|localtime|GETDATE|SYSDATETIME|CURRENT_(DATE|TIME)", re.I)
    if any(gercek_saat.search(b) for b in bloklar) or gercek_saat.search(inspect.getsource(araclar)):
        hatalar.append("SQL'de gerçek saat kullanımı var")
        print("SQL bloklarında / araclar.py'de gerçek saat: VAR")
    else:
        print("SQL bloklarında / araclar.py'de gerçek saat (date('now') vb.): YOK")
    yazan = re.compile(r"\b(UPDATE|DELETE|INSERT)\b", re.I)
    okuma = [normalize(b) for b in bloklar if not yazan.search(b)]
    yazma_sayisi = len(bloklar) - len(okuma)

    # araçların SQL'ini yakala (veritabanına gitmeden)
    yakalanan = {}
    asil = araclar._calistir
    ornek = {"siparis_no": "x", "iade_no": "x", "kupon_kodu": "x", "depo_kodu": "x", "is_no": "x",
             "urun_kodu": "x", "varyant_kodu": "x", "talep_no": "x", "magaza_kodu": "x",
             "baslangic": "x", "bitis": "x", "satici_id": "x", "kullanici_adi": "x"}
    try:
        for ad, fn in ARACLAR.items():
            araclar._calistir = lambda sql, params=(), ad=ad: yakalanan.__setitem__(ad, (sql, params)) or {}
            argnames = fn.__code__.co_varnames[:fn.__code__.co_argcount]
            fn(**{a: ornek[a] for a in argnames})
    finally:
        araclar._calistir = asil

    eslesmeyen_arac = []
    for ad, (sql, params) in yakalanan.items():
        n = normalize(sql)
        if yazan.search(sql):
            hatalar.append(f"{ad} veri değiştiren SQL içeriyor")
        if n not in okuma:
            eslesmeyen_arac.append(ad)
        if n.count("?") != len(params):
            hatalar.append(f"{ad}: ? sayısı ({n.count('?')}) parametre sayısıyla ({len(params)}) uyuşmuyor")
    aracsiz = [i for i, o in enumerate(okuma) if o not in {normalize(s) for s, _ in yakalanan.values()}]
    print(f"sorgular_sqlite.md: {len(bloklar)} SQL bloğu = {len(okuma)} salt okuma + {yazma_sayisi} veri değiştiren")
    print(f"Araç sayısı: {len(ARACLAR)}")
    print(f"SQL'i md'deki bir okuma sorgusuyla birebir aynı olan araç: {len(ARACLAR) - len(eslesmeyen_arac)}/{len(ARACLAR)}")
    print(f"Aracı olmayan salt okuma sorgusu: {len(aracsiz)}")
    if eslesmeyen_arac:
        hatalar.append(f"md ile eşleşmeyen araçlar: {eslesmeyen_arac}")
    if aracsiz:
        hatalar.append(f"aracı olmayan okuma sorgusu sayısı: {len(aracsiz)}")

    # salt okunur bağlantı
    con = sqlite3.connect(araclar.DB_YOLU.as_uri() + "?mode=ro", uri=True)
    try:
        con.execute("UPDATE Kupon SET Aktif = Aktif")
        print("Salt okunur bağlantı: HAYIR (yazma başarılı oldu)")
        hatalar.append("bağlantı salt okunur değil")
    except sqlite3.OperationalError as e:
        print(f"Salt okunur bağlantı: EVET (yazma denemesi reddedildi: {e})")
    finally:
        con.close()


# ---------------------------------------------------------------------------------------
# 2) Senaryolar
# ---------------------------------------------------------------------------------------
def bekleyen_adim(sonuc):
    return [s for s in sonuc["satirlar"] if s["AdimDurum"] == "BEKLIYOR"]


def k_S1A(r):
    sayilar = []
    for sonuc in r:
        hatali = [s for s in sonuc["satirlar"] if s["Durum"] == "HATA"
                  and ("401" in (s["SonHataMesaji"] or "") or "yetkisiz" in (s["SonHataMesaji"] or "").lower())]
        if not hatali:
            return "YOK", "401/yetkisiz içeren HATA kaydı olmayan sipariş var"
        sayilar.append(len(hatali))
    return "DOGRUDAN", f"iki siparişte {sayilar} HATA kaydı, mesaj: '{hatali[0]['SonHataMesaji'][:60]}...'"


def k_S1B(r):
    bekleyen = [s for s in r[0]["satirlar"] if s["Durum"] == "BEKLIYOR"]
    if not bekleyen:
        return "YOK", "BEKLIYOR kaydı yok"
    firma = bekleyen[0]["FirmaAdi"]
    son = {s["FirmaAdi"]: s["SonBasariliYanit"] for s in r[1]["satirlar"]}
    fark = saat_farki(son[firma], SIMDI)
    digerleri = {f: round(saat_farki(t, SIMDI), 1) for f, t in son.items() if f != firma}
    if fark >= 2 and all(v < 2 for v in digerleri.values()):
        return "DOGRUDAN", f"kayıt BEKLIYOR; {firma} son başarılı yanıt {son[firma]} ({fark:.1f} saat önce), diğerleri {digerleri} saat önce"
    return "YOK", f"{firma} son yanıt {fark:.1f} saat önce"


def k_S1C(r):
    if r[0]["toplam"] == 0:
        return "DOGRUDAN", "siparişe ait kuyruk kaydı yok (runbook: kargo firması seçilmeden onaylanmış)"
    return "YOK", f"{r[0]['toplam']} kuyruk kaydı var"


def k_S2A(r):
    bos = [s for s in r[0]["satirlar"] if s["TeslimAlmaZamani"] is None]
    if bos:
        return "DOGRUDAN", f"{len(bos)} kalemde TeslimAlmaZamani boş (IadeKalemId {[s['IadeKalemId'] for s in bos]})"
    return "YOK", "boş kabul zamanı yok"


def k_S2B(r):
    fazla = [s for s in r[0]["satirlar"] if s["IadeAdet"] > s["SatisAdet"]]
    if fazla:
        return "DOGRUDAN", f"IadeAdet {fazla[0]['IadeAdet']} > SatisAdet {fazla[0]['SatisAdet']} ({fazla[0]['UrunKodu']})"
    return "YOK", "IadeAdet > SatisAdet olan kalem yok"


def k_S2C(r):
    kalemler = r[0]["satirlar"]
    tutarli = kalemler and all(x["TeslimAlmaZamani"] and x["IadeAdet"] <= x["SatisAdet"] for x in kalemler)
    o = r[1]["satirlar"][0] if r[1]["satirlar"] else None
    if tutarli and o and o["IadeKargoUcretiKes"] == 1 \
            and abs(o["GeriOdemeTutari"] - (o["KalemToplami"] - o["KargoKesintiTutari"])) < 0.005:
        return "DOGRUDAN", (f"kalemler tutarlı; {o['MagazaKodu']} IadeKargoUcretiKes=1, geri ödeme {o['GeriOdemeTutari']}"
                            f" = kalem toplamı {o['KalemToplami']} - kesinti {o['KargoKesintiTutari']}")
    return "YOK", "kesinti ayarı açık + tutar = toplam - kesinti görülmedi"


def k_S3A(r):
    s = r[0]["satirlar"]
    eski = [x for x in s[1:] if x["Aktif"] == 1 and x["BitisTarihi"] < BUGUN]
    if len(s) >= 2 and eski:
        return "DOGRUDAN", f"{len(s)} kayıt; eski KuponId {eski[0]['KuponId']} Aktif=1, bitiş {eski[0]['BitisTarihi']} < {BUGUN}"
    return "YOK", f"{len(s)} kayıt, süresi dolmuş aktif eski kayıt yok"


def k_S3B(r):
    s = r[0]["satirlar"]
    if len(s) == 1 and s[0]["BitisTarihi"] >= BUGUN:
        return "DOGRUDAN", f"tek kayıt, bitiş {s[0]['BitisTarihi']} >= {BUGUN} (doğru; runbook: önbellek)"
    return "YOK", "tek ve doğru tarihli kayıt değil"


def k_S3C(r):
    s = r[0]["satirlar"]
    if len(s) == 1 and s[0]["BitisTarihi"] < BUGUN:
        return "DOGRUDAN", f"tek kayıt, bitiş hâlâ {s[0]['BitisTarihi']} < {BUGUN} (uzatma kaydedilmemiş)"
    return "YOK", "tek ve eski tarihli kayıt değil"


def k_S4A(r):
    satir = r[0]["satirlar"]
    hic_gelmemis = satir and all(x["OkutulanAdet"] == 0 for x in satir)
    sorunlu = [x for x in r[1]["satirlar"] if x["Durum"] in ("BEKLIYOR", "HATA") and x["GonderimZamani"][:10] == BUGUN]
    if hic_gelmemis and sorunlu:
        t = sorunlu[0]
        return "DOGRUDAN", f"satırlarda hiç okutma yok; {t['TerminalKodu']} son senkron {t['Durum']} ({t['GonderimZamani']})"
    return "YOK", "okutma yok + senkron BEKLIYOR/HATA birlikte görülmedi"


def k_S4B(r):
    satir = r[0]["satirlar"]
    if satir and all(x["OkutulanAdet"] == x["IstenenAdet"] for x in satir) and satir[0]["IsDurum"] == "ACIK":
        return "DOGRUDAN", f"{len(satir)} satırın hepsi tam okutulmuş ama IsDurum ACIK"
    return "YOK", "tam okutulmuş + ACIK değil"


def k_S4C(r, is_no="TPL-42289"):
    eksik = [x for x in r[0]["satirlar"] if x["OkutulanAdet"] < x["IstenenAdet"]]
    uyari = [x for x in r[1]["satirlar"] if x["HataMesaji"] and "eşleşmedi" in x["HataMesaji"] and is_no in x["HataMesaji"]]
    if eksik and uyari:
        return "DOGRUDAN", f"{eksik[0]['UrunKodu']} {eksik[0]['OkutulanAdet']}/{eksik[0]['IstenenAdet']}; senkron: '{uyari[0]['HataMesaji']}'"
    if eksik:
        return "ELEME", "eksik satır var ama yanlış barkod uyarısı bulunamadı"
    return "YOK", "eksik satır yok"


def k_S5A(r):
    if r[0]["toplam"]:
        m = r[0]["satirlar"][0]
        return "DOGRUDAN", f"mükerrer: {m['KaynakReferans']} {m['VaryantKodu']} Miktar {m['Miktar']} x{m['Adet']}"
    return "YOK", "mükerrer hareket yok"


def k_S5B(r):
    h = r[0]
    tam = h["toplam"] <= len(h["satirlar"])
    mal_kabul = [x for x in h["satirlar"] if x["HareketTipi"] == "MAL_KABUL"]
    if tam and not mal_kabul and r[1]["toplam"] == 0:
        return "DOGRUDAN", f"{h['toplam']} hareketin tamamı SATIS, hiç MAL_KABUL yok; mükerrer yok"
    return "YOK", "mal kabul var ya da hareketlerin tamamı görülemedi"


def k_S5C(r):
    u = [x for x in r[2]["satirlar"] if x["DusulenVaryant"] == "PJM-4003-L"]
    if r[1]["toplam"] == 0 and u:
        x = u[0]
        return "DOGRUDAN", (f"mükerrer yok; {x['KaynakReferans']} satışı {x['DusulenVaryant']}'den düşülmüş, "
                            f"sipariş kalemi {x['SiparisVaryant']} (HareketId {x['HareketId']})")
    return "YOK", "varyant uyuşmazlığı bulunamadı"


def k_S6A(r):
    b = bekleyen_adim(r[0])
    if b and b[0]["KullaniciAdi"] and b[0]["OnaylayiciAktif"] == 0:
        return "DOGRUDAN", f"BEKLIYOR adım {b[0]['AdimSira']}: {b[0]['KullaniciAdi']} pasif (Aktif=0)"
    return "YOK", "bekleyen adımda pasif onaylayıcı yok"


def k_S6B(r):
    b = bekleyen_adim(r[0])
    if b and b[0]["KullaniciAdi"] is None:
        return "DOGRUDAN", f"BEKLIYOR adım {b[0]['AdimSira']}: atanmış kullanıcı yok"
    return "YOK", "bekleyen adımda boş onaylayıcı yok"


def k_S6C(r):
    b = bekleyen_adim(r[0])
    if b and b[0]["KullaniciAdi"] and b[0]["OnaylayiciAktif"] == 1:
        return "KULLANICIYA_SOR", (f"BEKLIYOR adım {b[0]['AdimSira']}: {b[0]['KullaniciAdi']} aktif, akış sağlam; "
                                   "filtre veritabanında yok, agent kullanıcıya hangi filtreyi kullandığını sormalı")
    return "YOK", "bekleyen adımda aktif onaylayıcı yok (veritabanında başka bir neden görünüyor)"


SENARYOLAR = [
    # kod, beklenen neden, araç çağrıları, kanıt fonksiyonu, beklenen kanıt seviyesi
    ("S1-A", "Kargo firmasının erişim anahtarı süresi dolmuş",
     [("kargo_kuyrugu_siparis", {"siparis_no": "S26-00655"}),
      ("kargo_kuyrugu_siparis", {"siparis_no": "S26-00659"})], k_S1A, "DOGRUDAN"),
    ("S1-B", "Kargo firmasının servisinde geçici kesinti",
     [("kargo_kuyrugu_siparis", {"siparis_no": "S26-00660"}), ("kargo_firma_son_basarili_yanit", {})], k_S1B, "DOGRUDAN"),
    ("S1-C", "Siparişte kargo firması seçilmemiş",
     [("kargo_kuyrugu_siparis", {"siparis_no": "S26-00653"})], k_S1C, "DOGRUDAN"),
    ("S2-A", "Depo paketi teslim almış, kabulü sisteme girmemiş",
     [("iade_kalemleri", {"iade_no": "IAD-2026-00177"})], k_S2A, "DOGRUDAN"),
    ("S2-B", "İade adedi satılan adetten fazla girilmiş",
     [("iade_kalemleri", {"iade_no": "IAD-2026-00180"})], k_S2B, "DOGRUDAN"),
    ("S2-C", "'İade kargo ücretini müşteriden kes' ayarı açık",
     [("iade_kalemleri", {"iade_no": "IAD-2026-00176"}),
      ("iade_tutar_ozeti", {"iade_no": "IAD-2026-00176"})], k_S2C, "DOGRUDAN"),
    ("S3-A", "Uzatma aynı kodla yeni kupon açmış, eski kayıt aktif",
     [("kupon_kayitlari", {"kupon_kodu": "GUZ25"})], k_S3A, "DOGRUDAN"),
    ("S3-B", "Vitrin önbelleği yenilenmemiş",
     [("kupon_kayitlari", {"kupon_kodu": "SONBAHAR15"})], k_S3B, "DOGRUDAN"),
    ("S3-C", "Kullanıcı uzatmayı yapmış ama kaydetmemiş",
     [("kupon_kayitlari", {"kupon_kodu": "HAFTASONU20"})], k_S3C, "DOGRUDAN"),
    ("S4-A", "El terminali ağdan düşmüş, okutmalar cihazda",
     [("toplama_isi_satirlari", {"depo_kodu": "DP-ANK", "is_no": "TPL-42301"}),
      ("terminal_senkron_kayitlari", {"depo_kodu": "DP-ANK"})], k_S4A, "DOGRUDAN"),
    ("S4-B", "Okutmalar gelmiş ama iş otomatik kapanmamış",
     [("toplama_isi_satirlari", {"depo_kodu": "DP-IST", "is_no": "TPL-42285"})], k_S4B, "DOGRUDAN"),
    ("S4-C", "Ürün yanlış barkodla okutulmuş, satır eksik",
     [("toplama_isi_satirlari", {"depo_kodu": "DP-IZM", "is_no": "TPL-42289"}),
      ("terminal_senkron_kayitlari", {"depo_kodu": "DP-IZM"})], k_S4C, "DOGRUDAN"),
    ("S5-A", "Pazaryeri bildirimi iki kez işlenmiş (mükerrer satış)",
     [("stok_mukerrer_hareketler", {"urun_kodu": "HVL-3002"}),
      ("stok_hareketleri", {"urun_kodu": "HVL-3002", "varyant_kodu": "HVL-3002-GRI"})], k_S5A, "DOGRUDAN"),
    ("S5-B", "Mal kabul kaydı hiç girilmemiş",
     [("stok_hareketleri", {"urun_kodu": "SWT-2105", "varyant_kodu": "SWT-2105-M"}),
      ("stok_mukerrer_hareketler", {"urun_kodu": "SWT-2105"})], k_S5B, "DOGRUDAN"),
    ("S5-C", "Satış yanlış varyanttan düşülmüş",
     [("stok_hareketleri", {"urun_kodu": "PJM-4003", "varyant_kodu": "PJM-4003-L"}),
      ("stok_mukerrer_hareketler", {"urun_kodu": "PJM-4003"}),
      ("stok_varyant_uyusmazligi", {"urun_kodu": "PJM-4003"})], k_S5C, "DOGRUDAN"),
    ("S6-A", "Onaylayıcı kullanıcı pasife alınmış / ayrılmış",
     [("fiyat_talebi_onay_adimlari", {"talep_no": "FT-2026-0133"})], k_S6A, "DOGRUDAN"),
    ("S6-B", "O adımda onaylayıcı tanımlı değil",
     [("fiyat_talebi_onay_adimlari", {"talep_no": "FT-2026-0139"})], k_S6B, "DOGRUDAN"),
    ("S6-C", "Onaylayıcı yanlış filtre kullanıyor, talep listede var",
     [("fiyat_talebi_onay_adimlari", {"talep_no": "FT-2026-0120"})], k_S6C, "KULLANICIYA_SOR"),
]

BILGI_NOTLARI = [
    ("07", "kargoya_verme_suresi", {"magaza_kodu": "MG-CRV-01", "baslangic": "2026-09-01 00:00:00", "bitis": "2026-09-30 23:59:59"}),
    ("08", "magaza_satici_id", {"satici_id": "418230"}),
    ("09", "kullanici_rol_yetkileri", {"kullanici_adi": "deniz.kaplanli"}),
]


def satir_yaz(s, en_fazla=6):
    for x in s["satirlar"][:en_fazla]:
        print("      " + ", ".join(f"{k}={v}" for k, v in x.items()))
    if s["toplam"] > en_fazla:
        print(f"      ... (toplam {s['toplam']} satır, araç en fazla 20 döndürür)")


def senaryolari_calistir():
    print("\n" + "=" * 78)
    print(f"SENARYOLAR (SIMDI = {SIMDI})")
    print("=" * 78)
    sonuc_tablosu = []
    for kod, neden, cagrilar, kanit, beklenen in SENARYOLAR:
        print(f"\n[{kod}] Beklenen neden: {neden}")
        sonuclar = []
        for ad, kw in cagrilar:
            s = ARACLAR[ad](**kw)
            sonuclar.append(s)
            print(f"  > {ad}({', '.join(f'{k}={v!r}' for k, v in kw.items())}) -> toplam {s['toplam']}")
            satir_yaz(s)
        seviye, aciklama = kanit(sonuclar)
        durum = "OK" if seviye == beklenen else f"BEKLENMEYEN (beklenen {beklenen})"
        print(f"  KANIT: {seviye} - {aciklama}")
        print(f"  SONUÇ: {durum}")
        if seviye != beklenen:
            hatalar.append(f"{kod}: kanıt {seviye}, beklenen {beklenen}")
        sonuc_tablosu.append((kod, seviye, durum))

    print("\n" + "=" * 78)
    print("BİLGİ NOTU ARAÇLARI (senaryo yok, yalnızca çalıştığı kontrol edilir)")
    print("=" * 78)
    for no, ad, kw in BILGI_NOTLARI:
        s = ARACLAR[ad](**kw)
        print(f"  [{no}] {ad} -> toplam {s['toplam']}, dönen {len(s['satirlar'])}")
        if s["toplam"] == 0:
            hatalar.append(f"bilgi notu {no}: {ad} boş döndü")
    return sonuc_tablosu


def ayirt_edicilik():
    """Yeni araçlar başka senaryolarda yanlış alarm veriyor mu?"""
    print("\n" + "=" * 78)
    print("AYIRT EDİCİLİK (yeni araçlar ilgisiz senaryolarda sinyal vermemeli)")
    print("=" * 78)
    for urun in ("HVL-3002", "SWT-2105", "TSH-1001", "NVR-5001"):
        n = ARACLAR["stok_varyant_uyusmazligi"](urun_kodu=urun)["toplam"]
        print(f"  stok_varyant_uyusmazligi({urun}) -> {n}  {'OK' if n == 0 else 'YANLIŞ ALARM'}")
        if n:
            hatalar.append(f"stok_varyant_uyusmazligi {urun} için {n} satır döndü")
    for iade in ("IAD-2026-00177", "IAD-2026-00180"):
        o = ARACLAR["iade_tutar_ozeti"](iade_no=iade)["satirlar"][0]
        ok = o["IadeKargoUcretiKes"] == 0
        print(f"  iade_tutar_ozeti({iade}) -> IadeKargoUcretiKes={o['IadeKargoUcretiKes']}  {'OK' if ok else 'YANLIŞ ALARM'}")
        if not ok:
            hatalar.append(f"iade_tutar_ozeti {iade}: kesinti ayarı açık görünüyor")


def main():
    if not araclar.DB_YOLU.exists():
        sys.exit(f"{araclar.DB_YOLU} yok. Önce: python db/create_db.py")
    yapisal_kontroller()
    tablo = senaryolari_calistir()
    ayirt_edicilik()

    print("\n" + "=" * 78)
    print("ÖZET")
    print("=" * 78)
    print(f"{'Senaryo':<9}{'Kanıt':<17}Durum")
    print(f"{'-------':<9}{'-----':<17}-----")
    for kod, seviye, durum in tablo:
        print(f"{kod:<9}{seviye:<17}{durum}")
    for seviye in ("DOGRUDAN", "ELEME", "KULLANICIYA_SOR", "YOK"):
        print(f"{seviye:<16}: {sum(1 for _, s, _ in tablo if s == seviye)}/{len(tablo)}")
    if hatalar:
        print("\nBAŞARISIZ:")
        for h in hatalar:
            print("  - " + h)
        sys.exit(1)
    print("\nTüm kontroller beklendiği gibi.")


if __name__ == "__main__":
    main()
