# İade kaydı kapanmıyor / iade tutarı yanlış hesaplanıyor

## Belirti
- Kullanıcı / müşteri ne görüyor?
  - "İadeyi Tamamla" butonuna basınca "Teslim alınmamış kalemler var, iade kapatılamaz"
    uyarısı çıkıyor.
  - Geri ödenecek tutar boş ya da olması gerekenden çok farklı çıkıyor (ör. yarısı kadar).
- Destek ekibi bu sorunu nasıl tanır?
  - İade kaydının durumu `ACIK`, ama kullanıcı ürünlerin depoya ulaştığını söylüyor.
  - İadeye bağlı bir kalemde `TeslimAlmaZamani` (depo kabul) boş.
- Nasıl soruluyor: "İade bir türlü kapanmıyor", "Geri ödeme sıfır çıkıyor",
  "İade tutarı tutmuyor"

## Etkilenen modül
- Siparişler > İadeler > İade Detay > Kapanış
- Siparişler > İadeler > Geri Ödeme Hesabı
- İlgili tablolar: `dbo.Iade`, `dbo.IadeKalem`, `dbo.SiparisKalem`

## Kontrol adımları
1. **Program sürümüne bakın.** 4.8 öncesinde depo kabulü girilmemiş kalem iade kapanışını
   engellemiyordu (eksik geri ödemeye yol açardı); 4.8 ile birlikte engelleme eklendi.
2. **İadeye bağlı kalemlerin kabul bilgisini ve adetlerini kontrol edin.** Bu sorgu sadece
   okuma yapar, hiçbir şeyi değiştirmez.

```sql
   SELECT ik.IadeKalemId, ik.SiraNo, ik.UrunKodu,
          ik.IadeAdet, sk.Adet AS SatisAdet,
          ik.TeslimAlmaZamani, ik.Durum
   FROM dbo.IadeKalem ik
   JOIN dbo.Iade i ON i.IadeId = ik.IadeId
   JOIN dbo.SiparisKalem sk ON sk.SiparisKalemId = ik.SiparisKalemId
   WHERE i.IadeNo = @IadeNo
   ORDER BY ik.SiraNo;
```

3. **Sonucu okuyun.**
   - `TeslimAlmaZamani` NULL olan kalem varsa → iade bu yüzden kapanmıyor.
   - `IadeAdet > SatisAdet` (satılandan fazla iade) ise → hatalı giriş, geri ödeme tutarı bozuk.
   - Tüm satırlar dolu ve tutarlıysa → sorun kapanışta değil, kargo ücreti kesintisi
     ayarındadır.
   - Eksik/hatalı satır sayısını not alın.

## Olası nedenler ve çözümleri
- **Neden:** Depo, paketi teslim aldığı halde kabul işlemini sisteme girmemiş.
  **Çözüm:** Kullanıcıdan İade Detay > Kalemler ekranında "Depo Kabul" girmesini isteyin;
  ekran kalemi kilitliyorsa kabul zamanının doldurulması gerekir (aşağıdaki script,
  geliştirici onayı).
- **Neden:** İade adedi, satılan adetten fazla girilmiş.
  **Çözüm:** Kullanıcı iade kalemini açıp adedi düzeltmeli; ardından geri ödeme yeniden hesaplanır.
- **Neden:** Mağaza ayarlarında "İade kargo ücretini müşteriden kes" seçeneği açık.
  **Çözüm:** Tutar doğrudur; müşteriye kesintiyi açıklayın ya da mağaza yöneticisi ayarı değiştirsin.

## Ne zaman geliştiriciye iletilir
- Tüm kalemler kabul edildiği halde iade kapanmıyorsa.
- Geri ödeme tutarı, kalemler ve kesinti ayarı doğru olduğu halde yanlışsa.
- İletirken eklenecekler:
  - Müşteri adı
  - Program sürümü
  - Kontrol sorgusunun sonucu / satır sayısı
  - Varsa ekran görüntüsü

### Eksik depo kabul zamanını doldurma script'i — SADECE geliştirici onayından sonra
> ⚠ Bu script veri değiştirir. Geliştiriciden onay almadan çalıştırmayın.
> Değiştirmeniz gereken TEK satır: @BeklenenSayi (kontrol sorgusunun bulduğu boş satır sayısı).

```sql
DECLARE @BeklenenSayi int = NULL;   -- ← TeslimAlmaZamani boş olan kalem sayısı
SET XACT_ABORT ON;

IF @BeklenenSayi IS NULL
BEGIN
    PRINT 'DURDURULDU: @BeklenenSayi yazılmamış. Önce kontrol sorgusunu çalıştırın.';
    RETURN;
END

DECLARE @Guncellenen int;
DECLARE @IadeId int = NULL;                 -- ← geliştiricinin onayladığı iade
DECLARE @KabulZamani datetime2 = NULL;      -- ← depodan teyit edilen kabul zamanı

BEGIN TRY
    BEGIN TRAN;

    UPDATE dbo.IadeKalem
    SET TeslimAlmaZamani = @KabulZamani,
        Durum = 'KABUL_EDILDI'
    WHERE IadeId = @IadeId
      AND TeslimAlmaZamani IS NULL;

    SET @Guncellenen = @@ROWCOUNT;

    IF @Guncellenen = @BeklenenSayi
    BEGIN
        COMMIT;
        PRINT 'TAMAM: ' + CAST(@Guncellenen AS varchar(10)) + ' kayıt güncellendi.';
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
