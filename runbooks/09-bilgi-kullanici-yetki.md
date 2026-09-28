# Kullanıcı yetkisi / rol nereden değiştirilir

Nasıl soruluyor: "Kullanıcıya yetki nasıl veririm?", "Bu ekranı göremiyor, yetki lazım", "Rol değiştireceğim"
Kısa cevap: Yönetim > Kullanıcılar & Roller ekranından ilgili kullanıcı seçilip rolü değiştirilir veya ek yetki (modül/ekran bazında) verilir. Yetkiler role bağlıdır; kullanıcıya değil role izin eklemek daha doğrudur. Kullanıcı, değişiklikten sonra yeniden giriş yaptığında yeni yetkiler geçerli olur.
Programda nerede: Yönetim > Kullanıcılar & Roller > (kullanıcı seç) > Rol / Yetkiler
Detay: Bir kullanıcı yalnızca kendi mağaza grubundaki mağazaları görür; mağaza ya da siparişleri görünmüyorsa yetki değil "Mağaza Grubu" atamasını kontrol edin. Kullanıcının etkin rol ve yetkilerini görmek için:

```sql
SELECT k.KullaniciAdi, r.RolAdi, y.YetkiKodu
FROM dbo.Kullanici k
JOIN dbo.KullaniciRol kr ON kr.KullaniciId = k.KullaniciId
JOIN dbo.Rol r ON r.RolId = kr.RolId
JOIN dbo.RolYetki ry ON ry.RolId = r.RolId
JOIN dbo.Yetki y ON y.YetkiId = ry.YetkiId
WHERE k.KullaniciAdi = @KullaniciAdi
ORDER BY r.RolAdi, y.YetkiKodu;
```
İlgili: [06-fiyat-talebi-onay-akisi-takili.md](06-fiyat-talebi-onay-akisi-takili.md), [08-bilgi-yeni-pazaryeri-magazasi.md](08-bilgi-yeni-pazaryeri-magazasi.md)
Son güncelleme: 2026-09-28
