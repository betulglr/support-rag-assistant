# Destek Ekibi Runbook & Bilgi Notu Kütüphanesi

Bu klasör, **Siparion** (kurgusal e-ticaret sipariş yönetim yazılımı) destek ekibi için
hazırlanmış runbook (sorun çözüm rehberi) ve bilgi notlarını içerir.

> ⚠ Buradaki tüm müşteri adları, pazaryeri ve kargo firması adları, sürüm numaraları, tablo
> ve ekran isimleri **kurgusaldır**. Gerçek bir sistemde çalıştırmadan önce kendi şemanıza uyarlayın.

## Genel kurallar

1. **Önce kontrol sorgusu.** Hiçbir veri değiştiren script, kontrol sorgusu çalıştırılıp
   satır sayısı doğrulanmadan çalıştırılmaz.
2. **`@BeklenenSayi`** her zaman kontrol sorgusunun bulduğu satır sayısıdır. Uyuşmazlık
   olursa script kendini geri alır (ROLLBACK).
3. **Veri değiştiren scriptler yalnızca geliştirici onayından sonra çalıştırılır.**
4. Geliştiriciye ileterken her zaman: müşteri adı, program sürümü, kontrol sorgusu sonucu
   / satır sayısı ve varsa ekran görüntüsü eklenir.

## İçindekiler

### Sorun runbookları
```
#    Konu                                                      Dosya
--   -------------------------------------------------------   ------------------------------------
01   Kargo takip numarası siparişe düşmüyor                    01-kargo-takip-no-dusmuyor.md
02   İade kaydı kapanmıyor / iade tutarı yanlış hesaplanıyor   02-iade-kapanmiyor-tutar-yanlis.md
03   Kampanya kuponu süresi dolmuş görünüyor (ama uzatılmış)   03-kupon-suresi-dolmus-gorunuyor.md
04   Depo toplama işi tamamlandı ama açık görünüyor            04-toplama-isi-acik-gorunuyor.md
05   Ürün stoğu negatif çıkıyor                                05-urun-stok-negatif.md
06   Toplu fiyat değişikliği talebi onay akışında takılı       06-fiyat-talebi-onay-akisi-takili.md
```

### Bilgi notları
```
#    Konu                                               Dosya
--   ------------------------------------------------   -----------------------------------
07   Kargoya verme süresi (SLA) raporu nereden alınır   07-bilgi-kargo-sla-raporu.md
08   Yeni pazaryeri mağazası nasıl bağlanır             08-bilgi-yeni-pazaryeri-magazasi.md
09   Kullanıcı yetkisi / rol nereden değiştirilir       09-bilgi-kullanici-yetki.md
10   Sipariş dökümünün PDF çıktısı nasıl alınır         10-bilgi-siparis-dokumu-pdf.md
```

## Son güncelleme
2026-09-28
