# (soru, doğru dosya) çiftleri. Soruları destek ekibinin diliyle yaz.
# Kurgusal set: Siparion (e-ticaret sipariş yönetimi). Başlık kelimeleri bilerek kullanılmadı.
TESTS = [
    ("musteri paketim nerde diyo ama sistemde gonderi kodu bos gorunuyo", "01-kargo-takip-no-dusmuyor.md"),
    ("pazaryerine yola cikti bilgisi gitmemis satici panelinde hala hazirlaniyor yaziyo", "01-kargo-takip-no-dusmuyor.md"),
    ("Menzilo entegrasyonu dunden beri cevap vermiyo galiba barkod olusmadi", "01-kargo-takip-no-dusmuyor.md"),
    ("müşteri ürünü geri yolladı ama para ödemesini bitiremiyoruz teslim alınmamış kalem diyo", "02-iade-kapanmiyor-tutar-yanlis.md"),
    ("geri ödenecek para olması gerekenin yarısı çıkmış müşteri kızgın", "02-iade-kapanmiyor-tutar-yanlis.md"),
    ("adam 2 tane aldı 3 tane geri gönderdi girilmiş hesap saçma çıkıyo", "02-iade-kapanmiyor-tutar-yanlis.md"),
    ("indirim kodunun bitişini ay sonuna çektik ama sepette gecersiz diyo", "03-kupon-suresi-dolmus-gorunuyor.md"),
    ("promosyon kodu bazi musterilerde calisiyo bazilarinda calismiyo iki tane ayni kod mu var", "03-kupon-suresi-dolmus-gorunuyor.md"),
    ("%20 kodunu giren tarihi gecmis hatasi aliyo panelde tarih ileri alinmis gorunuyo", "03-kupon-suresi-dolmus-gorunuyor.md"),
    ("el terminaliyle okuttuk paketledik ama panelde hala toplaniyo yaziyo", "04-toplama-isi-acik-gorunuyor.md"),
    ("barkod tabancasi wifi dan dustu galiba yapilan okutmalar merkeze gelmemis", "04-toplama-isi-acik-gorunuyor.md"),
    ("raf personeli bitirdik dedi ama siparis paketleme adimina gecmiyo", "04-toplama-isi-acik-gorunuyor.md"),
    ("mavi tişört M beden eksi 3 adet görünüyo nasıl olur", "05-urun-stok-negatif.md"),
    ("ayni pazaryeri siparisi iki kere dusmus galiba mal ikiye katlanarak azalmis", "05-urun-stok-negatif.md"),
    ("rafta 10 tane var ama sistem -2 gösterip satışa kapattı", "05-urun-stok-negatif.md"),
    ("etiket guncelleme istegi 5 gundur ayni adimda bekliyo", "06-fiyat-talebi-onay-akisi-takili.md"),
    ("zam listesini yolladim mudure dusmedi o da gecen ay istifa etmisti", "06-fiyat-talebi-onay-akisi-takili.md"),
    ("yeni tarife siteye yansımadı kimin masasında bekliyo bilmiyoruz", "06-fiyat-talebi-onay-akisi-takili.md"),
    ("siparisleri kac saatte gonderdigimizi aylik gormek istiyorum", "07-bilgi-kargo-sla-raporu.md"),
    ("48 saat kuralını aşan siparişler hangileri nasıl bakarım", "07-bilgi-kargo-sla-raporu.md"),
    ("pazaryeri geç sevkiyat cezası kesti geciken paketlerin listesini excel almam lazım", "07-bilgi-kargo-sla-raporu.md"),
    ("Çarşıvera'da ikinci dükkan açtık programa nasıl tanıtırım", "08-bilgi-yeni-pazaryeri-magazasi.md"),
    ("satici ID zaten kayitli diyo kaydetmiyo", "08-bilgi-yeni-pazaryeri-magazasi.md"),
    ("eklediğim satış kanalı listede çıkmıyo siparişleri de gelmiyo", "08-bilgi-yeni-pazaryeri-magazasi.md"),
    ("yeni başlayan arkadaşa geri ödemeler ekranını açmam lazım", "09-bilgi-kullanici-yetki.md"),
    ("calisan raporlar menusunu goremiyo erisim verelim", "09-bilgi-kullanici-yetki.md"),
    ("stajyerin hesabina tam admin haklari tanimlamak istiyorum", "09-bilgi-kullanici-yetki.md"),
    ("müşteri alışveriş özetini istiyo dosya olarak mail atcam nasıl indiririm", "10-bilgi-siparis-dokumu-pdf.md"),
    ("yazdırdığım belgede taslak yazısı çıkıyo neden", "10-bilgi-siparis-dokumu-pdf.md"),
    ("paket içeriği ve gönderi bilgisi olan sayfayı yazıcıdan almak istiyorum", "10-bilgi-siparis-dokumu-pdf.md"),
]

AMBIGUOUS = [
    ("her seyi yaptik ama hala bekliyo, urunler de depoya ulasti", "02-iade-kapanmiyor-tutar-yanlis.md"),
    ("yonetici ekraninda gozukmuyo, erisimi mi yok acaba", "06-fiyat-talebi-onay-akisi-takili.md"),
]
