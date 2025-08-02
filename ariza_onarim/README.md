# Arıza ve Onarım Yönetimi Modülü

Bu modül, Odoo 15 için geliştirilmiş bir arıza ve onarım yönetim sistemidir.

## Özellikler

- Müşteri ürünleri için arıza kaydı
- Mağaza ürünleri için arıza kaydı
- Teknik servis yönetimi
- Otomatik stok transfer işlemleri
- QR kod desteği
- Detaylı raporlama
- Dashboard görünümü

## Kurulum

### GitHub Üzerinden Kurulum

1. Odoo eklentiler klasörüne gidin:
   ```bash
   cd /path/to/odoo/addons
   ```

2. Modülü GitHub'dan klonlayın:
   ```bash
   git clone https://github.com/your-username/ariza_onarim.git
   ```

3. Gerekli Python paketini yükleyin:
   ```bash
   pip install qrcode
   ```

4. Odoo'yu yeniden başlatın

5. Uygulamalar menüsünden modülü yükleyin

### Güncelleme

Modülü güncellemek için:
```bash
cd /path/to/odoo/addons/ariza_onarim
git pull origin main
```

## Kullanım

### Arıza Kaydı Oluşturma

1. "Arıza ve Onarım" menüsüne gidin
2. "Arıza Kayıtları" alt menüsünü seçin
3. "Oluştur" butonuna tıklayın
4. Arıza tipini seçin:
   - Müşteri Ürünü
   - Mağaza Ürünü
   - Teknik Servis

### Müşteri Ürünü Arıza Kaydı

1. Müşteri bilgilerini seçin
2. Sipariş varsa seçin, yoksa "Sipariş Yok" seçeneğini işaretleyin
3. Ürün, marka ve model bilgilerini girin
4. Arıza tanımını yapın
5. Garanti durumunu belirleyin
6. Sorumlu kişiyi seçin

### Mağaza Ürünü Arıza Kaydı

1. Mağaza arıza tipini seçin:
   - Depo Arıza
   - Tedarikçiler
   - Nefesli Arıza
2. Analitik hesabı seçin
3. Gerekli diğer bilgileri girin

### Stok Transfer İşlemleri

- Depo arıza: Otomatik olarak arıza/stok konumuna transfer oluşturulur
- Tedarikçi: Tedarikçiye transfer belgesi oluşturulur
- Nefesli arıza: Nefesli stok konumuna transfer oluşturulur

### QR Kod Kullanımı

- Her arıza kaydı için otomatik QR kod oluşturulur
- QR kodlar form görünümünde görüntülenir
- QR kodları yazdırmak için yazdır butonunu kullanın

### Raporlama

- Pivot tablo görünümü
- Grafik görünümü
- Tarih bazlı filtreler
- Gruplama seçenekleri

## Geliştirme

### Katkıda Bulunma

1. Bu depoyu fork edin
2. Yeni bir branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add some amazing feature'`)
4. Branch'inizi push edin (`git push origin feature/amazing-feature`)
5. Pull Request oluşturun

## Gereksinimler

- Odoo 15
- Python qrcode paketi

## Lisans

LGPL-3

## Geliştirici

**Alper Tofta**

## İletişim

GitHub: [@toftamars](https://github.com/toftamars) 