# SİSTEM RİSK ANALİZİ
## Arıza Onarım Modülü - Ne Zaman Sorun Çıkarır?

**Analiz Tarihi:** Şubat 2025  
**Modül Versiyonu:** 1.0.5  
**Risk Seviyesi:** Orta

---

## 🚨 KRİTİK RİSK SENARYOLARI

### 1. EKSİK STOK KONUMLARI (YÜKSEK RİSK)

**Ne Zaman Sorun Çıkarır:**
- Stok konumları (DTL/Stok, Arıza/Stok, NFSL/Arızalı) Odoo'da tanımlı değilse
- Konum isimleri yanlış yazılmışsa (büyük/küçük harf, boşluk farkı)
- Company bazlı konumlar yanlış company'ye atanmışsa

**Etkilenen İşlemler:**
- ✅ Transfer oluşturma (`_create_stock_transfer`)
- ✅ Hedef konum otomatik belirleme (`_update_hedef_konum`)
- ✅ Mağaza ürünü işlemleri

**Hata Senaryosu:**
```python
# location_helper.py - Satır 38-42
dtl_konum = env['stock.location'].search([
    ('name', '=', LocationNames.DTL_STOK),  # "DTL/Stok" bulunamazsa
    ('company_id', '=', company_id)
], limit=1)
return dtl_konum if dtl_konum else False  # False döner, transfer oluşturulamaz
```

**Sonuç:**
- Transfer oluşturulamaz
- Kullanıcıya hata mesajı gösterilmez (sessizce başarısız olur)
- Arıza kaydı oluşturulur ama transfer oluşmaz

**Çözüm:**
- Tüm konumlar Odoo sisteminde mevcuttur; modül konum oluşturmaz.
- post_init_hook ile konum validasyonu eklendi (v1.0.5) - eksik konum varsa log'a yazılır.

---

### 2. EKSİK ANALİTİK HESAP KONUM KODU (ORTA RİSK)

**Durum:** Analitik Bilgileri.txt dosya bağımlılığı kaldırıldı. Artık `ir.config_parameter` ve `account.analytic.account.konum_kodu` (warehouse'dan otomatik) kullanılıyor.

**Ne Zaman Sorun Çıkarır:**
- `analitik_hesap_id.konum_kodu` field'ı boşsa (warehouse atanmamışsa)
- `ir.config_parameter` ile `ariza_onarim.location_code.[mağaza_adı]` tanımlı değilse

**Etkilenen İşlemler:**
- ✅ Müşteri ürünü için hedef konum belirleme
- ✅ Mağaza ürünü için kaynak konum belirleme

**Hata Senaryosu:**
```python
# location_helper.py - get_konum_kodu_from_analytic
# ir.config_parameter veya analytic.konum_kodu kullanılır
# Dosya bağımlılığı yok
```

**Sonuç:**
- Hedef konum otomatik belirlenemez
- Kullanıcı manuel olarak konum seçmek zorunda kalır
- İşlem devam eder ama otomasyon çalışmaz

**Çözüm:**
- Tüm analitik hesaplara `warehouse_id` atanmalı (konum_kodu otomatik hesaplanır)
- Alternatif: `ir.config_parameter` ile `ariza_onarim.location_code.[mağaza_adı]` tanımlanmalı

---

### 3. EKSİK PARTNER/TEDARİKÇİ BİLGİLERİ (ORTA RİSK)

**Ne Zaman Sorun Çıkarır:**
- Tedarikçi seçilmiş ama `property_stock_supplier` tanımlı değilse
- Partner telefon numarası yoksa (SMS gönderilemez)
- Partner adresi eksikse

**Etkilenen İşlemler:**
- ✅ SMS gönderimi
- ✅ Tedarikçi transfer oluşturma
- ✅ Adres bilgileri

**Hata Senaryosu:**
```python
# ariza.py - Satır 672-675
elif self.teknik_servis == TeknikServis.TEDARIKCI and self.tedarikci_id:
    if self.tedarikci_id.property_stock_supplier:  # None ise
        self.hedef_konum_id = self.tedarikci_id.property_stock_supplier
    # Hedef konum None kalır
```

**Sonuç:**
- Transfer oluşturulamaz veya yanlış konuma oluşturulur
- SMS gönderilemez (sessizce başarısız olur)

**Çözüm:**
- Tedarikçi partner'lere `property_stock_supplier` atanmalı
- SMS gönderiminde hata kontrolü var (iyi)

---

### 4. EKSİK SEQUENCE TANIMI (DÜŞÜK RİSK)

**Ne Zaman Sorun Çıkarır:**
- `ir.sequence` tanımı yoksa veya silinmişse
- Sequence kodu yanlışsa

**Etkilenen İşlemler:**
- ✅ Arıza numarası oluşturma

**Hata Senaryosu:**
```python
# sequence_helper.py - Satır 29
sequence_number = env['ir.sequence'].next_by_code(model_name)
if sequence_number:  # None ise
    return sequence_number
# Fallback: Manuel numara oluşturulur
```

**Sonuç:**
- Sequence bulunamazsa manuel numara oluşturulur
- İşlem devam eder (fallback mekanizması var - iyi)

**Çözüm:**
- Sequence tanımı kontrol edilmeli
- Fallback mekanizması çalışıyor (iyi)

---

### 5. EKSİK GRUP: `group_ariza_technician` (KULLANILMIYOR)

**Durum:** Teknisyen grubu kullanılmıyor. Onarım başlatma sadece `group_ariza_manager` ile yapılıyor.

**Etkilenen İşlemler:**
- `can_start_repair` computed field
- `action_onarim_baslat` metodu

---

### 6. SMS GÖNDERİM HATALARI (ORTA RİSK)

**Ne Zaman Sorun Çıkarır:**
- SMS modülü yüklü değilse
- SMS gateway yapılandırılmamışsa
- Partner telefon numarası yanlış formattaysa

**Etkilenen İşlemler:**
- ✅ Tüm SMS gönderimleri (3 aşamalı)

**Hata Senaryosu:**
```python
# sms_helper.py - Satır 37-42
sms = env['sms.sms'].create({
    'number': partner.phone,
    'body': message,
    'partner_id': partner.id,
})
sms.send()  # Hata olursa exception fırlatılır
```

**Sonuç:**
- SMS gönderilemez
- Exception yakalanır, log'a yazılır
- İşlem devam eder (SMS olmadan)

**Çözüm:**
- SMS modülü ve gateway yapılandırması kontrol edilmeli
- Hata yakalama mekanizması var (iyi)

---

### 7. STOK TRANSFER OLUŞTURMA HATALARI (YÜKSEK RİSK)

**Ne Zaman Sorun Çıkarır:**
- Kaynak veya hedef konum None ise
- Warehouse veya picking type bulunamazsa
- Ürün stokta yoksa
- Transfer validation kuralları ihlal edilirse

**Etkilenen İşlemler:**
- ✅ Tüm transfer oluşturma işlemleri

**Hata Senaryosu:**
```python
# ariza.py - Satır 1192
picking = self.env['stock.picking'].sudo().create(picking_vals)
# Eğer picking_vals'da eksik/yanlış veri varsa
# ValidationError veya IntegrityError fırlatılır
```

**Sonuç:**
- Transfer oluşturulamaz
- Kullanıcıya hata mesajı gösterilir
- Arıza kaydı oluşturulur ama transfer oluşmaz

**Çözüm:**
- Transfer oluşturmadan önce tüm validasyonlar yapılmalı
- Hata mesajları kullanıcı dostu olmalı

---

### 8. COMPUTED FIELD DEPENDENCY EKSİKLİĞİ (DÜŞÜK RİSK)

**Ne Zaman Sorun Çıkarır:**
- Computed field'ların dependency'leri eksikse
- İlişkili field'lar değiştiğinde computed field güncellenmezse

**Etkilenen İşlemler:**
- ✅ `kalan_is_gunu` hesaplama
- ✅ `musteri_gosterim` hesaplama
- ✅ `beklenen_tamamlanma_tarihi` hesaplama

**Hata Senaryosu:**
```python
# ariza.py - Satır 561
@api.depends('onarim_baslangic_tarihi', 'beklenen_tamamlanma_tarihi')
def _compute_kalan_is_gunu(self):
    # Eğer dependency eksikse, field güncellenmez
```

**Sonuç:**
- Computed field'lar yanlış değer gösterir
- Kullanıcı yanlış bilgi görür
- İşlem devam eder ama veri tutarsızlığı olur

**Çözüm:**
- Tüm computed field dependencies kontrol edilmeli
- Test senaryoları ile doğrulanmalı

---

### 9. DOSYA OKUMA HATALARI (ARTIK GEÇERLİ DEĞİL)

**Durum:** `Analitik Bilgileri.txt` dosya bağımlılığı kaldırıldı. Konum kodu artık `ir.config_parameter` ve `account.analytic.account.konum_kodu` üzerinden alınıyor.

---

### 10. MULTI-COMPANY SORUNLARI (ORTA RİSK)

**Ne Zaman Sorun Çıkarır:**
- Multi-company aktifse
- Company bazlı konumlar yanlış company'ye atanmışsa
- Kullanıcı yanlış company'de çalışıyorsa

**Etkilenen İşlemler:**
- ✅ Tüm konum arama işlemleri
- ✅ Transfer oluşturma

**Hata Senaryosu:**
```python
# location_helper.py - Satır 38-41
dtl_konum = env['stock.location'].search([
    ('name', '=', LocationNames.DTL_STOK),
    ('company_id', '=', company_id)  # Yanlış company ise bulunamaz
], limit=1)
```

**Sonuç:**
- Konumlar bulunamaz
- Transfer oluşturulamaz
- Company bazlı record rules çalışır (iyi)

**Çözüm:**
- Company bazlı kontroller var (iyi)
- Ancak company yapılandırması doğru olmalı

---

## 📊 RİSK ÖNCELİK MATRİSİ

| Risk | Öncelik | Etki | Olasılık | Çözüm Süresi |
|------|---------|------|----------|--------------|
| Eksik Stok Konumları | 🟡 AZALTILDI | Yüksek | Orta | post_init_hook ile log |
| Eksik Grup (technician) | ✅ KULLANILMIYOR | - | - | Sadece manager |
| SMS Gönderim Hataları | 🟡 ORTA | Orta | Düşük | 2 saat |
| Transfer Oluşturma Hataları | 🔴 YÜKSEK | Yüksek | Düşük | 4 saat |
| Eksik Analitik Hesap Kodu | 🟡 ORTA | Düşük | Orta | 1 saat |
| Multi-Company Sorunları | 🟡 ORTA | Orta | Düşük | 2 saat |
| Computed Field Dependency | 🟢 DÜŞÜK | Düşük | Düşük | 3 saat |
| Dosya Okuma Hataları | ✅ KALDIRILDI | - | - | Dosya bağımlılığı yok |

---

## 🎯 EN KRİTİK 3 SORUN

### 1. Eksik Stok Konumları (AZALTILDI - post_init_hook)
**Ne Zaman:** Konumlar Odoo'da tanımlı değilse (nadir)  
**Etki:** Transfer oluşturulamaz, işlemler yarıda kalır  
**Çözüm:** Konumlar Odoo sisteminde mevcuttur; modül konum oluşturmaz. post_init_hook eksik varsa log'a yazar.

### 2. group_ariza_technician (KULLANILMIYOR)
**Durum:** Teknisyen grubu kullanılmıyor; sadece yönetici (manager) onarım başlatabilir.

### 3. Transfer Oluşturma Hataları (YÜKSEK RİSK)
**Ne Zaman:** Kaynak/hedef konum None ise veya validation kuralları ihlal edilirse  
**Etki:** Transfer oluşturulamaz, arıza kaydı yarıda kalır  
**Çözüm:** Transfer öncesi validasyon kontrolü yapılmalı

---

## ✅ ÖNERİLER

### Acil (Production Öncesi)
1. Stok konumları Odoo'da mevcuttur; modül konum oluşturmaz. Sorun olursa post_init_hook log'unu kontrol edin.
2. Teknisyen grubu kullanılmıyor; sadece manager onarım başlatır
3. Transfer oluşturma validasyonlarını güçlendir

### Kısa Vadeli (1 Hafta)
1. ✅ SMS gateway yapılandırmasını kontrol et
2. ✅ Tüm analitik hesaplara `konum_kodu` ekle
3. ✅ Computed field dependencies'lerini kontrol et

### Uzun Vadeli (1 Ay)
1. ✅ Test coverage ekle
2. ✅ Error monitoring ekle (Sentry)
3. ✅ Performance monitoring ekle

---

## 📝 SONUÇ

Sistem **çoğunlukla güvenli** ancak **kritik bağımlılıklar** var:
- Stok konumları Odoo sisteminde mevcuttur (modül oluşturmaz)
- Grup yapılandırması düzeltilmeli
- Transfer validasyonları güçlendirilmeli

**En büyük risk:** Eksik stok konumları nedeniyle transfer oluşturulamaması. Konumlar Odoo'da mevcuttur; modül konum oluşturmaz.

---

## YENİ RİSKLER (v1.0.5 Güncellemesi)

### Odoo Sürüm Bağımlılığı
- Modül Odoo 15 için yazıldı. Odoo 16/17/18 geçişinde API değişiklikleri sorun çıkarabilir.
- `stock_move_line.py` Odoo 16+ uyumluluğu için `location_lot_ids` ekliyor.

### Hardcoded Default Driver ID (2205)
- `ariza_constants.py` ve `system_parameters.xml`'de fallback değer.
- Farklı ortamlarda Settings > Technical > Parameters ile `ariza_onarim.default_driver_id` güncellenmeli.

### Teknik Servis Sabitleri
- NGaudio, MATT Guitar vb. adres/telefon koda gömülü. Yeni servis eklemek için kod değişikliği gerekiyor.
- Öneri: Config tabanlı yapıya taşınması (ariza.teknik_servis.config veya ir.config_parameter).

### Fat Model (ariza.py ~2540 satır)
- Tek dosyada çok fazla sorumluluk; değişiklikler yan etki riski taşıyor.
- Öneri: Domain/servis katmanına bölme.

### Test Eksikliği
- Unit/integration test yok; regression riski yüksek.

---

**Rapor Hazırlayan:** AI Risk Analyst  
**Tarih:** Şubat 2025  
**Versiyon:** 1.1

---

## İlgili Dokümantasyon

- **ariza_onarim/README.md** – Kurulum, yapılandırma, iş akışları
- **ariza_onarim/ARCHITECTURE.md** – Modül mimarisi, modeller, helper'lar

