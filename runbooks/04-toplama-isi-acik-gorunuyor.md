# Depo toplama işi tamamlandı ama açık görünüyor

## Belirti
- Kullanıcı / müşteri ne görüyor?
  - Depo personeli ürünleri el terminaliyle okutup paketlediğini söylüyor, ama panelde
    toplama işi hâlâ "Toplanıyor" / "Açık" görünüyor.
  - Sipariş bir sonraki adıma (Paketleme / Kargoya Hazır) geçmiyor; gecikenler listesinde
    kırmızı duruyor.
- Destek ekibi bu sorunu nasıl tanır?
  - El terminalinden gelen okutma kayıtları merkeze ulaşmamış (`dbo.TerminalSenkron`
    tablosunda `BEKLIYOR` ya da `HATA`).
  - Ya da okutmalar gelmiş ama işin durumu `ACIK` kalmış.
- Nasıl soruluyor: "Topladık ama açık görünüyor", "El terminalindeki işler panele gelmedi",
  "Sipariş paketlemeye geçmiyor"

## Etkilenen modül
- Depo > Toplama İşleri
- Depo > El Terminali Senkronizasyonu
- İlgili tablolar: `dbo.ToplamaIsi`, `dbo.ToplamaSatir`, `dbo.TerminalSenkron`, `dbo.Depo`

## Kontrol adımları
1. **Program sürümüne bakın.** 5.0 öncesinde el terminali kablosuz ağdan düştüğünde biriken
   okutmalar yeniden bağlanınca otomatik gönderilmiyordu; 5.0'da otomatik yeniden gönderim eklendi.
2. **Toplama işinin durumunu ve satırlarını kontrol edin.** Bu sorgu sadece okuma yapar,
   hiçbir şeyi değiştirmez.

```sql
   SELECT ti.ToplamaIsiId, ti.IsNo, ti.Durum AS IsDurum,
          ts.UrunKodu, ts.IstenenAdet, ts.OkutulanAdet, ts.OkutmaZamani
   FROM dbo.ToplamaIsi ti
   JOIN dbo.ToplamaSatir ts ON ts.ToplamaIsiId = ti.ToplamaIsiId
   JOIN dbo.Depo d ON d.DepoId = ti.DepoId
   WHERE d.DepoKodu = @DepoKodu
     AND ti.IsNo = @IsNo
   ORDER BY ts.UrunKodu;
```

3. **El terminalinden gelen son senkron kayıtlarına bakın.**

```sql
   SELECT tsn.TerminalKodu, tsn.Durum, tsn.KayitSayisi,
          tsn.GonderimZamani, tsn.HataMesaji
   FROM dbo.TerminalSenkron tsn
   JOIN dbo.Depo d ON d.DepoId = tsn.DepoId
   WHERE d.DepoKodu = @DepoKodu
   ORDER BY tsn.GonderimZamani DESC;
```

4. **Sonucu okuyun.**
   - Senkron kaydı `BEKLIYOR` / `HATA` ise → okutmalar merkeze hiç gelmemiş.
   - Tüm satırlarda `OkutulanAdet = IstenenAdet` ama `IsDurum = 'ACIK'` ise → iş kapatılmamış (bug).
   - Bazı satırlarda `OkutulanAdet < IstenenAdet` ise → gerçekten eksik toplama var, depoyla teyit edin.
   - `ACIK` kalan iş sayısını not alın.

## Olası nedenler ve çözümleri
- **Neden:** El terminali ağdan düşmüş, okutmalar cihazda bekliyor.
  **Çözüm:** Depo personelinden terminalde "Senkronize Et" demesini isteyin.
- **Neden:** Okutmalar gelmiş ama iş durumu otomatik kapanmamış.
  **Çözüm:** İşin kapatılması gerekir (aşağıdaki script, geliştirici onayı).
- **Neden:** Bir ürün yanlış barkodla okutulmuş, satır eksik görünüyor.
  **Çözüm:** Depo personeli ilgili satırı terminalde doğru barkodla tekrar okutmalı.

## Ne zaman geliştiriciye iletilir
- Senkron yapıldığı halde okutmalar gelmiyorsa.
- Tüm satırlar tam okutulmuş ama iş açık kalıyorsa.
- İletirken eklenecekler:
  - Müşteri adı
  - Program sürümü
  - Kontrol sorgusunun sonucu / satır sayısı
  - Varsa ekran görüntüsü

### Tamamlanmış toplama işini "açık" durumdan kapatma script'i — SADECE geliştirici onayından sonra
> ⚠ Bu script veri değiştirir. Geliştiriciden onay almadan çalıştırmayın.
> Değiştirmeniz gereken TEK satır: @BeklenenSayi (kapatılacak iş sayısı, genelde 1).

```sql
DECLARE @BeklenenSayi int = NULL;   -- ← kapatılacak ACIK iş sayısı
SET XACT_ABORT ON;

IF @BeklenenSayi IS NULL
BEGIN
    PRINT 'DURDURULDU: @BeklenenSayi yazılmamış. Önce kontrol sorgusunu çalıştırın.';
    RETURN;
END

DECLARE @Guncellenen int;
DECLARE @ToplamaIsiId int = NULL;   -- ← geliştiricinin onayladığı iş

BEGIN TRY
    BEGIN TRAN;

    UPDATE dbo.ToplamaIsi
    SET Durum = 'TAMAMLANDI',
        TamamlanmaZamani = SYSDATETIME()
    WHERE ToplamaIsiId = @ToplamaIsiId
      AND Durum = 'ACIK'
      AND NOT EXISTS (
            SELECT 1 FROM dbo.ToplamaSatir ts
            WHERE ts.ToplamaIsiId = @ToplamaIsiId
              AND ts.OkutulanAdet < ts.IstenenAdet
      );

    SET @Guncellenen = @@ROWCOUNT;

    IF @Guncellenen = @BeklenenSayi
    BEGIN
        COMMIT;
        PRINT 'TAMAM: ' + CAST(@Guncellenen AS varchar(10)) + ' kayıt kapatıldı.';
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
