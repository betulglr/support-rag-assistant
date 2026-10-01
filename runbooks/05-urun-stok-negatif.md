# Ürün stoğu negatif çıkıyor

## Belirti
- Kullanıcı / müşteri ne görüyor?
  - Stok ekranında bir ürün / varyant (beden, renk) için bakiye eksi (negatif) değerde.
  - Ürün pazaryerinde otomatik olarak satışa kapanmış; raftaki gerçek adetle sistem uyuşmuyor.
- Destek ekibi bu sorunu nasıl tanır?
  - Stok hareketlerinde satış düşümü, mal kabulden daha erken tarihli işlenmiş ya da mükerrer
    satış düşümü var.
  - Pazaryerinden gelen aynı sipariş bildirimi iki kez işlenmiş olabilir.
- Nasıl soruluyor: "Stok eksi görünüyor", "Bakiye sıfırın altında", "Elde var ama sistem yok diyor"

## Etkilenen modül
- Stok > Bakiye
- Stok > Hareketler (Mal Kabul / Satış / İade Girişi)
- İlgili tablolar: `dbo.StokHareket`, `dbo.StokBakiye`, `dbo.Urun`

## Kontrol adımları
1. **Program sürümüne bakın.** 4.6 öncesinde pazaryeri aynı sipariş bildirimini iki kez
   gönderdiğinde mükerrer satış düşümü oluşabiliyordu; 4.6'da tekillik kontrolü (idempotency) eklendi.
2. **İlgili ürün ve varyant için son hareketleri listeleyin.** Bu sorgu sadece okuma yapar,
   hiçbir şeyi değiştirmez.

```sql
   SELECT sh.HareketId, sh.VaryantKodu, sh.HareketTipi, sh.Miktar,
          sh.HareketTarihi, sh.KaynakReferans
   FROM dbo.StokHareket sh
   JOIN dbo.Urun u ON u.UrunId = sh.UrunId
   WHERE u.UrunKodu = @UrunKodu
     AND sh.VaryantKodu = @VaryantKodu
   ORDER BY sh.HareketTarihi DESC;
```

3. **Mükerrer hareketleri arayın (aynı referans + aynı miktar).**

```sql
   SELECT sh.KaynakReferans, sh.VaryantKodu, sh.Miktar, COUNT(*) AS Adet
   FROM dbo.StokHareket sh
   JOIN dbo.Urun u ON u.UrunId = sh.UrunId
   WHERE u.UrunKodu = @UrunKodu
   GROUP BY sh.KaynakReferans, sh.VaryantKodu, sh.Miktar
   HAVING COUNT(*) > 1;
```

4. **Satışın siparişteki beden/varyanttan düşülüp düşülmediğini kontrol edin.** Satış
   hareketinin `KaynakReferans` değeri `SiparisNo/SiraNo` biçimindedir; sorgu her satışı ait olduğu
   sipariş kalemiyle eşleştirir ve yalnızca varyantı uyuşmayanları listeler.

```sql
   SELECT sh.HareketId, sh.HareketTarihi, sh.KaynakReferans, sh.Miktar,
          sh.VaryantKodu AS DusulenVaryant,
          sk.VaryantKodu AS SiparisVaryant
   FROM dbo.StokHareket sh
   JOIN dbo.Urun u ON u.UrunId = sh.UrunId
   JOIN dbo.SiparisKalem sk ON sk.UrunId = sh.UrunId
   JOIN dbo.Siparis s ON s.SiparisId = sk.SiparisId
   WHERE u.UrunKodu = @UrunKodu
     AND sh.HareketTipi = 'SATIS'
     AND sh.KaynakReferans = s.SiparisNo + '/' + CAST(sk.SiraNo AS varchar(10))
     AND sh.VaryantKodu <> sk.VaryantKodu
   ORDER BY sh.HareketTarihi DESC;
```

5. **Sonucu okuyun.**
   - Mükerrer hareket varsa (Adet > 1) → fazladan satış düşümü bakiyeyi eksiye düşürmüş olabilir.
   - Varyantın hiç `MAL_KABUL` hareketi yoksa → mal kabul girilmemiş, sadece satışlar işlenmiş.
   - Mal kabul kaydı, kendisinden sonraki satışlardan geç tarihliyse → sıralama sorunu.
   - 4. adım satır döndürürse → beden karışıklığı: satış, siparişteki bedenden (`SiparisVaryant`)
     değil başka bir bedenden (`DusulenVaryant`) düşülmüş. `DusulenVaryant` eksiye düşer,
     `SiparisVaryant` raftakinden fazla görünür.
   - Hiç anormallik yoksa → gerçekten fazla satış yapılmış olabilir, depoyla sayım teyidi yapın.
   - Mükerrer satır sayısını not alın.

## Olası nedenler ve çözümleri
- **Neden:** Aynı pazaryeri sipariş bildirimi iki kez işlenmiş, satış mükerrer düşülmüş.
  **Çözüm:** Fazladan (mükerrer) hareketi silmek gerekir → aşağıdaki script (geliştirici onayı).
- **Neden:** Mal kabul kaydı hiç girilmemiş, sadece satışlar işlenmiş.
  **Çözüm:** Kullanıcıdan eksik mal kabul kaydını Hareketler ekranından girmesini isteyin.
- **Neden:** Beden/varyant karışıklığı: satış, siparişteki bedenden değil başka bir bedenden
  düşülmüş (ör. M beden satışı L bedenden düşülmüş). Bir beden eksiye düşer, diğeri fazla görünür;
  4. adımda `DusulenVaryant` ile `SiparisVaryant` farklı çıkar.
  **Çözüm:** Kullanıcı ilgili hareketin varyantını sipariş kalemindeki bedene düzeltmeli; ekranda
  düzeltilemiyorsa geliştiriciye iletin.

## Ne zaman geliştiriciye iletilir
- Mükerrer hareket tespit edildiyse (silme işlemi gerekir).
- Bakiye, açıklanamayan bir farkla negatifse.
- İletirken eklenecekler:
  - Müşteri adı
  - Program sürümü
  - Kontrol sorgusunun sonucu / satır sayısı (hareketler + mükerrer listesi)
  - Varsa ekran görüntüsü

### Mükerrer stok hareketini silme script'i — SADECE geliştirici onayından sonra
> ⚠ Bu script veri değiştirir. Geliştiriciden onay almadan çalıştırmayın.
> Değiştirmeniz gereken TEK satır: @BeklenenSayi (silinecek mükerrer satır sayısı).

```sql
DECLARE @BeklenenSayi int = NULL;   -- ← silinecek mükerrer satır sayısı
SET XACT_ABORT ON;

IF @BeklenenSayi IS NULL
BEGIN
    PRINT 'DURDURULDU: @BeklenenSayi yazılmamış. Önce kontrol sorgusunu çalıştırın.';
    RETURN;
END

DECLARE @Guncellenen int;
DECLARE @KaynakReferans varchar(100) = NULL;  -- ← geliştiricinin onayladığı referans
DECLARE @VaryantKodu varchar(30) = NULL;      -- ← geliştiricinin onayladığı varyant

BEGIN TRY
    BEGIN TRAN;

    -- Aynı referans+varyant için en küçük HareketId'yi koru, geri kalan mükerrerleri sil.
    DELETE sh
    FROM dbo.StokHareket sh
    WHERE sh.KaynakReferans = @KaynakReferans
      AND sh.VaryantKodu = @VaryantKodu
      AND sh.HareketId > (
            SELECT MIN(i.HareketId)
            FROM dbo.StokHareket i
            WHERE i.KaynakReferans = @KaynakReferans
              AND i.VaryantKodu = @VaryantKodu
      );

    SET @Guncellenen = @@ROWCOUNT;

    IF @Guncellenen = @BeklenenSayi
    BEGIN
        COMMIT;
        PRINT 'TAMAM: ' + CAST(@Guncellenen AS varchar(10)) + ' kayıt silindi.';
    END
    ELSE
    BEGIN
        ROLLBACK;
        PRINT 'GERİ ALINDI: Beklenen ' + CAST(@BeklenenSayi AS varchar(10))
            + ', bulunan ' + CAST(@Guncellenen AS varchar(10))
            + '. Hiçbir kayıt değiştirilmedi. Geliştiriciye bildirin.';
    END
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK;
    PRINT 'HATA: Hiçbir kayıt değiştirilmedi. Geliştiriciye bildirin. Detay: ' + ERROR_MESSAGE();
END CATCH
```

**Sonuç nasıl okunur:** TAMAM → işlem bitti. GERİ ALINDI veya HATA → hiçbir şey değişmedi, geliştiriciye bildirin.

## Son güncelleme
2026-10-01
