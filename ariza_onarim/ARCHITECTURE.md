# Arıza Onarım Modülü – Mimari Dokümantasyonu

**Versiyon:** 1.0.5

---

## Dizin Yapısı

```
ariza_onarim/
├── __manifest__.py
├── hooks.py                 # post_init_hook: konum validasyonu
├── models/
│   ├── ariza.py             # Ana model (ariza.kayit)
│   ├── ariza_constants.py   # Sabitler
│   ├── ariza_helpers/       # Yardımcı servisler
│   │   ├── location_helper.py
│   │   ├── partner_helper.py
│   │   ├── sequence_helper.py
│   │   ├── sms_helper.py
│   │   └── transfer_helper.py
│   ├── account_analytic_account.py
│   ├── stock_picking.py
│   ├── stock_move_line.py
│   ├── res_partner.py
│   ├── hr_employee.py
│   ├── delivery_carrier.py
│   └── account_move_line.py
├── wizards/
├── views/
├── reports/
├── security/
└── data/
```

---

## Ana Model: ariza.kayit

Arıza kayıtlarının tutulduğu ana model.

**Önemli alanlar:**
- `name` – Arıza numarası (sequence)
- `ariza_tipi` – Müşteri / Mağaza
- `teknik_servis` – DTL, NGaudio, Tedarikçi vb.
- `state` – İş akışı durumu
- `kaynak_konum_id`, `hedef_konum_id` – Transfer konumları
- `transfer_id` – İlişkili stock.picking
- `analitik_hesap_id` – Mağaza/depo (analytic account)

---

## Durum Akışı (State)

```
Taslak (draft)
    ↓ Personel Onayı
Personel Onayı (personel_onay)
    ↓ Kabul
Kabul Edildi (kabul_edildi)
    ↓ Onarım Başlat (yönetici)
Teknik Onarım (teknik_onarim)
    ↓ Onayla (yönetici)
Onaylandı (onaylandi)
    ↓ Yönetici Tamamla
Yönetici Tamamlandı (yonetici_tamamlandi)
    ↓ Teslim Et / Teslim Al
Tamamlandı (tamamlandi) veya Teslim Edildi (teslim_edildi)
```

**Alternatif durumlar:** Onarım Dışı, Kilitli, İptal

---

## Helper Modülleri

### location_helper

Stok konumu aramaları.

- `get_dtl_stok_location()` – DTL/Stok
- `get_ariza_stok_location()` – Arıza/Stok
- `get_ngaudio_location()` – ARIZA/NGaudio
- `get_matt_guitar_location()` – ARIZA/MATT
- `get_konum_kodu_from_analytic()` – Analitik hesaptan konum kodu
- `validate_critical_locations()` – Kritik konumları doğrular (post_init_hook)

### partner_helper

Müşteri/partner işlemleri.

- Adres birleştirme
- Tedarikçi konum araması

### sequence_helper

Arıza numarası üretimi.

- `ir.sequence` kullanır
- Fallback: manuel numara

### sms_helper

SMS gönderimi.

- Odoo `sms.sms` modeli kullanır
- 3 aşamalı SMS (müşteri ürünleri)

### transfer_helper

Transfer oluşturma mantığı.

- `stock.picking` oluşturma
- Operasyon tipi seçimi

### teknik_servis_helper

Teknik servis adres ve telefon bilgileri.

- `get_adres()` – Tedarikçi veya sabit adres
- `get_telefon()` – Tedarikçi veya sabit telefon
- ADRES_MAP, TELEFON_MAP – Sabit değerler

### hedef_konum_helper

Teknik servise göre hedef stok konumu.

- `get_hedef_konum()` – Teknik servis + arıza tipi → stock.location
- DTL, ZUHAL, NGaudio, MATT, Prohan, ERK, Tedarikçi eşlemesi

### transfer_helper (ek metodlar)

- `get_warehouse_for_magaza()` – Analitik hesap adından depo
- `get_tamir_picking_type()` – Tamir Teslimatları / Tamir Alımlar

---

## Genişletilen Odoo Modelleri

| Model | Dosya | Eklenenler |
|-------|-------|------------|
| account.analytic.account | account_analytic_account.py | partner_id, konum_kodu, warehouse_id |
| stock.picking | stock_picking.py | Arıza ile ilişki |
| stock.move.line | stock_move_line.py | Odoo 16 uyumluluğu (location_lot_ids) |
| res.partner | res_partner.py | Arıza ile ilişkiler |
| hr.employee | hr_employee.py | Arıza ile ilişki |
| delivery.carrier | delivery_carrier.py | Kargo entegrasyonu |
| account.move.line | account_move_line.py | Muhasebe entegrasyonu |

---

## Sabitler (ariza_constants.py)

- **ArizaStates** – state seçenekleri
- **StateManager** – Yönetici görünümü durumları
- **TeknikServis** – Teknik servis listesi
- **ArizaTipi** – Müşteri / Mağaza
- **LocationNames** – Konum isimleri (DTL_STOK, ARIZA_STOK vb.)
- **DefaultValues** – Varsayılan değerler (DEFAULT_DRIVER_ID vb.)
- **SMSTemplates** – SMS şablonları

---

## Transfer Akışı

### Müşteri ürünü

1. **Personel Onayı:** Mağaza → Hedef konum (teknik servis)
2. **Onaylandı:** Hedef konum → Mağaza (geri gönderim)
3. **Teslim Edildi:** Müşteriye teslim (kargo/araç)

### Mağaza ürünü

1. **Personel Onayı:** Mağaza → Hedef konum (teknik servis)
2. **Onaylandı:** 2. transfer (gerekirse)
3. **Teslim Al:** Teknik servis → Mağaza (Tamir Alımlar)

---

## Güvenlik

- **group_ariza_manager** – Yönetici (onaylama, onarım başlatma)
- **group_ariza_super_manager** – Süper yönetici (+ silme)
- Company bazlı `ir.rule` – Kayıtlar company'ye göre filtrelenir

---

## post_init_hook

Modül yüklendikten sonra:

1. `LocationHelper.validate_critical_locations(env)` çağrılır
2. Eksik konum varsa log'a uyarı yazılır
3. Modül yüklenmesi engellenmez
