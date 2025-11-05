# ARİZA ONARIM MODÜLÜ - YAPILACAKLAR LİSTESİ

**Oluşturulma Tarihi:** 2025-01-XX  
**Kaynak:** Teknik Denetim Raporu + Modüler Yapı Denetim Raporu  
**Toplam Öncelikli Görev:** 25+  
**Tahmini Süre:** 3-4 ay (fazlara bölünmüş)

---

## 🔴 FAZ 1: ACİL VE KRİTİK SORUNLAR (1-2 Hafta)

### 1.1 Dosya Yapısı Refactoring

#### ✅ Görev 1.1.1: `ariza.py` Dosyasını Böl
- **Öncelik:** 🔴 KRİTİK
- **Durum:** Beklemede
- **Açıklama:** 1,859 satırlık dosyayı 6-8 ayrı dosyaya böl
- **Tahmini Süre:** 3-4 gün
- **Dosyalar:**
  - [ ] `models/ariza_kayit.py` - Ana model (fields, basic methods) ~200 satır
  - [ ] `models/ariza_kayit_state.py` - State management ~150 satır
  - [ ] `models/ariza_kayit_sms.py` - SMS işlemleri ~200 satır
  - [ ] `models/ariza_kayit_transfer.py` - Transfer oluşturma ~400 satır
  - [ ] `models/ariza_kayit_compute.py` - Computed fields ~300 satır
  - [ ] `models/ariza_kayit_onchange.py` - Onchange metodları ~400 satır
  - [ ] `models/ariza_kayit_actions.py` - Action metodları ~200 satır

#### ✅ Görev 1.1.2: Inherit Sınıfları Ayrı Dosyalara Taşı
- **Öncelik:** 🔴 KRİTİK
- **Durum:** Beklemede
- **Açıklama:** `ariza.py` içindeki inherit sınıfları ayrı dosyalara taşı
- **Tahmini Süre:** 1 gün
- **Dosyalar:**
  - [ ] `models/account_analytic_account.py` - AccountAnalyticAccount inherit
  - [ ] `models/delivery_carrier.py` - DeliveryCarrier inherit (yeni)
  - [x] `models/stock_picking.py` - StockPicking inherit (zaten var)

### 1.2 Constants ve Configuration

#### ✅ Görev 1.2.1: Constants Dosyası Oluştur
- **Öncelik:** 🟡 YÜKSEK
- **Durum:** Beklemede
- **Açıklama:** Magic string'leri constants dosyasına taşı
- **Tahmini Süre:** 1 gün
- **Dosya:** `models/ariza_constants.py`
- **İçerik:**
  - [ ] `ArizaStates` sınıfı (tüm state'ler)
  - [ ] `TeknikServis` sınıfı (teknik servis seçenekleri)
  - [ ] `ArizaTipi` sınıfı (arıza tipi seçenekleri)
  - [ ] `IslemTipi` sınıfı (işlem tipi seçenekleri)
  - [ ] `TransferMetodu` sınıfı (transfer metodu seçenekleri)
  - [ ] `TeslimAlan` sınıfı (teslim alan seçenekleri)

#### ✅ Görev 1.2.2: Hardcoded ID'leri System Parameter'a Taşı
- **Öncelik:** 🟡 YÜKSEK
- **Durum:** Beklemede
- **Açıklama:** ID 2205 (default driver) gibi hardcoded değerleri system parameter'a taşı
- **Tahmini Süre:** 0.5 gün
- **Yapılacaklar:**
  - [ ] System parameter oluştur: `ariza_onarim.default_driver_id`
  - [ ] `ariza.py` içindeki tüm hardcoded ID referanslarını bul
  - [ ] System parameter kullanımına geçir

### 1.3 Metod Refactoring (Kritik Uzun Metodlar)

#### ✅ Görev 1.3.1: `_create_stock_transfer` Metodunu Böl
- **Öncelik:** 🔴 KRİTİK
- **Durum:** Beklemede
- **Açıklama:** ~300 satırlık metodu 5-6 küçük metoda böl
- **Tahmini Süre:** 2 gün
- **Alt Metodlar:**
  - [ ] `_prepare_transfer_vals()` - Transfer vals hazırlama
  - [ ] `_get_source_location()` - Kaynak konum belirleme
  - [ ] `_get_dest_location()` - Hedef konum belirleme
  - [ ] `_create_picking()` - Picking oluşturma
  - [ ] `_create_move_lines()` - Move line'ları oluşturma
  - [ ] `_assign_driver()` - Sürücü atama

#### ✅ Görev 1.3.2: `action_personel_onayla` Metodunu Böl
- **Öncelik:** 🔴 KRİTİK
- **Durum:** Beklemede
- **Açıklama:** ~200 satırlık metodu 3-4 küçük metoda böl
- **Tahmini Süre:** 1.5 gün
- **Alt Metodlar:**
  - [ ] `_validate_personel_onay()` - Validasyon
  - [ ] `_create_first_transfer()` - İlk transfer oluşturma
  - [ ] `_send_first_sms()` - İlk SMS gönderimi
  - [ ] `_update_state()` - State güncelleme

#### ✅ Görev 1.3.3: `create` Metodunu Böl
- **Öncelik:** 🟡 YÜKSEK
- **Durum:** Beklemede
- **Açıklama:** ~80 satırlık metodu 2-3 küçük metoda böl
- **Tahmini Süre:** 1 gün
- **Alt Metodlar:**
  - [ ] `_prepare_create_vals()` - Create vals hazırlama
  - [ ] `_set_default_values()` - Default değerleri ayarlama
  - [ ] `_validate_create_data()` - Validasyon

---

## 🟡 FAZ 2: ORTA ÖNCELİKLİ İYİLEŞTİRMELER (1 Ay)

### 2.1 Helper Sınıfları

#### ✅ Görev 2.1.1: Helper Sınıfları Oluştur
- **Öncelik:** 🟡 YÜKSEK
- **Durum:** Beklemede
- **Açıklama:** Ortak kullanılan helper metodları ayrı sınıflara taşı
- **Tahmini Süre:** 3 gün
- **Dosyalar:**
  - [ ] `models/ariza_helpers/__init__.py`
  - [ ] `models/ariza_helpers/location_helper.py` - Konum helper metodları
  - [ ] `models/ariza_helpers/partner_helper.py` - Partner helper metodları
  - [ ] `models/ariza_helpers/sequence_helper.py` - Sequence helper metodları
  - [ ] `models/ariza_helpers/sms_helper.py` - SMS helper metodları
  - [ ] `models/ariza_helpers/transfer_helper.py` - Transfer helper metodları

### 2.2 Service Layer

#### ✅ Görev 2.2.1: Service Layer Oluştur
- **Öncelik:** 🟡 YÜKSEK
- **Durum:** Beklemede
- **Açıklama:** Business logic'i service katmanına taşı
- **Tahmini Süre:** 4 gün
- **Dosyalar:**
  - [ ] `services/__init__.py`
  - [ ] `services/sms_service.py` - SMS gönderim servisi
  - [ ] `services/transfer_service.py` - Transfer oluşturma servisi
  - [ ] `services/notification_service.py` - Bildirim servisi (gerekirse)

### 2.3 Kod Kalitesi İyileştirmeleri

#### ✅ Görev 2.3.1: Try-Except Bloklarını İyileştir
- **Öncelik:** 🟡 ORTA
- **Durum:** Beklemede
- **Açıklama:** Pass kullanılan yerleri loglama ile değiştir, merkezi hata yönetimi
- **Tahmini Süre:** 2 gün
- **Yapılacaklar:**
  - [ ] Tüm `pass` kullanan except bloklarını bul
  - [ ] Uygun log mesajları ekle
  - [ ] Merkezi exception handler oluştur (gerekirse)

#### ✅ Görev 2.3.2: Magic Number'ları Constants'a Taşı
- **Öncelik:** 🟡 ORTA
- **Durum:** Beklemede
- **Açıklama:** Kodda geçen sayısal değerleri constants'a taşı
- **Tahmini Süre:** 1 gün
- **Yapılacaklar:**
  - [ ] Garanti hesaplama değerleri
  - [ ] SMS limit değerleri
  - [ ] Deadline değerleri

#### ✅ Görev 2.3.3: Duplicate Kodları Temizle
- **Öncelik:** 🟡 ORTA
- **Durum:** Beklemede
- **Açıklama:** Tekrar eden kod bloklarını helper metodlara taşı
- **Tahmini Süre:** 2 gün

---

## 🟢 FAZ 3: UZUN VADELİ İYİLEŞTİRMELER (2-3 Ay)

### 3.1 Test Coverage

#### ✅ Görev 3.1.1: Unit Testler Ekle
- **Öncelik:** 🟢 ORTA
- **Durum:** Beklemede
- **Açıklama:** Her modül için unit testler yaz
- **Tahmini Süre:** 1 hafta
- **Test Dosyaları:**
  - [ ] `tests/__init__.py`
  - [ ] `tests/test_ariza_kayit.py` - Ana model testleri
  - [ ] `tests/test_ariza_kayit_state.py` - State management testleri
  - [ ] `tests/test_ariza_kayit_sms.py` - SMS testleri
  - [ ] `tests/test_ariza_kayit_transfer.py` - Transfer testleri
  - [ ] `tests/test_helpers.py` - Helper testleri
  - [ ] `tests/test_services.py` - Service testleri

### 3.2 Dokümantasyon

#### ✅ Görev 3.2.1: Dokümantasyon İyileştir
- **Öncelik:** 🟢 ORTA
- **Durum:** Beklemede
- **Açıklama:** Kod içi dokümantasyon ve README güncelle
- **Tahmini Süre:** 2 gün
- **Yapılacaklar:**
  - [ ] Her metod için docstring ekle/güncelle (Google style)
  - [ ] README.md dosyası oluştur/güncelle
  - [ ] API dokümantasyonu hazırla

### 3.3 Performance Optimizasyonu

#### ✅ Görev 3.3.1: Performance Analizi ve Optimizasyon
- **Öncelik:** 🟢 DÜŞÜK
- **Durum:** Beklemede
- **Açıklama:** Performans bottleneck'lerini tespit et ve optimize et
- **Tahmini Süre:** 3 gün
- **Yapılacaklar:**
  - [ ] Profiling yap
  - [ ] N+1 query problemlerini tespit et
  - [ ] Cache mekanizmaları ekle (gerekirse)
  - [ ] Database index'leri optimize et

---

## 🔧 GENEL İYİLEŞTİRME GÖREVLERİ

### 4.1 Security

#### ✅ Görev 4.1.1: Record Rules İnceleme ve İyileştirme
- **Öncelik:** 🟡 YÜKSEK
- **Durum:** Beklemede
- **Açıklama:** Record rules'ları gözden geçir, company-based access kontrolü
- **Tahmini Süre:** 1 gün
- **Not:** Bazı düzeltmeler yapıldı ama kontrol edilmeli

### 4.2 Code Style

#### ✅ Görev 4.2.1: PEP 8 Uyumluluğu
- **Öncelik:** 🟢 DÜŞÜK
- **Durum:** Beklemede
- **Açıklama:** Tüm kodun PEP 8 standartlarına uygunluğunu kontrol et
- **Tahmini Süre:** 1 gün
- **Araçlar:**
  - [ ] `black` formatter kullan
  - [ ] `flake8` ile kontrol et
  - [ ] `pylint` ile kontrol et

### 4.3 Import Optimizasyonu

#### ✅ Görev 4.3.1: Import Organizasyonu
- **Öncelik:** 🟢 DÜŞÜK
- **Durum:** Beklemede
- **Açıklama:** Import'ları organize et (stdlib → third-party → local)
- **Tahmini Süre:** 0.5 gün

---

## 📊 İLERLEME TAKİBİ

### Tamamlanan Görevler
- ✅ XML syntax hatası düzeltildi (report_ariza_kayit.xml)
- ✅ Email sistemi kaldırıldı
- ✅ Hardcoded email adresleri system parameter'a taşındı
- ✅ Hardcoded user logins group-based checks'e çevrildi
- ✅ Silent error handling iyileştirildi
- ✅ Record rules company-based access'e güncellendi

### Devam Eden Görevler
- Yok

### Bekleyen Görevler
- Tüm Faz 1, 2, 3 görevleri

---

## 🎯 ÖNCELİK SIRASI (Özet)

### 🔴 KRİTİK (Hemen Yapılmalı)
1. `ariza.py` dosyasını böl (6-8 dosya)
2. Inherit sınıfları ayrı dosyalara taşı
3. `_create_stock_transfer` metodunu böl
4. `action_personel_onayla` metodunu böl

### 🟡 YÜKSEK (1 Ay İçinde)
1. Constants dosyası oluştur
2. Hardcoded ID'leri system parameter'a taşı
3. Helper sınıfları oluştur
4. Service layer ekle
5. Record rules gözden geçir

### 🟢 ORTA/DÜŞÜK (2-3 Ay İçinde)
1. Unit testler ekle
2. Dokümantasyon iyileştir
3. Performance optimizasyonu
4. Code style iyileştirmeleri

---

## 📝 NOTLAR

- **Strateji:** Incremental refactoring - Her fazı ayrı test et
- **Risk:** Breaking changes riski var, kapsamlı test gerekli
- **Backup:** Her faz öncesi git tag oluştur (v3.0, v3.1, vb.)
- **Modülerlik Hedefi:** 48.5/100 → 75+/100

---

**Son Güncelleme:** 2025-01-XX  
**Hazırlayan:** AI Code Assistant

