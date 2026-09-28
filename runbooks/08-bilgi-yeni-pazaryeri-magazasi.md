# Yeni pazaryeri mağazası nasıl bağlanır

Nasıl soruluyor: "Yeni mağaza nasıl eklerim?", "Çarşıvera hesabımızı bağlayacağım", "Satış kanalı tanımlama"
Kısa cevap: Tanımlar > Satış Kanalları > Mağazalar ekranında "Yeni" ile mağaza kartı açılır; pazaryeri, satıcı ID, mağaza adı ve API anahtarı zorunludur. Kart kaydedildikten sonra mağaza otomatik olarak "Aktif" olur ve modüllerde (Siparişler, Stok, Fiyat) görünmeye başlar. Satıcı ID benzersizdir; aynı satıcı ID ikinci kez eklenemez.
Programda nerede: Tanımlar > Satış Kanalları > Mağazalar > "Yeni"
Detay: Mağaza eklendikten sonra stokların pazaryerine gitmesi için ürün eşleştirme şablonu atanmalıdır (Tanımlar > Satış Kanalları > Mağazalar > Ürün Eşleştirme). Kaydettikten sonra listede görünmüyorsa filtreyi "Tümü / Aktif" olarak kontrol edin. Aynı satıcı ID var mı kontrolü:

```sql
SELECT MagazaId, MagazaAdi, PazaryeriKodu, SaticiId, Aktif
FROM dbo.Magaza
WHERE SaticiId = @SaticiId;
```
İlgili: [01-kargo-takip-no-dusmuyor.md](01-kargo-takip-no-dusmuyor.md), [09-bilgi-kullanici-yetki.md](09-bilgi-kullanici-yetki.md)
Son güncelleme: 2026-09-28
