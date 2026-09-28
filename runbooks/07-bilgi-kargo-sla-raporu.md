# Kargoya verme süresi (SLA) raporu nereden alınır

Nasıl soruluyor: "SLA raporunu nereden alacağım?", "Geciken gönderilerin dökümü nasıl çıkar?", "Pazaryeri denetimine sevk süresi listesi lazım"
Kısa cevap: Raporlar > Operasyon > Kargoya Verme Süresi ekranından mağaza ve dönem seçilip "Rapor Oluştur" denir. Rapor, seçilen ay için her siparişin onaydan kargoya verilene kadar geçen süresini ve SLA ihlallerini gösterir. PDF veya Excel olarak dışa aktarılabilir.
Programda nerede: Raporlar > Operasyon > Kargoya Verme Süresi (Mağaza + Ay/Dönem + "Rapor Oluştur")
Detay: İhlaller kırmızı işaretlenir (sipariş onayından sonra en geç 48 saatte kargoya verme / haftalık ortalama en fazla 24 saat kuralı). Bir siparişin kargoya verme zamanı eksikse o satır raporda "Veri Yok" görünür; önce kargo entegrasyonu tarafı tamamlanmalıdır. Kontrol için:

```sql
SELECT s.SiparisNo, s.OnayZamani, s.KargoyaVermeZamani,
       DATEDIFF(hour, s.OnayZamani, s.KargoyaVermeZamani) AS GecenSaat
FROM dbo.Siparis s
JOIN dbo.Magaza m ON m.MagazaId = s.MagazaId
WHERE m.MagazaKodu = @MagazaKodu
  AND s.OnayZamani BETWEEN @Baslangic AND @Bitis
ORDER BY GecenSaat DESC;
```
İlgili: [01-kargo-takip-no-dusmuyor.md](01-kargo-takip-no-dusmuyor.md)
Son güncelleme: 2026-09-28
