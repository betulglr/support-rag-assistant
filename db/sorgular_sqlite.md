# Runbook sorgularının SQLite karşılıkları

Runbook'lardaki SQL'ler SQL Server (T-SQL) sözdizimindedir. Runbook dosyaları değiştirilmedi.
Burada her sorgunun `db/siparion.db` üzerinde çalışan SQLite karşılığı var.

## Yapılan dönüşümler

```
SQL Server                          SQLite
---------------------------------   -----------------------------------------------------------
dbo.Tablo                           Tablo  (şema öneki yok)
@Parametre                          :Parametre  (Python: con.execute(sql, {"Parametre": ...}))
DATEDIFF(hour, a, b)                saat sınırı farkı; aşağıdaki 07-1 sorgusuna bakın
GETDATE() / CAST(... AS date)       date(:Simdi)   (sabit SIMDI, aşağıya bakın)
SYSDATETIME()                       :Simdi
DELETE sh FROM dbo.X sh WHERE ...   DELETE FROM X WHERE ...  (takma ad kullanılmaz)
a + '/' + CAST(b AS varchar(10))    a || '/' || CAST(b AS TEXT)  (metin birleştirme)
SUM(para)                           ROUND(SUM(para), 2)  (REAL toplamında kuruş kayması olmasın)
DECLARE / IF / TRY...CATCH          SQLite'ta yok: BEGIN; değişiklik; SELECT changes(); sonra
                                    elle COMMIT ya da ROLLBACK
```

- Tarih/saat kolonları `'YYYY-MM-DD HH:MM:SS'` biçiminde metin olarak saklanır. Metin karşılaştırması
  bu biçimde doğru sıralar.
- `BETWEEN` ile gün aralığı verirken bitişe saat ekleyin (`'2026-09-30 23:59:59'`). Sadece
  `'2026-09-30'` yazarsanız o günün kayıtları dışarıda kalır. SQL Server'da `datetime` ile de böyledir.
- **Sabit zaman:** `SIMDI = '2026-09-30 15:00:00'`. Bu veritabanının "şu an"ıdır. Hiçbir sorguda
  `date('now')` veya gerçek saat kullanılmaz. Zamana bağlı her sorgu `:Simdi` parametresini alır ve
  her zaman bu değerle çalıştırılır. Aynı sabit `db/create_db.py` (`SIMDI_METIN`) ve `araclar.py`
  (`SIMDI`) içinde de tanımlıdır.
- Parametre örnekleri `db/SENARYOLAR.md` dosyasındaki senaryolardan alındı.

### Veri değiştiren scriptler hakkında
Runbook'taki `@BeklenenSayi` kontrolü SQLite'ta tek bir script içinde yapılamaz, çünkü `IF` yok.
Aynı güvenliği elle sağlayın:

1. `BEGIN;` ile işlemi başlatın ve değişiklik komutunu çalıştırın.
2. `SELECT changes();` ile etkilenen satır sayısını okuyun.
3. Sayı, kontrol sorgusunun bulduğu sayıya (`BeklenenSayi`) eşitse `COMMIT;` yazın, değilse `ROLLBACK;`.

Runbook kuralı burada da geçerlidir: bu scriptler **sadece geliştirici onayından sonra** çalıştırılır.

---

## 01 — Kargo takip numarası siparişe düşmüyor

**01-1. Siparişin kargo kuyruğu kayıtları** (örnek: `:SiparisNo = 'S26-00655'`)
```sql
SELECT kk.KuyrukId, kk.Durum, kk.DenemeSayisi, kk.SonHataMesaji,
       kk.OlusturmaZamani, kk.SonDenemeZamani, kf.FirmaAdi
FROM KargoKuyruk kk
JOIN Siparis s ON s.SiparisId = kk.SiparisId
JOIN KargoFirma kf ON kf.KargoFirmaId = kk.KargoFirmaId
WHERE s.SiparisNo = :SiparisNo
ORDER BY kk.OlusturmaZamani DESC;
```

**01-2. Kargo firmasından son başarılı yanıt**
```sql
SELECT kf.FirmaAdi, MAX(kk.SonDenemeZamani) AS SonBasariliYanit
FROM KargoKuyruk kk
JOIN KargoFirma kf ON kf.KargoFirmaId = kk.KargoFirmaId
WHERE kk.Durum = 'GONDERILDI'
GROUP BY kf.FirmaAdi;
```

**01-3. Hatalı kuyruk kaydını yeniden kuyruğa alma (geliştirici onayı)**
(örnek: `:SiparisId = 655`, beklenen 2 satır)
```sql
BEGIN;
UPDATE KargoKuyruk
SET Durum = 'BEKLIYOR',
    DenemeSayisi = 0,
    SonHataMesaji = NULL
WHERE SiparisId = :SiparisId
  AND Durum = 'HATA';
SELECT changes() AS Guncellenen;   -- BeklenenSayi ile aynıysa COMMIT; değilse ROLLBACK;
```

## 02 — İade kaydı kapanmıyor / iade tutarı yanlış hesaplanıyor

**02-1. İadeye bağlı kalemlerin kabul bilgisi ve adetleri** (örnek: `:IadeNo = 'IAD-2026-00177'`)
```sql
SELECT ik.IadeKalemId, ik.SiraNo, ik.UrunKodu,
       ik.IadeAdet, sk.Adet AS SatisAdet,
       ik.TeslimAlmaZamani, ik.Durum
FROM IadeKalem ik
JOIN Iade i ON i.IadeId = ik.IadeId
JOIN SiparisKalem sk ON sk.SiparisKalemId = ik.SiparisKalemId
WHERE i.IadeNo = :IadeNo
ORDER BY ik.SiraNo;
```

**02-2. İade tutarı ve mağazanın iade kargo kesintisi ayarı** (örnek: `:IadeNo = 'IAD-2026-00176'`)
```sql
SELECT i.IadeNo, i.Durum, m.MagazaKodu, m.IadeKargoUcretiKes,
       ROUND(SUM(ik.IadeAdet * sk.BirimFiyat), 2) AS KalemToplami,
       i.KargoKesintiTutari, i.GeriOdemeTutari
FROM Iade i
JOIN Siparis s ON s.SiparisId = i.SiparisId
JOIN Magaza m ON m.MagazaId = s.MagazaId
JOIN IadeKalem ik ON ik.IadeId = i.IadeId
JOIN SiparisKalem sk ON sk.SiparisKalemId = ik.SiparisKalemId
WHERE i.IadeNo = :IadeNo
GROUP BY i.IadeNo, i.Durum, m.MagazaKodu, m.IadeKargoUcretiKes,
         i.KargoKesintiTutari, i.GeriOdemeTutari;
```

**02-3. Eksik depo kabul zamanını doldurma (geliştirici onayı)**
(örnek: `:IadeId = 37`, `:KabulZamani = '2026-09-24 15:40:00'`, beklenen 1 satır)
```sql
BEGIN;
UPDATE IadeKalem
SET TeslimAlmaZamani = :KabulZamani,
    Durum = 'KABUL_EDILDI'
WHERE IadeId = :IadeId
  AND TeslimAlmaZamani IS NULL;
SELECT changes() AS Guncellenen;   -- BeklenenSayi ile aynıysa COMMIT; değilse ROLLBACK;
```

## 03 — Kampanya kuponu süresi dolmuş görünüyor

**03-1. Kupon koduna ait tüm kayıtlar** (örnek: `:KuponKodu = 'GUZ25'`)
```sql
SELECT ku.KuponId, ku.KuponKodu, ku.BaslangicTarihi, ku.BitisTarihi,
       ku.Aktif, ku.OlusturmaZamani, ka.KampanyaAdi
FROM Kupon ku
JOIN Kampanya ka ON ka.KampanyaId = ku.KampanyaId
WHERE ku.KuponKodu = :KuponKodu
ORDER BY ku.OlusturmaZamani DESC;
```

**03-2. Süresi dolmuş mükerrer kuponu pasife alma (geliştirici onayı)**
(örnek: `:KuponKodu = 'GUZ25'`, `:Simdi = '2026-09-30 15:00:00'`, beklenen 1 satır)
```sql
BEGIN;
UPDATE Kupon
SET Aktif = 0
WHERE KuponKodu = :KuponKodu
  AND Aktif = 1
  AND BitisTarihi < date(:Simdi)
  AND KuponId < (
        SELECT MAX(k2.KuponId)
        FROM Kupon k2
        WHERE k2.KuponKodu = :KuponKodu
  );
SELECT changes() AS Guncellenen;   -- BeklenenSayi ile aynıysa COMMIT; değilse ROLLBACK;
```

## 04 — Depo toplama işi tamamlandı ama açık görünüyor

**04-1. Toplama işinin durumu ve satırları** (örnek: `:DepoKodu = 'DP-IST'`, `:IsNo = 'TPL-42285'`)
```sql
SELECT ti.ToplamaIsiId, ti.IsNo, ti.Durum AS IsDurum,
       ts.UrunKodu, ts.IstenenAdet, ts.OkutulanAdet, ts.OkutmaZamani
FROM ToplamaIsi ti
JOIN ToplamaSatir ts ON ts.ToplamaIsiId = ti.ToplamaIsiId
JOIN Depo d ON d.DepoId = ti.DepoId
WHERE d.DepoKodu = :DepoKodu
  AND ti.IsNo = :IsNo
ORDER BY ts.UrunKodu;
```

**04-2. El terminalinden gelen son senkron kayıtları** (örnek: `:DepoKodu = 'DP-ANK'`)
```sql
SELECT tsn.TerminalKodu, tsn.Durum, tsn.KayitSayisi,
       tsn.GonderimZamani, tsn.HataMesaji
FROM TerminalSenkron tsn
JOIN Depo d ON d.DepoId = tsn.DepoId
WHERE d.DepoKodu = :DepoKodu
ORDER BY tsn.GonderimZamani DESC;
```

**04-3. Tamamlanmış toplama işini kapatma (geliştirici onayı)**
(örnek: `:ToplamaIsiId = 638`, `:Simdi = '2026-09-30 15:00:00'`, beklenen 1 satır)
```sql
BEGIN;
UPDATE ToplamaIsi
SET Durum = 'TAMAMLANDI',
    TamamlanmaZamani = :Simdi
WHERE ToplamaIsiId = :ToplamaIsiId
  AND Durum = 'ACIK'
  AND NOT EXISTS (
        SELECT 1 FROM ToplamaSatir ts
        WHERE ts.ToplamaIsiId = :ToplamaIsiId
          AND ts.OkutulanAdet < ts.IstenenAdet
  );
SELECT changes() AS Guncellenen;   -- BeklenenSayi ile aynıysa COMMIT; değilse ROLLBACK;
```

## 05 — Ürün stoğu negatif çıkıyor

**05-1. Ürün ve varyant için son hareketler**
(örnek: `:UrunKodu = 'HVL-3002'`, `:VaryantKodu = 'HVL-3002-GRI'`)
```sql
SELECT sh.HareketId, sh.VaryantKodu, sh.HareketTipi, sh.Miktar,
       sh.HareketTarihi, sh.KaynakReferans
FROM StokHareket sh
JOIN Urun u ON u.UrunId = sh.UrunId
WHERE u.UrunKodu = :UrunKodu
  AND sh.VaryantKodu = :VaryantKodu
ORDER BY sh.HareketTarihi DESC;
```

**05-2. Mükerrer hareketler (aynı referans + aynı miktar)** (örnek: `:UrunKodu = 'HVL-3002'`)
```sql
SELECT sh.KaynakReferans, sh.VaryantKodu, sh.Miktar, COUNT(*) AS Adet
FROM StokHareket sh
JOIN Urun u ON u.UrunId = sh.UrunId
WHERE u.UrunKodu = :UrunKodu
GROUP BY sh.KaynakReferans, sh.VaryantKodu, sh.Miktar
HAVING COUNT(*) > 1;
```

**05-3. Siparişteki bedenden farklı bir varyanttan düşülmüş satışlar** (örnek: `:UrunKodu = 'PJM-4003'`)

Satış hareketinin `KaynakReferans` değeri `SiparisNo/SiraNo` biçimindedir. Bu sorgu her satış
hareketini ait olduğu sipariş kalemiyle eşleştirir ve yalnızca varyantı uyuşmayanları döndürür.
```sql
SELECT sh.HareketId, sh.HareketTarihi, sh.KaynakReferans, sh.Miktar,
       sh.VaryantKodu AS DusulenVaryant,
       sk.VaryantKodu AS SiparisVaryant
FROM StokHareket sh
JOIN Urun u ON u.UrunId = sh.UrunId
JOIN SiparisKalem sk ON sk.UrunId = sh.UrunId
JOIN Siparis s ON s.SiparisId = sk.SiparisId
WHERE u.UrunKodu = :UrunKodu
  AND sh.HareketTipi = 'SATIS'
  AND sh.KaynakReferans = s.SiparisNo || '/' || CAST(sk.SiraNo AS TEXT)
  AND sh.VaryantKodu <> sk.VaryantKodu
ORDER BY sh.HareketTarihi DESC;
```

**05-4. Mükerrer stok hareketini silme (geliştirici onayı)**
(örnek: `:KaynakReferans = 'S26-00624/1'`, `:VaryantKodu = 'HVL-3002-GRI'`, beklenen 1 satır)
```sql
BEGIN;
-- Aynı referans+varyant için en küçük HareketId'yi koru, geri kalan mükerrerleri sil.
DELETE FROM StokHareket
WHERE KaynakReferans = :KaynakReferans
  AND VaryantKodu = :VaryantKodu
  AND HareketId > (
        SELECT MIN(i.HareketId)
        FROM StokHareket i
        WHERE i.KaynakReferans = :KaynakReferans
          AND i.VaryantKodu = :VaryantKodu
  );
SELECT changes() AS Guncellenen;   -- BeklenenSayi ile aynıysa COMMIT; değilse ROLLBACK;
```

Not: Bu veritabanında `StokBakiye` tablosu hareketlerden otomatik güncellenmez (tetikleyici yok).
Hareket silindikten sonra bakiyeyi yeniden hesaplamak gerekirse:
```sql
UPDATE StokBakiye
SET Bakiye = (SELECT COALESCE(SUM(sh.Miktar), 0) FROM StokHareket sh
              WHERE sh.VaryantKodu = StokBakiye.VaryantKodu)
WHERE VaryantKodu = :VaryantKodu;
```

## 06 — Toplu fiyat değişikliği talebi onay akışında takılı

**06-1. Talebin onay adımları ve atanan kullanıcı** (örnek: `:TalepNo = 'FT-2026-0133'`)
```sql
SELECT ft.TalepNo, ft.Durum, oa.AdimSira, oa.AdimDurum,
       k.KullaniciAdi, k.Aktif AS OnaylayiciAktif
FROM FiyatTalep ft
JOIN FiyatOnayAdim oa ON oa.FiyatTalepId = ft.FiyatTalepId
LEFT JOIN Kullanici k ON k.KullaniciId = oa.AtananKullaniciId
WHERE ft.TalepNo = :TalepNo
ORDER BY oa.AdimSira;
```

**06-2. Onay adımını aktif kullanıcıya yeniden atama (geliştirici onayı)**
(örnek: `:FiyatTalepId = 33`, `:YeniKullaniciId = 4`, beklenen 1 satır)
```sql
BEGIN;
UPDATE FiyatOnayAdim
SET AtananKullaniciId = :YeniKullaniciId
WHERE FiyatTalepId = :FiyatTalepId
  AND AdimDurum = 'BEKLIYOR';
SELECT changes() AS Guncellenen;   -- BeklenenSayi ile aynıysa COMMIT; değilse ROLLBACK;
```

## 07 — Kargoya verme süresi (SLA) raporu

**07-1. Onaydan kargoya verilene kadar geçen saat**
(örnek: `:MagazaKodu = 'MG-CRV-01'`, `:Baslangic = '2026-09-01 00:00:00'`, `:Bitis = '2026-09-30 23:59:59'`)

`DATEDIFF(hour, a, b)` geçen tam saati değil, aradaki saat sınırı sayısını verir (10:59 → 11:01 = 1).
Aşağıdaki ifade bunu aynen taklit eder: iki zamanı saat başına yuvarlayıp farkı alır.
```sql
SELECT s.SiparisNo, s.OnayZamani, s.KargoyaVermeZamani,
       (CAST(strftime('%s', strftime('%Y-%m-%d %H:00:00', s.KargoyaVermeZamani)) AS INTEGER)
        - CAST(strftime('%s', strftime('%Y-%m-%d %H:00:00', s.OnayZamani)) AS INTEGER)) / 3600 AS GecenSaat
FROM Siparis s
JOIN Magaza m ON m.MagazaId = s.MagazaId
WHERE m.MagazaKodu = :MagazaKodu
  AND s.OnayZamani BETWEEN :Baslangic AND :Bitis
ORDER BY GecenSaat DESC;
```
Kargoya verme zamanı boş olan siparişlerde `GecenSaat` NULL olur ve listenin sonunda çıkar
(SQL Server'da da öyle). Bunlar raporda "Veri Yok" görünen satırlardır.

## 08 — Yeni pazaryeri mağazası

**08-1. Aynı satıcı ID var mı** (örnek: `:SaticiId = '418230'`)
```sql
SELECT MagazaId, MagazaAdi, PazaryeriKodu, SaticiId, Aktif
FROM Magaza
WHERE SaticiId = :SaticiId;
```

## 09 — Kullanıcı yetkisi / rol

**09-1. Kullanıcının etkin rol ve yetkileri** (örnek: `:KullaniciAdi = 'deniz.kaplanli'`)
```sql
SELECT k.KullaniciAdi, r.RolAdi, y.YetkiKodu
FROM Kullanici k
JOIN KullaniciRol kr ON kr.KullaniciId = k.KullaniciId
JOIN Rol r ON r.RolId = kr.RolId
JOIN RolYetki ry ON ry.RolId = r.RolId
JOIN Yetki y ON y.YetkiId = ry.YetkiId
WHERE k.KullaniciAdi = :KullaniciAdi
ORDER BY r.RolAdi, y.YetkiKodu;
```

## 10 — Sipariş dökümünün PDF çıktısı

Bu bilgi notunda SQL sorgusu yok.
