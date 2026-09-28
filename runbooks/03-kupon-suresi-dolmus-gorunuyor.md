# Kampanya kuponu süresi dolmuş görünüyor (ama uzatılmış)

## Belirti
- Kullanıcı / müşteri ne görüyor?
  - Son kullanıcı sepette kodu girince "Kupon geçersiz veya süresi doldu" hatası alıyor.
  - Mağaza yöneticisi panelde kuponun bitiş tarihini ileri almış, ekranda yeni tarih görünüyor.
- Destek ekibi bu sorunu nasıl tanır?
  - Aynı kupon kodu için `dbo.Kupon` tablosunda birden fazla satır var; eski satır hâlâ
    `Aktif = 1` ve bitiş tarihi geçmiş.
  - Kod bazı müşterilerde çalışıyor, bazılarında çalışmıyor.
- Nasıl soruluyor: "Kod geçersiz diyor ama uzattık", "İndirim kodu çalışmıyor",
  "Kupon tarihi yenilenmedi"

## Etkilenen modül
- Pazarlama > Kampanyalar > Kuponlar
- Sepet / Ödeme > Kupon Doğrulama
- İlgili tablolar: `dbo.Kupon`, `dbo.Kampanya`, `dbo.KuponKullanim`

## Kontrol adımları
1. **Program sürümüne bakın.** 4.5 öncesinde kupon uzatma işlemi eski kaydı güncellemek yerine
   aynı kodla yeni bir kayıt açıyordu; 4.5'te uzatma mevcut kaydı güncelleyecek şekilde düzeltildi.
2. **Kupon koduna ait tüm kayıtları listeleyin.** Bu sorgu sadece okuma yapar, hiçbir şeyi
   değiştirmez.

```sql
   SELECT ku.KuponId, ku.KuponKodu, ku.BaslangicTarihi, ku.BitisTarihi,
          ku.Aktif, ku.OlusturmaZamani, ka.KampanyaAdi
   FROM dbo.Kupon ku
   JOIN dbo.Kampanya ka ON ka.KampanyaId = ku.KampanyaId
   WHERE ku.KuponKodu = @KuponKodu
   ORDER BY ku.OlusturmaZamani DESC;
```

3. **Sonucu okuyun.**
   - Aynı kod için iki satır varsa ve eskisi `Aktif = 1`, `BitisTarihi` geçmişse → mükerrer
     kupon; doğrulama eski kaydı buluyor.
   - Tek satır var ve `BitisTarihi` doğruysa → vitrin önbelleği henüz yenilenmemiş olabilir
     (15 dakika).
   - Tek satır var ve `BitisTarihi` hâlâ eskiyse → uzatma kaydedilmemiş.
   - Süresi dolmuş mükerrer satır sayısını not alın.

## Olası nedenler ve çözümleri
- **Neden:** Uzatma işlemi aynı kodla yeni kupon açmış, eski kayıt aktif kalmış.
  **Çözüm:** Süresi dolmuş eski kaydın pasife alınması gerekir (aşağıdaki script, geliştirici onayı).
- **Neden:** Vitrin önbelleği yenilenmemiş.
  **Çözüm:** 15 dakika bekleyin ya da Pazarlama > Kuponlar ekranında "Önbelleği Yenile" deyin.
- **Neden:** Kullanıcı uzatmayı yapmış ama "Kaydet" dememiş.
  **Çözüm:** Kullanıcıdan bitiş tarihini tekrar girip kaydetmesini isteyin.

## Ne zaman geliştiriciye iletilir
- Mükerrer kupon kaydı tespit edildiyse (pasife alma gerekir).
- Tek ve doğru kayıt olduğu halde önbellek yenilendikten sonra da hata sürüyorsa.
- İletirken eklenecekler:
  - Müşteri adı
  - Program sürümü
  - Kontrol sorgusunun sonucu / satır sayısı
  - Varsa ekran görüntüsü

### Süresi dolmuş mükerrer kuponu pasife alma script'i — SADECE geliştirici onayından sonra
> ⚠ Bu script veri değiştirir. Geliştiriciden onay almadan çalıştırmayın.
> Değiştirmeniz gereken TEK satır: @BeklenenSayi (pasife alınacak eski kupon satırı sayısı).

```sql
DECLARE @BeklenenSayi int = NULL;   -- ← pasife alınacak süresi dolmuş satır sayısı
SET XACT_ABORT ON;

IF @BeklenenSayi IS NULL
BEGIN
    PRINT 'DURDURULDU: @BeklenenSayi yazılmamış. Önce kontrol sorgusunu çalıştırın.';
    RETURN;
END

DECLARE @Guncellenen int;
DECLARE @KuponKodu varchar(50) = NULL;   -- ← geliştiricinin onayladığı kupon kodu

BEGIN TRY
    BEGIN TRAN;

    UPDATE dbo.Kupon
    SET Aktif = 0
    WHERE KuponKodu = @KuponKodu
      AND Aktif = 1
      AND BitisTarihi < CAST(GETDATE() AS date)
      AND KuponId < (
            SELECT MAX(k2.KuponId)
            FROM dbo.Kupon k2
            WHERE k2.KuponKodu = @KuponKodu
      );

    SET @Guncellenen = @@ROWCOUNT;

    IF @Guncellenen = @BeklenenSayi
    BEGIN
        COMMIT;
        PRINT 'TAMAM: ' + CAST(@Guncellenen AS varchar(10)) + ' kayıt pasife alındı.';
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
2026-09-28
