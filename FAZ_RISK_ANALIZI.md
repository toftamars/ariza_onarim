# FAZ RİSK ANALİZİ - ARİZA ONARIM MODÜLÜ

**Hazırlanma Tarihi:** 2025-01-XX  
**Amaç:** Her fazın mevcut çalışan sisteme riskini değerlendirmek

---

## 🎯 GENEL RİSK DEĞERLENDİRMESİ

### Risk Seviyeleri:
- 🔴 **YÜKSEK RİSK:** Breaking change potansiyeli, sistemi bozabilir
- 🟡 **ORTA RİSK:** Dikkatli yapılmalı, test gerekli
- 🟢 **DÜŞÜK RİSK:** Güvenli, sorunsuz yapılabilir
- ✅ **RİSK YOK:** Sadece iyileştirme, mevcut sistemi etkilemez

---

## 🔴 FAZ 1: ACİL VE KRİTİK (1-2 Hafta) - 10 GÖREV

### ✅ Görev 1.1.1: `ariza.py` Dosyasını Böl
**Risk:** 🔴 **YÜKSEK RİSK**

**Neden Riskli:**
- Mevcut kodun bölünmesi breaking change riski taşır
- Import path'leri değişir
- Odoo model yükleme sırası değişebilir
- Metodlar arası bağımlılıklar kopabilir

**Risk Senaryoları:**
- Model yüklenirken hata: `AttributeError`, `ImportError`
- Metodlar bulunamayabilir
- Computed field'lar çalışmayabilir
- View'lar hata verebilir

**Güvenli Yapılma Yöntemi:**
- Incremental refactoring (adım adım)
- Her dosya bölümünden sonra test
- Git branch kullan (rollback için)
- Önce sadece inherit sınıfları ayır (en az riskli)

**Sonuç:** ⚠️ **SİSTEMİ BOZABİLİR - DİKKATLİ YAPILMALI**

---

### ✅ Görev 1.1.2: Inherit Sınıfları Ayrı Dosyalara Taşı
**Risk:** 🟡 **ORTA RİSK**

**Neden Riskli:**
- Model inheritance yükleme sırası önemli
- `_inherit` sırası değişebilir
- View inheritance etkilenebilir

**Risk Senaryoları:**
- Model yüklenirken sıra hatası
- View'lar render edilemeyebilir
- Field'lar görünmeyebilir

**Güvenli Yapılma Yöntemi:**
- `__manifest__.py` dosyasında model sırasını kontrol et
- Her sınıfı ayrı ayrı test et
- View dosyalarını kontrol et

**Sonuç:** ⚠️ **DİKKATLİ YAPILMALI - TEST GEREKLİ**

---

### ✅ Görev 1.2.1: Constants Dosyası Oluştur
**Risk:** 🟢 **DÜŞÜK RİSK**

**Neden Güvenli:**
- Sadece string değerleri taşıyor
- Kod mantığı değişmiyor
- Referanslar kolayca değiştirilebilir

**Risk Senaryoları:**
- Typo (yazım hatası) riski
- Eksik import hatası

**Güvenli Yapılma Yöntemi:**
- Tüm string'leri tek tek değiştir
- Find & Replace kullan
- Her değişiklikten sonra test

**Sonuç:** ✅ **GÜVENLİ - KOLAY YAPILABİLİR**

---

### ✅ Görev 1.2.2: Hardcoded ID'leri System Parameter'a Taşı
**Risk:** 🟢 **DÜŞÜK RİSK**

**Neden Güvenli:**
- Sadece değer kaynağı değişiyor
- Kod mantığı aynı kalıyor
- Fallback mekanizması eklenebilir

**Risk Senaryoları:**
- System parameter tanımlı değilse hata
- ID değeri yanlış olabilir

**Güvenli Yapılma Yöntemi:**
- System parameter'ı önce oluştur
- Fallback mekanizması ekle (ID 2205 yoksa eski yöntem)
- Test et

**Sonuç:** ✅ **GÜVENLİ - KOLAY YAPILABİLİR**

---

### ✅ Görev 1.3.1: `_create_stock_transfer` Metodunu Böl
**Risk:** 🔴 **YÜKSEK RİSK**

**Neden Riskli:**
- Transfer oluşturma kritik bir işlem
- 300 satırlık metodun bölünmesi mantık hatası riski
- Metodlar arası bağımlılık kompleks
- State değişiklikleri etkilenebilir

**Risk Senaryoları:**
- Transfer oluşturulamaz
- Location atamaları yanlış olur
- Driver ataması çalışmaz
- Chatter mesajları gönderilmez
- State güncellenmez

**Güvenli Yapılma Yöntemi:**
- Önce helper metodları ekle (mevcut metodu değiştirmeden)
- Her helper metodunu ayrı test et
- Sonra mevcut metodu refactor et
- Comprehensive test yap (tüm senaryolar)

**Sonuç:** ⚠️ **SİSTEMİ BOZABİLİR - ÇOK DİKKATLİ YAPILMALI**

---

### ✅ Görev 1.3.2: `action_personel_onayla` Metodunu Böl
**Risk:** 🔴 **YÜKSEK RİSK**

**Neden Riskli:**
- İş akışının kritik noktası
- State değişiklikleri
- SMS gönderimi
- Transfer oluşturma
- 200 satırlık metodun bölünmesi riskli

**Risk Senaryoları:**
- State yanlış güncellenir
- SMS gönderilmez
- Transfer oluşturulmaz
- Chatter mesajları eksik kalır
- Validation hataları atlanır

**Güvenli Yapılma Yöntemi:**
- Önce validation metodunu ayır
- Sonra SMS metodunu ayır
- Son olarak transfer metodunu ayır
- Her adımda test et
- Rollback planı hazırla

**Sonuç:** ⚠️ **SİSTEMİ BOZABİLİR - ÇOK DİKKATLİ YAPILMALI**

---

### ✅ Görev 1.3.3: `create` Metodunu Böl
**Risk:** 🟡 **ORTA RİSK**

**Neden Riskli:**
- Model create işlemi kritik
- Default değerler ataması
- Validation mantığı
- Sequence oluşturma

**Risk Senaryoları:**
- Kayıt oluşturulamaz
- Default değerler atanmaz
- Validation atlanır
- Sequence hatalı olur

**Güvenli Yapılma Yöntemi:**
- Önce validation metodunu ayır
- Sonra default değer metodunu ayır
- Her adımda test et
- Create işlemini test et

**Sonuç:** ⚠️ **DİKKATLİ YAPILMALI - TEST GEREKLİ**

---

## 🟡 FAZ 2: ORTA ÖNCELİKLİ (1 AY) - 6 GÖREV

### ✅ Görev 2.1.1: Helper Sınıfları Oluştur
**Risk:** 🟢 **DÜŞÜK RİSK**

**Neden Güvenli:**
- Sadece kod organizasyonu
- Mevcut metodları taşıyor
- Mantık değişmiyor
- Test edilebilir

**Risk Senaryoları:**
- Import hatası
- Metod çağrısı hatası (yazım hatası)

**Güvenli Yapılma Yöntemi:**
- Helper metodları static yap
- Import'ları doğru yap
- Her helper metodunu test et

**Sonuç:** ✅ **GÜVENLİ - KOLAY YAPILABİLİR**

---

### ✅ Görev 2.2.1: Service Layer Oluştur
**Risk:** 🟡 **ORTA RİSK**

**Neden Riskli:**
- Business logic'in taşınması
- Metod çağrıları değişir
- State management etkilenebilir

**Risk Senaryoları:**
- Service metodları yanlış çağrılır
- State güncellemeleri eksik kalır
- Transaction yönetimi sorunlu olur

**Güvenli Yapılma Yöntemi:**
- Önce service sınıflarını oluştur
- Mevcut kodları wrapper olarak bırak
- Yavaş yavaş migration yap
- Her service metodunu test et

**Sonuç:** ⚠️ **DİKKATLİ YAPILMALI - TEST GEREKLİ**

---

### ✅ Görev 2.3.1: Try-Except Bloklarını İyileştir
**Risk:** 🟢 **DÜŞÜK RİSK**

**Neden Güvenli:**
- Sadece hata yakalama iyileştiriliyor
- Kod mantığı değişmiyor
- Logging ekleniyor (sadece iyileştirme)

**Risk Senaryoları:**
- Logging seviyesi yanlış olabilir
- Çok fazla log üretilebilir

**Güvenli Yapılma Yöntemi:**
- Her except bloğunu tek tek değiştir
- Log seviyesini doğru ayarla
- Production'da log seviyesini kontrol et

**Sonuç:** ✅ **GÜVENLİ - KOLAY YAPILABİLİR**

---

### ✅ Görev 2.3.2: Magic Number'ları Constants'a Taşı
**Risk:** 🟢 **DÜŞÜK RİSK**

**Neden Güvenli:**
- Sadece değer kaynağı değişiyor
- Kod mantığı aynı

**Risk Senaryoları:**
- Typo riski
- Eksik import

**Güvenli Yapılma Yöntemi:**
- Tüm sayıları bul ve değiştir
- Test et

**Sonuç:** ✅ **GÜVENLİ - KOLAY YAPILABİLİR**

---

### ✅ Görev 2.3.3: Duplicate Kodları Temizle
**Risk:** 🟢 **DÜŞÜK RİSK**

**Neden Güvenli:**
- Kod tekrarını azaltıyor
- Mantık değişmiyor

**Risk Senaryoları:**
- Helper metod parametreleri eksik olabilir
- Bazı edge case'ler atlanabilir

**Güvenli Yapılma Yöntemi:**
- Her duplicate kod bloğunu analiz et
- Helper metod parametrelerini doğru ayarla
- Tüm senaryoları test et

**Sonuç:** ✅ **GÜVENLİ - DİKKATLİ YAPILMALI**

---

## 🟢 FAZ 3: UZUN VADELİ (2-3 AY) - 3 GÖREV

### ✅ Görev 3.1.1: Unit Testler Ekle
**Risk:** ✅ **RİSK YOK**

**Neden Risksiz:**
- Sadece test ekleniyor
- Mevcut koda dokunulmuyor
- Sadece iyileştirme

**Risk Senaryoları:**
- Test yazımı yanlış olabilir (ama sistemi bozmaz)
- Test coverage eksik olabilir

**Sonuç:** ✅ **RİSK YOK - SADECE İYİLEŞTİRME**

---

### ✅ Görev 3.2.1: Dokümantasyon İyileştir
**Risk:** ✅ **RİSK YOK**

**Neden Risksiz:**
- Sadece dokümantasyon
- Koda dokunulmuyor
- Sadece iyileştirme

**Sonuç:** ✅ **RİSK YOK - SADECE İYİLEŞTİRME**

---

### ✅ Görev 3.3.1: Performance Optimizasyonu
**Risk:** 🟡 **ORTA RİSK**

**Neden Riskli:**
- Query optimizasyonu
- Cache mekanizması
- Index değişiklikleri

**Risk Senaryoları:**
- Query sonuçları değişebilir
- Cache invalidation sorunları
- Index hataları

**Güvenli Yapılma Yöntemi:**
- Önce profiling yap
- Optimizasyonları küçük adımlarla yap
- Her optimizasyonu test et

**Sonuç:** ⚠️ **DİKKATLİ YAPILMALI - TEST GEREKLİ**

---

## 🔧 GENEL İYİLEŞTİRME GÖREVLERİ - 5 GÖREV

### ✅ Görev 4.1.1: Record Rules İnceleme ve İyileştirme
**Risk:** 🔴 **YÜKSEK RİSK**

**Neden Riskli:**
- Güvenlik kuralları değişiyor
- Kullanıcı erişim hakları etkilenir
- Veri güvenliği riski

**Risk Senaryoları:**
- Kullanıcılar kayıtlara erişemez (çok kısıtlayıcı)
- Kullanıcılar tüm kayıtlara erişir (çok açık)
- Company-based access yanlış çalışır

**Güvenli Yapılma Yöntemi:**
- Önce mevcut erişimleri analiz et
- Test kullanıcıları ile test et
- Yavaş yavaş değiştir
- Rollback planı hazırla

**Sonuç:** ⚠️ **SİSTEMİ BOZABİLİR - ÇOK DİKKATLİ YAPILMALI**

---

### ✅ Görev 4.2.1: PEP 8 Uyumluluğu
**Risk:** 🟢 **DÜŞÜK RİSK**

**Neden Güvenli:**
- Sadece kod formatı değişiyor
- Mantık değişmiyor
- Python formatter kullanılıyor

**Risk Senaryoları:**
- Formatter hatalı format yapabilir (nadir)
- Bazı satırlar yanlış yorumlanabilir

**Güvenli Yapılma Yöntemi:**
- Önce backup al
- Formatter'ı kullan
- Sonucu kontrol et
- Test et

**Sonuç:** ✅ **GÜVENLİ - KOLAY YAPILABİLİR**

---

### ✅ Görev 4.3.1: Import Organizasyonu
**Risk:** 🟢 **DÜŞÜK RİSK**

**Neden Güvenli:**
- Sadece import sırası değişiyor
- Import'lar aynı kalıyor
- Mantık değişmiyor

**Risk Senaryoları:**
- Circular import riski (nadir)
- Import sırası hatası (nadir)

**Güvenli Yapılma Yöntemi:**
- Import'ları kontrol et
- Circular import kontrolü yap
- Test et

**Sonuç:** ✅ **GÜVENLİ - KOLAY YAPILABİLİR**

---

## 📊 ÖZET RİSK TABLOSU

| Faz | Görev | Risk Seviyesi | Sistemi Bozabilir mi? | Öneri |
|-----|-------|---------------|----------------------|-------|
| **FAZ 1** |
| 1.1.1 | `ariza.py` Böl | 🔴 YÜKSEK | ✅ EVET | Incremental refactoring |
| 1.1.2 | Inherit Sınıfları Ayır | 🟡 ORTA | ⚠️ OLABİLİR | Test gerekli |
| 1.2.1 | Constants Dosyası | 🟢 DÜŞÜK | ❌ HAYIR | Güvenli |
| 1.2.2 | System Parameter | 🟢 DÜŞÜK | ❌ HAYIR | Güvenli |
| 1.3.1 | `_create_stock_transfer` Böl | 🔴 YÜKSEK | ✅ EVET | Çok dikkatli |
| 1.3.2 | `action_personel_onayla` Böl | 🔴 YÜKSEK | ✅ EVET | Çok dikkatli |
| 1.3.3 | `create` Böl | 🟡 ORTA | ⚠️ OLABİLİR | Test gerekli |
| **FAZ 2** |
| 2.1.1 | Helper Sınıfları | 🟢 DÜŞÜK | ❌ HAYIR | Güvenli |
| 2.2.1 | Service Layer | 🟡 ORTA | ⚠️ OLABİLİR | Test gerekli |
| 2.3.1 | Try-Except İyileştir | 🟢 DÜŞÜK | ❌ HAYIR | Güvenli |
| 2.3.2 | Magic Number | 🟢 DÜŞÜK | ❌ HAYIR | Güvenli |
| 2.3.3 | Duplicate Kod | 🟢 DÜŞÜK | ❌ HAYIR | Güvenli |
| **FAZ 3** |
| 3.1.1 | Unit Testler | ✅ RİSK YOK | ❌ HAYIR | Sadece iyileştirme |
| 3.2.1 | Dokümantasyon | ✅ RİSK YOK | ❌ HAYIR | Sadece iyileştirme |
| 3.3.1 | Performance | 🟡 ORTA | ⚠️ OLABİLİR | Test gerekli |
| **GENEL** |
| 4.1.1 | Record Rules | 🔴 YÜKSEK | ✅ EVET | Çok dikkatli |
| 4.2.1 | PEP 8 | 🟢 DÜŞÜK | ❌ HAYIR | Güvenli |
| 4.3.1 | Import Organizasyonu | 🟢 DÜŞÜK | ❌ HAYIR | Güvenli |

---

## 🎯 ÖNERİLEN YAKLAŞIM

### 🔴 YÜKSEK RİSKLİ GÖREVLER (Sistemi Bozabilir)
1. **`ariza.py` Dosyasını Böl** - Incremental refactoring
2. **`_create_stock_transfer` Böl** - Helper metodları önce ekle
3. **`action_personel_onayla` Böl** - Adım adım refactor
4. **Record Rules İyileştirme** - Test kullanıcıları ile test et

**Öneri:** Bu görevler için:
- Git branch kullan
- Her adımda test
- Rollback planı hazır
- Production'a yavaş yavaş deploy

### 🟡 ORTA RİSKLİ GÖREVLER (Dikkatli Yapılmalı)
1. **Inherit Sınıfları Ayır** - Model sırasını kontrol et
2. **`create` Böl** - Validation test et
3. **Service Layer** - Wrapper metodlar bırak
4. **Performance Optimizasyonu** - Küçük adımlarla

**Öneri:** Bu görevler için:
- Test yap
- Rollback planı hazır

### 🟢 DÜŞÜK RİSKLİ GÖREVLER (Güvenli)
1. **Constants Dosyası** - Kolay yapılabilir
2. **System Parameter** - Kolay yapılabilir
3. **Helper Sınıfları** - Kolay yapılabilir
4. **Try-Except İyileştir** - Kolay yapılabilir
5. **Magic Number** - Kolay yapılabilir
6. **Duplicate Kod** - Kolay yapılabilir
7. **PEP 8** - Kolay yapılabilir
8. **Import Organizasyonu** - Kolay yapılabilir

**Öneri:** Bu görevler önce yapılabilir (risk yok)

### ✅ RİSK YOK (Sadece İyileştirme)
1. **Unit Testler** - Sadece ekleme
2. **Dokümantasyon** - Sadece ekleme

**Öneri:** İstediğin zaman yapılabilir

---

## 🚀 ÖNERİLEN SIRA

### Adım 1: Güvenli Görevler (1 hafta)
1. Constants Dosyası
2. System Parameter
3. Try-Except İyileştir
4. Magic Number
5. PEP 8
6. Import Organizasyonu

**Sonuç:** Risk yok, hızlı ilerleme

### Adım 2: Orta Riskli Görevler (2 hafta)
1. Helper Sınıfları
2. Inherit Sınıfları Ayır (dikkatli)
3. Duplicate Kod

**Sonuç:** Test gerekli ama güvenli

### Adım 3: Yüksek Riskli Görevler (3-4 hafta)
1. `ariza.py` Böl (incremental)
2. `_create_stock_transfer` Böl
3. `action_personel_onayla` Böl
4. Record Rules

**Sonuç:** Çok dikkatli, test gerekli

### Adım 4: Uzun Vadeli (2-3 ay)
1. Service Layer
2. Performance Optimizasyonu
3. Unit Testler
4. Dokümantasyon

**Sonuç:** Zaman alıcı ama değerli

---

## ✅ SONUÇ

**Şu an sorunsuz çalışan sisteme risk yaratmayan görevler:**
- ✅ Constants Dosyası
- ✅ System Parameter
- ✅ Helper Sınıfları
- ✅ Try-Except İyileştir
- ✅ Magic Number
- ✅ Duplicate Kod
- ✅ PEP 8
- ✅ Import Organizasyonu
- ✅ Unit Testler (sadece ekleme)
- ✅ Dokümantasyon (sadece ekleme)

**Toplam: 10 görev - GÜVENLİ YAPILABİLİR**

**Sistemi bozabilir görevler:**
- 🔴 `ariza.py` Böl
- 🔴 `_create_stock_transfer` Böl
- 🔴 `action_personel_onayla` Böl
- 🔴 Record Rules İyileştirme

**Toplam: 4 görev - DİKKATLİ YAPILMALI**

---

**Son Güncelleme:** 2025-01-XX

