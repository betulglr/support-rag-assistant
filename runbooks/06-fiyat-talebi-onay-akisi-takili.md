# Toplu fiyat değişikliği talebi onay akışında takılı

## Belirti
- Kullanıcı / müşteri ne görüyor?
  - Toplu fiyat değişikliği talebi "Onay bekliyor" durumunda takılı, yeni fiyatlar yayına girmiyor.
  - Onaylayacak kişi talebi listesinde göremiyor ("bana düşmedi").
- Destek ekibi bu sorunu nasıl tanır?
  - Talebin mevcut onay adımındaki (`FiyatOnayAdim`) atanan kullanıcı pasif / silinmiş ya da
    o adımda hiç onaylayıcı tanımlı değil.
- Nasıl soruluyor: "Fiyat talebi onaya takıldı", "Onaycı göremiyor", "Yeni fiyatlar yayına girmiyor"

## Etkilenen modül
- Ürünler > Fiyat Talepleri
- Ürünler > Onay Akışı Tanımları
- İlgili tablolar: `dbo.FiyatTalep`, `dbo.FiyatOnayAdim`, `dbo.Kullanici`

## Kontrol adımları
1. **Program sürümüne bakın.** 4.2 öncesinde onaylayıcı kullanıcı pasife alındığında akış
   otomatik olarak yedek onaylayıcıya devretmiyordu; 4.2'de devretme (delegation) eklendi.
2. **Talebin bulunduğu onay adımını ve atanan kullanıcıyı kontrol edin.** Bu sorgu sadece
   okuma yapar, hiçbir şeyi değiştirmez.

```sql
   SELECT ft.TalepNo, ft.Durum, oa.AdimSira, oa.AdimDurum,
          k.KullaniciAdi, k.Aktif AS OnaylayiciAktif
   FROM dbo.FiyatTalep ft
   JOIN dbo.FiyatOnayAdim oa ON oa.FiyatTalepId = ft.FiyatTalepId
   LEFT JOIN dbo.Kullanici k ON k.KullaniciId = oa.AtananKullaniciId
   WHERE ft.TalepNo = @TalepNo
   ORDER BY oa.AdimSira;
```

3. **Sonucu okuyun.**
   - Mevcut adımda (`AdimDurum = 'BEKLIYOR'`) `AtananKullaniciId` NULL ise → o adımda
     onaylayıcı tanımlı değil.
   - Atanan kullanıcı var ama `OnaylayiciAktif = 0` ise → onaylayıcı pasif, göremiyor.
   - Tüm adımlar `ONAYLANDI` ama talep hâlâ `BEKLIYOR` ise → durum güncellenmemiş (bug).
   - `BEKLIYOR` adım sayısını not alın.

## Olası nedenler ve çözümleri
- **Neden:** Onaylayıcı kullanıcı pasife alınmış / işten ayrılmış.
  **Çözüm:** Onay Akışı Tanımları'ndan yedek onaylayıcı atanabilir; ya da adımın atanan
  kullanıcısı aktif bir kişiyle değiştirilir (aşağıdaki script, geliştirici onayı).
- **Neden:** O adımda hiç onaylayıcı tanımlı değil (akış eksik kurulmuş).
  **Çözüm:** Yöneticiden onay akışı tanımını tamamlamasını isteyin.
- **Neden:** Onaylayıcı yanlış filtre/görünüm kullanıyor, talep aslında listede var.
  **Çözüm:** Kullanıcıya "Bana Atananlar" filtresini ve tarih aralığını kontrol ettirin.

## Ne zaman geliştiriciye iletilir
- Tüm adımlar onaylı olduğu halde talep durumu ilerlememişse.
- Onay adımının atanan kullanıcısını ekrandan değiştirmek mümkün değilse.
- İletirken eklenecekler:
  - Müşteri adı
  - Program sürümü
  - Kontrol sorgusunun sonucu / satır sayısı
  - Varsa ekran görüntüsü

### Onay adımını aktif kullanıcıya yeniden atama script'i — SADECE geliştirici onayından sonra
> ⚠ Bu script veri değiştirir. Geliştiriciden onay almadan çalıştırmayın.
> Değiştirmeniz gereken TEK satır: @BeklenenSayi (kontrol sorgusunun bulduğu satır sayısı).

```sql
DECLARE @BeklenenSayi int = NULL;   -- ← yeniden atanacak BEKLIYOR adım sayısı (genelde 1)
SET XACT_ABORT ON;

IF @BeklenenSayi IS NULL
BEGIN
    PRINT 'DURDURULDU: @BeklenenSayi yazılmamış. Önce kontrol sorgusunu çalıştırın.';
    RETURN;
END

DECLARE @Guncellenen int;
DECLARE @FiyatTalepId int = NULL;       -- ← geliştiricinin onayladığı talep
DECLARE @YeniKullaniciId int = NULL;    -- ← yeni (aktif) onaylayıcı

BEGIN TRY
    BEGIN TRAN;

    UPDATE dbo.FiyatOnayAdim
    SET AtananKullaniciId = @YeniKullaniciId
    WHERE FiyatTalepId = @FiyatTalepId
      AND AdimDurum = 'BEKLIYOR';

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
