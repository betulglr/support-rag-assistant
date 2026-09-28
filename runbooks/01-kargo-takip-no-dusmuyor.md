# Kargo takip numarası siparişe düşmüyor

## Belirti
- Kullanıcı / müşteri ne görüyor?
  - Sipariş "Hazırlanıyor" durumunda kalıyor, kargo takip numarası alanı boş.
  - Pazaryerine (ör. Çarşıvera, Tezgahlı) "kargoya verildi" bildirimi gitmiyor; satıcı
    panelinde sipariş hâlâ gönderilmemiş görünüyor.
- Destek ekibi bu sorunu nasıl tanır?
  - `dbo.KargoKuyruk` tablosunda siparişe ait kayıt `HATA` ya da uzun süredir `BEKLIYOR`
    durumunda.
  - Aynı kargo firmasına ait diğer siparişlerde de son birkaç saattir yanıt gelmemiş.
- Nasıl soruluyor: "Takip no gelmedi", "Kargo barkodu oluşmuyor", "Pazaryerinde hâlâ
  hazırlanıyor yazıyor"

## Etkilenen modül
- Siparişler > Kargo Entegrasyonu
- Entegrasyonlar > Kargo Firmaları (Menzilo Kargo, Paketra)
- İlgili tablolar: `dbo.Siparis`, `dbo.KargoKuyruk`, `dbo.KargoFirma`

## Kontrol adımları
1. **Program sürümüne bakın.** 5.1 öncesinde kargo firmasının erişim anahtarı (token) süresi
   dolduğunda otomatik yenilenmiyordu ve kuyruk sessizce duruyordu; 5.1'de otomatik yenileme
   eklendi.
2. **Siparişin kargo kuyruğundaki kayıtlarını kontrol edin.** Bu sorgu sadece okuma yapar,
   hiçbir şeyi değiştirmez.

```sql
   SELECT kk.KuyrukId, kk.Durum, kk.DenemeSayisi, kk.SonHataMesaji,
          kk.OlusturmaZamani, kk.SonDenemeZamani, kf.FirmaAdi
   FROM dbo.KargoKuyruk kk
   JOIN dbo.Siparis s ON s.SiparisId = kk.SiparisId
   JOIN dbo.KargoFirma kf ON kf.KargoFirmaId = kk.KargoFirmaId
   WHERE s.SiparisNo = @SiparisNo
   ORDER BY kk.OlusturmaZamani DESC;
```

3. **Kargo firmasından en son ne zaman başarılı yanıt geldiğine bakın.**

```sql
   SELECT kf.FirmaAdi, MAX(kk.SonDenemeZamani) AS SonBasariliYanit
   FROM dbo.KargoKuyruk kk
   JOIN dbo.KargoFirma kf ON kf.KargoFirmaId = kk.KargoFirmaId
   WHERE kk.Durum = 'GONDERILDI'
   GROUP BY kf.FirmaAdi;
```

4. **Sonucu okuyun.**
   - Kayıt `HATA` ve `SonHataMesaji` içinde "yetkisiz" / "401" geçiyorsa → erişim anahtarı
     süresi dolmuş.
   - Kayıt `BEKLIYOR` ve firmanın son başarılı yanıtı saatler önceyse → firma tarafında kesinti.
   - Siparişe ait hiç kuyruk kaydı yoksa → sipariş kargo firması seçilmeden onaylanmış.
   - `HATA` durumundaki satır sayısını not alın.

## Olası nedenler ve çözümleri
- **Neden:** Kargo firmasının erişim anahtarı süresi dolmuş.
  **Çözüm:** Müşteriden Entegrasyonlar > Kargo Firmaları ekranında "Bağlantıyı Yenile" demesini
  isteyin; ardından hatalı kayıtların yeniden kuyruğa alınması gerekir (aşağıdaki script,
  geliştirici onayı).
- **Neden:** Kargo firmasının servisinde geçici kesinti var.
  **Çözüm:** Bekleyen kayıtlar firma düzelince otomatik gönderilir; müşteriyi bilgilendirin.
- **Neden:** Siparişte kargo firması seçilmemiş.
  **Çözüm:** Kullanıcı Sipariş Detay ekranından kargo firmasını seçip "Kargoya Gönder" demeli.

## Ne zaman geliştiriciye iletilir
- Bağlantı yenilendiği halde kayıtlar `HATA` durumunda kalıyorsa.
- Hata mesajı anlaşılmıyorsa ya da birden çok kargo firması aynı anda etkilenmişse.
- İletirken eklenecekler:
  - Müşteri adı
  - Program sürümü
  - Kontrol sorgusunun sonucu / satır sayısı
  - Varsa ekran görüntüsü

### Hatalı kargo kuyruğu kaydını yeniden kuyruğa alma script'i — SADECE geliştirici onayından sonra
> ⚠ Bu script veri değiştirir. Geliştiriciden onay almadan çalıştırmayın.
> Değiştirmeniz gereken TEK satır: @BeklenenSayi (kontrol sorgusunun bulduğu HATA satır sayısı).

```sql
DECLARE @BeklenenSayi int = NULL;   -- ← kontrol sorgusunun bulduğu HATA satır sayısı
SET XACT_ABORT ON;

IF @BeklenenSayi IS NULL
BEGIN
    PRINT 'DURDURULDU: @BeklenenSayi yazılmamış. Önce kontrol sorgusunu çalıştırın.';
    RETURN;
END

DECLARE @Guncellenen int;
DECLARE @SiparisId int = NULL;   -- ← geliştiricinin onayladığı sipariş

BEGIN TRY
    BEGIN TRAN;

    UPDATE dbo.KargoKuyruk
    SET Durum = 'BEKLIYOR',
        DenemeSayisi = 0,
        SonHataMesaji = NULL
    WHERE SiparisId = @SiparisId
      AND Durum = 'HATA';

    SET @Guncellenen = @@ROWCOUNT;

    IF @Guncellenen = @BeklenenSayi
    BEGIN
        COMMIT;
        PRINT 'TAMAM: ' + CAST(@Guncellenen AS varchar(10)) + ' kayıt yeniden kuyruğa alındı.';
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
