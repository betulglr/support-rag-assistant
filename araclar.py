"""Siparion destek teşhis araçları (salt okunur).

db/sorgular_sqlite.md içindeki SADECE OKUMA sorgularının her biri burada ayrı bir fonksiyondur.
Veri değiştiren scriptler (UPDATE / DELETE / INSERT) bilerek araç yapılmadı. Onlar yalnızca
geliştirici onayıyla, elle çalıştırılır.

- Veritabanı salt okunur açılır (mode=ro). Bir araç yazmaya çalışsa bile SQLite hata verir.
- Parametreler her zaman ? yer tutucularıyla verilir, SQL metnine eklenmez.
- Sonuç formatı: {"toplam": <satır sayısı>, "satirlar": [en fazla 20 satır, her biri sözlük]}
- Zaman: veritabanının "şu an"ı sabit SIMDI'dir. Gerçek saat hiçbir yerde kullanılmaz.

Veritabanı yoksa önce:  python db/create_db.py
"""
import sqlite3
from pathlib import Path

SIMDI = "2026-09-30 15:00:00"
DB_YOLU = Path(__file__).resolve().parent / "db" / "siparion.db"
EN_FAZLA_SATIR = 20


def _calistir(sql, params=()):
    if not DB_YOLU.exists():
        raise FileNotFoundError(f"{DB_YOLU} bulunamadı. Önce 'python db/create_db.py' çalıştırın.")
    con = sqlite3.connect(DB_YOLU.as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        satirlar = con.execute(sql, params).fetchall()
    finally:
        con.close()
    return {"toplam": len(satirlar), "satirlar": [dict(s) for s in satirlar[:EN_FAZLA_SATIR]]}


# ---------------------------------------------------------------------------------------
# 01 — Kargo takip numarası siparişe düşmüyor
# ---------------------------------------------------------------------------------------
def kargo_kuyrugu_siparis(siparis_no):
    """Bir siparişin kargo entegrasyon kuyruğu kayıtlarını listeler.

    Ne zaman: Runbook 01 (kargo takip numarası siparişe düşmüyor), kontrol adımı 2. Siparişte
    takip numarası boşsa, sipariş "Hazırlanıyor"da kalmışsa veya pazaryerine "kargoya verildi"
    bildirimi gitmemişse ilk bakılacak araç. Depo toplama işi için değil, kargo firmasına gönderim
    için kullanılır.

    Parametreler:
        siparis_no: Siparion sipariş numarası, ör. "S26-00655". Pazaryeri sipariş numarası değil.

    Döndürür: Kuyruk kayıtları, en yenisi önce. Kolonlar: KuyrukId, Durum (BEKLIYOR / GONDERILDI /
    HATA), DenemeSayisi, SonHataMesaji, OlusturmaZamani, SonDenemeZamani, FirmaAdi.
    Okuma: HATA ve mesajda "401"/"yetkisiz" varsa erişim anahtarı süresi dolmuş. BEKLIYOR ise
    kargo_firma_son_basarili_yanit ile firma kesintisine bakın. 0 satır dönerse siparişte kargo
    firması seçilmemiş. HATA satır sayısı, yeniden kuyruğa alma scriptindeki @BeklenenSayi olur.
    """
    return _calistir("""
        SELECT kk.KuyrukId, kk.Durum, kk.DenemeSayisi, kk.SonHataMesaji,
               kk.OlusturmaZamani, kk.SonDenemeZamani, kf.FirmaAdi
        FROM KargoKuyruk kk
        JOIN Siparis s ON s.SiparisId = kk.SiparisId
        JOIN KargoFirma kf ON kf.KargoFirmaId = kk.KargoFirmaId
        WHERE s.SiparisNo = ?
        ORDER BY kk.OlusturmaZamani DESC""", (siparis_no,))


def kargo_firma_son_basarili_yanit():
    """Her kargo firmasından en son ne zaman başarılı yanıt alındığını gösterir.

    Ne zaman: Runbook 01, kontrol adımı 3. kargo_kuyrugu_siparis bir kaydı BEKLIYOR gösterdiğinde,
    sorunun tek siparişte mi yoksa firmanın tamamında mı olduğunu ayırmak için. Birden çok sipariş
    aynı anda takip numarası alamıyorsa da kullanılır.

    Parametreler: yok.

    Döndürür: Firma başına bir satır. Kolonlar: FirmaAdi, SonBasariliYanit (son GONDERILDI kaydının
    zamanı). Okuma: Bir firmanın son başarılı yanıtı SIMDI'den (2026-09-30 15:00) saatler önceyse ve
    diğer firmalar güncelse, o firmanın servisinde kesinti vardır.
    """
    return _calistir("""
        SELECT kf.FirmaAdi, MAX(kk.SonDenemeZamani) AS SonBasariliYanit
        FROM KargoKuyruk kk
        JOIN KargoFirma kf ON kf.KargoFirmaId = kk.KargoFirmaId
        WHERE kk.Durum = 'GONDERILDI'
        GROUP BY kf.FirmaAdi""")


# ---------------------------------------------------------------------------------------
# 02 — İade kaydı kapanmıyor / iade tutarı yanlış
# ---------------------------------------------------------------------------------------
def iade_kalemleri(iade_no):
    """Bir iade kaydının kalemlerini depo kabul bilgisi ve satış adediyle birlikte listeler.

    Ne zaman: Runbook 02 (iade kapanmıyor / geri ödeme tutarı yanlış), kontrol adımı 2. "İadeyi
    Tamamla" uyarı veriyorsa, geri ödeme boş, eksik veya fazla çıkıyorsa. Stoğa dönüş hareketleri
    için değil, iade kaydının kendisi için kullanılır.

    Parametreler:
        iade_no: İade numarası, ör. "IAD-2026-00177".

    Döndürür: Kalemler, SiraNo sırasıyla. Kolonlar: IadeKalemId, SiraNo, UrunKodu, IadeAdet,
    SatisAdet, TeslimAlmaZamani (depo kabul), Durum (BEKLIYOR / KABUL_EDILDI).
    Okuma: TeslimAlmaZamani boş kalem varsa depo kabulü girilmemiş, iade bu yüzden kapanmıyor.
    IadeAdet > SatisAdet ise adet hatalı girilmiş. Tüm satırlar dolu ve tutarlıysa tutar farkını
    iade_tutar_ozeti ile kontrol edin.
    """
    return _calistir("""
        SELECT ik.IadeKalemId, ik.SiraNo, ik.UrunKodu,
               ik.IadeAdet, sk.Adet AS SatisAdet,
               ik.TeslimAlmaZamani, ik.Durum
        FROM IadeKalem ik
        JOIN Iade i ON i.IadeId = ik.IadeId
        JOIN SiparisKalem sk ON sk.SiparisKalemId = ik.SiparisKalemId
        WHERE i.IadeNo = ?
        ORDER BY ik.SiraNo""", (iade_no,))


def iade_tutar_ozeti(iade_no):
    """Bir iadenin geri ödeme tutarını, kalem toplamını ve mağazanın iade kargo kesintisi ayarını gösterir.

    Ne zaman: Runbook 02, kontrol adımı 3. Müşteri geri ödemenin eksik olduğunu söylüyorsa ve
    iade_kalemleri tüm kalemleri kabul edilmiş, adetleri tutarlı gösteriyorsa. Farkın mağazanın
    "İade kargo ücretini müşteriden kes" ayarından mı yoksa açıklanamayan bir hatadan mı geldiğini
    ayırır. Kabul edilmemiş kalem veya hatalı adet için önce iade_kalemleri kullanılır.

    Parametreler:
        iade_no: İade numarası, ör. "IAD-2026-00176".

    Döndürür: Tek satır. Kolonlar: IadeNo, Durum, MagazaKodu, IadeKargoUcretiKes (1 = ayar açık),
    KalemToplami (tüm iade kalemlerinin IadeAdet × BirimFiyat toplamı), KargoKesintiTutari,
    GeriOdemeTutari.
    Okuma: IadeKargoUcretiKes = 1 ve GeriOdemeTutari = KalemToplami - KargoKesintiTutari ise tutar
    doğrudur, fark kesinti ayarından gelir. IadeKargoUcretiKes = 0 ve GeriOdemeTutari = KalemToplami
    ise tutar doğrudur. İkisi de tutmuyorsa açıklanamayan fark vardır, geliştiriciye iletilir.
    """
    return _calistir("""
        SELECT i.IadeNo, i.Durum, m.MagazaKodu, m.IadeKargoUcretiKes,
               ROUND(SUM(ik.IadeAdet * sk.BirimFiyat), 2) AS KalemToplami,
               i.KargoKesintiTutari, i.GeriOdemeTutari
        FROM Iade i
        JOIN Siparis s ON s.SiparisId = i.SiparisId
        JOIN Magaza m ON m.MagazaId = s.MagazaId
        JOIN IadeKalem ik ON ik.IadeId = i.IadeId
        JOIN SiparisKalem sk ON sk.SiparisKalemId = ik.SiparisKalemId
        WHERE i.IadeNo = ?
        GROUP BY i.IadeNo, i.Durum, m.MagazaKodu, m.IadeKargoUcretiKes,
                 i.KargoKesintiTutari, i.GeriOdemeTutari""", (iade_no,))


# ---------------------------------------------------------------------------------------
# 03 — Kampanya kuponu süresi dolmuş görünüyor
# ---------------------------------------------------------------------------------------
def kupon_kayitlari(kupon_kodu):
    """Bir kupon koduna ait tüm kupon kayıtlarını kampanya adıyla listeler.

    Ne zaman: Runbook 03 (kupon süresi dolmuş görünüyor ama uzatılmış), kontrol adımı 2. Sepette
    "Kupon geçersiz veya süresi doldu" hatası alınıyorsa, kod bazı müşterilerde çalışıp bazılarında
    çalışmıyorsa ya da bitiş tarihi uzatıldığı halde kod reddediliyorsa.

    Parametreler:
        kupon_kodu: Müşterinin sepete girdiği kod, ör. "GUZ25". Büyük/küçük harf duyarlı.

    Döndürür: Kayıtlar, en yeni oluşturulan önce. Kolonlar: KuponId, KuponKodu, BaslangicTarihi,
    BitisTarihi, Aktif, OlusturmaZamani, KampanyaAdi.
    Okuma (bugün = SIMDI'nin tarihi, 2026-09-30): Aynı kod için iki satır varsa ve eskisi Aktif=1,
    bitişi geçmişse kupon mükerrerdir. Tek satır var ve bitiş ileri tarihliyse vitrin önbelleği
    yenilenmemiştir (15 dk). Tek satır var ve bitiş geçmişse uzatma kaydedilmemiştir.
    """
    return _calistir("""
        SELECT ku.KuponId, ku.KuponKodu, ku.BaslangicTarihi, ku.BitisTarihi,
               ku.Aktif, ku.OlusturmaZamani, ka.KampanyaAdi
        FROM Kupon ku
        JOIN Kampanya ka ON ka.KampanyaId = ku.KampanyaId
        WHERE ku.KuponKodu = ?
        ORDER BY ku.OlusturmaZamani DESC""", (kupon_kodu,))


# ---------------------------------------------------------------------------------------
# 04 — Depo toplama işi tamamlandı ama açık görünüyor
# ---------------------------------------------------------------------------------------
def toplama_isi_satirlari(depo_kodu, is_no):
    """Bir depo toplama işinin durumunu ve ürün satırlarındaki okutma adetlerini gösterir.

    Ne zaman: Runbook 04 (toplama işi tamamlandı ama açık görünüyor), kontrol adımı 2. Depo personeli
    ürünleri el terminaliyle okutup paketlediğini söylüyor ama iş panelde "Toplanıyor"/"Açık"
    görünüyorsa veya sipariş paketlemeye geçmiyorsa. Kargo takip numarası sorunları için değildir.

    Parametreler:
        depo_kodu: Depo kodu, ör. "DP-IST", "DP-ANK", "DP-IZM".
        is_no: Toplama işi numarası, ör. "TPL-42285".

    Döndürür: İşin satırları, UrunKodu sırasıyla. Kolonlar: ToplamaIsiId, IsNo, IsDurum
    (ACIK / TAMAMLANDI), UrunKodu, IstenenAdet, OkutulanAdet, OkutmaZamani.
    Okuma: Tüm satırlarda OkutulanAdet = IstenenAdet ama IsDurum ACIK ise iş otomatik kapanmamıştır.
    Bazı satırlarda OkutulanAdet < IstenenAdet ise eksik veya yanlış barkodla okutma vardır.
    Okutmaların hiç gelmediği durumu ayırmak için terminal_senkron_kayitlari'na bakın.
    """
    return _calistir("""
        SELECT ti.ToplamaIsiId, ti.IsNo, ti.Durum AS IsDurum,
               ts.UrunKodu, ts.IstenenAdet, ts.OkutulanAdet, ts.OkutmaZamani
        FROM ToplamaIsi ti
        JOIN ToplamaSatir ts ON ts.ToplamaIsiId = ti.ToplamaIsiId
        JOIN Depo d ON d.DepoId = ti.DepoId
        WHERE d.DepoKodu = ?
          AND ti.IsNo = ?
        ORDER BY ts.UrunKodu""", (depo_kodu, is_no))


def terminal_senkron_kayitlari(depo_kodu):
    """Bir depodaki el terminallerinin merkeze gönderim (senkron) kayıtlarını, en yenisi önce listeler.

    Ne zaman: Runbook 04, kontrol adımı 3. Okutmalar panele hiç gelmemişse, el terminali kablosuz
    ağdan düşmüş olabilirse veya senkron sırasında yanlış barkod uyarısı aranıyorsa. Kargo firması
    entegrasyonu için değil, depo el terminalleri için kullanılır.

    Parametreler:
        depo_kodu: Depo kodu, ör. "DP-ANK".

    Döndürür: En yeni 20 senkron kaydı (toplam alanında tüm kayıt sayısı). Kolonlar: TerminalKodu,
    Durum (TAMAMLANDI / BEKLIYOR / HATA), KayitSayisi, GonderimZamani, HataMesaji.
    Okuma: Bir terminalin son kayıtları BEKLIYOR/HATA ise okutmalar cihazda kalmıştır. TAMAMLANDI
    olup HataMesaji'nda "eşleşmedi: barkod ..." geçiyorsa bir ürün yanlış barkodla okutulmuştur.
    """
    return _calistir("""
        SELECT tsn.TerminalKodu, tsn.Durum, tsn.KayitSayisi,
               tsn.GonderimZamani, tsn.HataMesaji
        FROM TerminalSenkron tsn
        JOIN Depo d ON d.DepoId = tsn.DepoId
        WHERE d.DepoKodu = ?
        ORDER BY tsn.GonderimZamani DESC""", (depo_kodu,))


# ---------------------------------------------------------------------------------------
# 05 — Ürün stoğu negatif çıkıyor
# ---------------------------------------------------------------------------------------
def stok_hareketleri(urun_kodu, varyant_kodu):
    """Bir ürün varyantının stok hareketlerini (mal kabul, satış, iade girişi) en yenisi önce listeler.

    Ne zaman: Runbook 05 (ürün stoğu negatif), kontrol adımı 2. Bir varyantın bakiyesi eksiye
    düştüyse veya raftaki adetle sistem uyuşmuyorsa. Mal kabul hiç girilmemiş mi, sıralama mı bozuk,
    hangi satış referansları düşülmüş, bunları görmek için kullanılır.

    Parametreler:
        urun_kodu: Ürün kodu, ör. "HVL-3002".
        varyant_kodu: Tam varyant kodu, ör. "HVL-3002-GRI" (ürün kodu + beden/renk).

    Döndürür: En yeni 20 hareket (toplam alanında tüm hareket sayısı). Kolonlar: HareketId,
    VaryantKodu, HareketTipi (MAL_KABUL / SATIS / IADE_GIRIS), Miktar (giriş +, çıkış -),
    HareketTarihi, KaynakReferans (satışta "SiparisNo/SiraNo").
    Okuma: Hiç MAL_KABUL yoksa mal kabul girilmemiştir. Mükerrer kayıt için stok_mukerrer_hareketler
    daha doğrudan sonuç verir.
    """
    return _calistir("""
        SELECT sh.HareketId, sh.VaryantKodu, sh.HareketTipi, sh.Miktar,
               sh.HareketTarihi, sh.KaynakReferans
        FROM StokHareket sh
        JOIN Urun u ON u.UrunId = sh.UrunId
        WHERE u.UrunKodu = ?
          AND sh.VaryantKodu = ?
        ORDER BY sh.HareketTarihi DESC""", (urun_kodu, varyant_kodu))


def stok_mukerrer_hareketler(urun_kodu):
    """Bir ürünün tüm varyantlarında aynı referans + aynı miktarla birden çok kez işlenmiş hareketleri bulur.

    Ne zaman: Runbook 05, kontrol adımı 3. Stok negatifse ve aynı pazaryeri sipariş bildiriminin
    iki kez işlendiğinden (mükerrer satış düşümü) şüpheleniliyorsa.

    Parametreler:
        urun_kodu: Ürün kodu, ör. "HVL-3002". Varyant verilmez, ürünün tüm varyantları taranır.

    Döndürür: Mükerrer gruplar. Kolonlar: KaynakReferans, VaryantKodu, Miktar, Adet (tekrar sayısı).
    Okuma: Satır dönerse mükerrer düşüm var. Adet - 1, silme scriptindeki @BeklenenSayi'dir.
    0 satır dönerse mükerrer yoktur. Diğer nedenler için stok_hareketleri ve
    stok_varyant_uyusmazligi'na bakın.
    """
    return _calistir("""
        SELECT sh.KaynakReferans, sh.VaryantKodu, sh.Miktar, COUNT(*) AS Adet
        FROM StokHareket sh
        JOIN Urun u ON u.UrunId = sh.UrunId
        WHERE u.UrunKodu = ?
        GROUP BY sh.KaynakReferans, sh.VaryantKodu, sh.Miktar
        HAVING COUNT(*) > 1""", (urun_kodu,))


def stok_varyant_uyusmazligi(urun_kodu):
    """Bir üründe, siparişteki bedenden/varyanttan farklı bir varyanttan düşülmüş satış hareketlerini bulur.

    Ne zaman: Runbook 05, kontrol adımı 4. Bir beden eksi görünürken aynı ürünün başka bir bedeni
    raftakinden fazla görünüyorsa (beden karışıklığı) ya da stok negatif olup mükerrer hareket ve
    eksik mal kabul bulunamadıysa.

    Parametreler:
        urun_kodu: Ürün kodu, ör. "PJM-4003". Varyant verilmez, ürünün tüm satışları taranır.

    Döndürür: Yalnızca varyantı uyuşmayan satışlar, en yenisi önce. Kolonlar: HareketId,
    HareketTarihi, KaynakReferans ("SiparisNo/SiraNo"), Miktar, DusulenVaryant (stoktan düşülen),
    SiparisVaryant (sipariş kalemindeki doğru varyant).
    Okuma: Satır dönerse beden karışıklığı vardır. DusulenVaryant eksiye düşer, SiparisVaryant
    fazla görünür. Hareketin varyantı SiparisVaryant olarak düzeltilmelidir. 0 satır dönerse bu
    neden yoktur.
    """
    return _calistir("""
        SELECT sh.HareketId, sh.HareketTarihi, sh.KaynakReferans, sh.Miktar,
               sh.VaryantKodu AS DusulenVaryant,
               sk.VaryantKodu AS SiparisVaryant
        FROM StokHareket sh
        JOIN Urun u ON u.UrunId = sh.UrunId
        JOIN SiparisKalem sk ON sk.UrunId = sh.UrunId
        JOIN Siparis s ON s.SiparisId = sk.SiparisId
        WHERE u.UrunKodu = ?
          AND sh.HareketTipi = 'SATIS'
          AND sh.KaynakReferans = s.SiparisNo || '/' || CAST(sk.SiraNo AS TEXT)
          AND sh.VaryantKodu <> sk.VaryantKodu
        ORDER BY sh.HareketTarihi DESC""", (urun_kodu,))


# ---------------------------------------------------------------------------------------
# 06 — Toplu fiyat değişikliği talebi onay akışında takılı
# ---------------------------------------------------------------------------------------
def fiyat_talebi_onay_adimlari(talep_no):
    """Bir toplu fiyat değişikliği talebinin onay adımlarını ve her adıma atanan kullanıcıyı gösterir.

    Ne zaman: Runbook 06 (fiyat talebi onay akışında takılı), kontrol adımı 2. Talep "Onay bekliyor"da
    kalmışsa, yeni fiyatlar yayına girmiyorsa veya onaylayıcı talebi listesinde göremiyorsa.
    Kullanıcının genel ekran yetkileri için değil, belirli bir talebin akışı için kullanılır.

    Parametreler:
        talep_no: Fiyat talebi numarası, ör. "FT-2026-0133".

    Döndürür: Adımlar, AdimSira sırasıyla. Kolonlar: TalepNo, Durum (talebin durumu), AdimSira,
    AdimDurum (SIRADA / BEKLIYOR / ONAYLANDI / REDDEDILDI / IPTAL), KullaniciAdi, OnaylayiciAktif.
    Okuma: Yalnızca AdimDurum = BEKLIYOR olan adıma bakın. KullaniciAdi boşsa o adımda onaylayıcı
    tanımlı değildir. OnaylayiciAktif = 0 ise onaylayıcı pasiftir. Onaylayıcı aktifse talep listede
    vardır ve kullanıcının filtresine bakılmalıdır.
    """
    return _calistir("""
        SELECT ft.TalepNo, ft.Durum, oa.AdimSira, oa.AdimDurum,
               k.KullaniciAdi, k.Aktif AS OnaylayiciAktif
        FROM FiyatTalep ft
        JOIN FiyatOnayAdim oa ON oa.FiyatTalepId = ft.FiyatTalepId
        LEFT JOIN Kullanici k ON k.KullaniciId = oa.AtananKullaniciId
        WHERE ft.TalepNo = ?
        ORDER BY oa.AdimSira""", (talep_no,))


# ---------------------------------------------------------------------------------------
# Bilgi notları 07–09
# ---------------------------------------------------------------------------------------
def kargoya_verme_suresi(magaza_kodu, baslangic, bitis):
    """Bir mağazanın siparişlerinde onaydan kargoya verilene kadar geçen saati (SLA) listeler.

    Ne zaman: Bilgi notu 07 (kargoya verme süresi / SLA raporu). Geciken gönderiler, 48 saat kuralını
    aşan siparişler veya pazaryeri sevk süresi denetimi soruluyorsa. Tek bir siparişin takip
    numarası sorunu için kargo_kuyrugu_siparis kullanılır.

    Parametreler:
        magaza_kodu: Mağaza kodu, ör. "MG-CRV-01".
        baslangic: Onay zamanı alt sınırı, "YYYY-MM-DD HH:MM:SS", ör. "2026-09-01 00:00:00".
        bitis: Onay zamanı üst sınırı, ör. "2026-09-30 23:59:59". Gün sonunu saatle birlikte verin,
            yoksa son günün siparişleri dışarıda kalır.

    Döndürür: En uzun süreli 20 sipariş (toplam alanında tüm sipariş sayısı). Kolonlar: SiparisNo,
    OnayZamani, KargoyaVermeZamani, GecenSaat (SQL Server DATEDIFF(hour) ile aynı hesap). GecenSaat
    48'den büyükse SLA ihlalidir. KargoyaVermeZamani boşsa (raporda "Veri Yok") GecenSaat de boştur.
    """
    return _calistir("""
        SELECT s.SiparisNo, s.OnayZamani, s.KargoyaVermeZamani,
               (CAST(strftime('%s', strftime('%Y-%m-%d %H:00:00', s.KargoyaVermeZamani)) AS INTEGER)
                - CAST(strftime('%s', strftime('%Y-%m-%d %H:00:00', s.OnayZamani)) AS INTEGER)) / 3600 AS GecenSaat
        FROM Siparis s
        JOIN Magaza m ON m.MagazaId = s.MagazaId
        WHERE m.MagazaKodu = ?
          AND s.OnayZamani BETWEEN ? AND ?
        ORDER BY GecenSaat DESC""", (magaza_kodu, baslangic, bitis))


def magaza_satici_id(satici_id):
    """Verilen pazaryeri satıcı ID'si ile tanımlı mağaza kartı olup olmadığını gösterir.

    Ne zaman: Bilgi notu 08 (yeni pazaryeri mağazası bağlama). Yeni mağaza kaydedilirken "satıcı ID
    zaten kayıtlı" hatası alınıyorsa veya eklenen mağaza listede görünmüyorsa.

    Parametreler:
        satici_id: Pazaryerinin verdiği satıcı ID'si (metin), ör. "418230".

    Döndürür: Eşleşen mağazalar. Kolonlar: MagazaId, MagazaAdi, PazaryeriKodu, SaticiId, Aktif.
    Satır dönerse bu satıcı ID zaten bir mağazada kullanılıyordur. Aktif = 0 ise mağaza pasiftir ve
    "Aktif" filtresinde görünmez.
    """
    return _calistir("""
        SELECT MagazaId, MagazaAdi, PazaryeriKodu, SaticiId, Aktif
        FROM Magaza
        WHERE SaticiId = ?""", (satici_id,))


def kullanici_rol_yetkileri(kullanici_adi):
    """Bir kullanıcının rollerini ve bu rollerden gelen yetki kodlarını listeler.

    Ne zaman: Bilgi notu 09 (kullanıcı yetkisi / rol). Bir kullanıcı bir ekranı veya menüyü
    göremiyorsa ya da hangi yetkilere sahip olduğu soruluyorsa. Fiyat onay akışında atanan
    onaylayıcıyı bulmak için değil, kullanıcının genel yetkileri için kullanılır.

    Parametreler:
        kullanici_adi: Giriş kullanıcı adı, ör. "deniz.kaplanli".

    Döndürür: Rol ve yetki çiftleri, RolAdi ve YetkiKodu sırasıyla. Kolonlar: KullaniciAdi, RolAdi,
    YetkiKodu. 0 satır dönerse kullanıcı yoktur veya hiç rolü yoktur. Kullanıcının pasif olup
    olmadığını bu araç göstermez.
    """
    return _calistir("""
        SELECT k.KullaniciAdi, r.RolAdi, y.YetkiKodu
        FROM Kullanici k
        JOIN KullaniciRol kr ON kr.KullaniciId = k.KullaniciId
        JOIN Rol r ON r.RolId = kr.RolId
        JOIN RolYetki ry ON ry.RolId = r.RolId
        JOIN Yetki y ON y.YetkiId = ry.YetkiId
        WHERE k.KullaniciAdi = ?
        ORDER BY r.RolAdi, y.YetkiKodu""", (kullanici_adi,))


ARACLAR = {
    "kargo_kuyrugu_siparis": kargo_kuyrugu_siparis,
    "kargo_firma_son_basarili_yanit": kargo_firma_son_basarili_yanit,
    "iade_kalemleri": iade_kalemleri,
    "iade_tutar_ozeti": iade_tutar_ozeti,
    "kupon_kayitlari": kupon_kayitlari,
    "toplama_isi_satirlari": toplama_isi_satirlari,
    "terminal_senkron_kayitlari": terminal_senkron_kayitlari,
    "stok_hareketleri": stok_hareketleri,
    "stok_mukerrer_hareketler": stok_mukerrer_hareketler,
    "stok_varyant_uyusmazligi": stok_varyant_uyusmazligi,
    "fiyat_talebi_onay_adimlari": fiyat_talebi_onay_adimlari,
    "kargoya_verme_suresi": kargoya_verme_suresi,
    "magaza_satici_id": magaza_satici_id,
    "kullanici_rol_yetkileri": kullanici_rol_yetkileri,
}
