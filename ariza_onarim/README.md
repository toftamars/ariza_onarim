# Arıza ve Onarım Yönetimi Modülü

Odoo 15 için geliştirilmiş arıza kaydı ve onarım takip modülü.

**Versiyon:** 1.0.5  
**Lisans:** LGPL-3

---

## Özellikler

- Müşteri ve mağaza ürünleri için arıza kaydı
- Teknik servis yönetimi (DTL, NGaudio, MATT Guitar, Tedarikçi vb.)
- Otomatik stok transfer işlemleri
- 3 aşamalı SMS bildirimleri (müşteri ürünleri)
- QR kod desteği
- Garanti takibi
- Detaylı raporlama ve dashboard
- Company bazlı erişim kontrolü

---

## Bağımlılıklar

| Modül | Amaç |
|-------|------|
| base, mail | Temel Odoo |
| stock | Stok transferleri |
| account | Muhasebe entegrasyonu |
| product | Ürün yönetimi |
| product_brand | Marka alanı |
| delivery | Kargo entegrasyonu |
| sms | SMS bildirimleri |
| analytic | Analitik hesap (mağaza/depo) |

**Python:** `qrcode` paketi gerekli.

---

## Kurulum

### 1. Eklentiler klasörüne gidin

```bash
cd /path/to/odoo/addons
```

### 2. Modülü klonlayın

```bash
git clone https://github.com/toftamars/ariza_onarim.git
```

### 3. Python paketini yükleyin

```bash
pip install qrcode
```

### 4. Odoo'yu yeniden başlatın

### 5. Uygulamalar menüsünden modülü yükleyin

---

## Yapılandırma

### Default sürücü ID

Transfer işlemlerinde otomatik atanan sürücü partner ID'si.

- **Parametre:** `ariza_onarim.default_driver_id`
- **Yol:** Settings > Technical > Parameters
- **Varsayılan:** 2205
- **Not:** Test/production ortamlarında farklı değer atayabilirsiniz.

### Stok konumları

Tüm stok konumları (DTL/Stok, Arıza/Stok, NFSL/Arızalı vb.) Odoo sisteminde mevcuttur. Modül konum oluşturmaz; mevcut konumları kullanır.

Modül yüklendikten sonra `post_init_hook` kritik konumları kontrol eder. Eksik varsa Odoo log'una uyarı yazılır.

### Analitik hesaplar (mağaza ürünleri)

Mağaza ürünleri için analitik hesaba `warehouse_id` atanmalı. `konum_kodu` warehouse'dan otomatik hesaplanır.

Alternatif: `ir.config_parameter` ile `ariza_onarim.location_code.[mağaza_adı]` tanımlanabilir.

---

## İş Akışları

### Müşteri ürünü

1. Arıza kaydı oluştur (Taslak)
2. Personel Onayı → İlk SMS, transfer oluşturulur
3. Kabul Edildi
4. Teknik Onarım → Yönetici "Onarım Başlat"
5. Onaylandı → 2. SMS
6. Yönetici Tamamlandı
7. Teslim Et → 3. SMS, transfer oluşturulur
8. Teslim Edildi

### Mağaza ürünü

1. Arıza kaydı oluştur (Taslak)
2. Personel Onayı → Transfer oluşturulur (SMS yok)
3. Kabul Edildi
4. Teknik Onarım → Yönetici "Onarım Başlat"
5. Onaylandı
6. Yönetici Tamamlandı
7. Teslim Al → Geri transfer (Teknik servis → Mağaza)
8. Tamamlandı

---

## Yetkilendirme

| Grup | Yetki |
|------|-------|
| Arıza Onarım / Yönetici | Kayıt yönetimi, onaylama, onarım başlatma |
| Arıza Onarım / Süper Yönetici | Yönetici + kayıt silme |
| base.group_user | Temel okuma/yazma (silme yok) |

---

## Güncelleme

```bash
cd /path/to/odoo/addons/ariza_onarim
git pull origin main
```

Odoo'yu yeniden başlatıp modülü güncelleyin.

---

## Dokümantasyon

- **ARCHITECTURE.md** – Modül mimarisi, modeller, helper'lar
- **SISTEM_RISK_ANALIZI.md** – Risk analizi ve öneriler

---

## Gereksinimler

- Odoo 15
- Python: qrcode

---

## Geliştirici

**Alper Tofta** – [@toftamars](https://github.com/toftamars)
