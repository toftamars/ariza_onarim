# Arıza Onarım Modülü – Mimari Dokümantasyonu

**Versiyon:** 1.0.5  
**Refactor:** Ana model iş mantığı helper ve service'lere taşınmıştır (~%69 kod azaltma).

---

## Dizin Yapısı

```
ariza_onarim/
├── __manifest__.py
├── hooks.py                 # post_init_hook: konum validasyonu
├── models/
│   ├── ariza.py             # Ana model (ariza.kayit) – ince delegasyon katmanı
│   ├── ariza_constants.py   # Sabitler
│   ├── ariza_helpers/       # Yardımcı servisler ve helper'lar
│   │   ├── location_helper.py
│   │   ├── partner_helper.py
│   │   ├── sequence_helper.py
│   │   ├── sms_helper.py
│   │   ├── transfer_helper.py
│   │   ├── teknik_servis_helper.py
│   │   ├── hedef_konum_helper.py
│   │   ├── ariza_transfer_service.py    # Stok transferi oluşturma
│   │   ├── ariza_state_service.py      # State geçişleri, lock/unlock
│   │   ├── ariza_computed_helper.py    # Computed alan hesaplamaları
│   │   ├── ariza_teslim_al_service.py  # Mağaza ürünü teslim al
│   │   ├── ariza_cron_service.py       # Cron işlemleri (deadline, kalan süre)
│   │   ├── ariza_create_service.py     # create() hazırlık ve sonrası
│   │   ├── ariza_search_helper.py      # _search domain genişletmesi
│   │   ├── ariza_onchange_helper.py    # Tüm onchange mantığı
│   │   ├── ariza_print_service.py      # Yazdırma işlemleri
│   │   └── ariza_write_helper.py       # write() hedef konum koruması
│   ├── account_analytic_account.py
│   ├── stock_picking.py
│   ├── stock_move_line.py
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

## Refactor Mimarisi

### Katmanlı Yapı

```
ariza.py (Ana Model)
    │
    ├── Field tanımları, @api.depends, @api.onchange decorator'ları
    │
    └── İnce delegasyon → Helper / Service
            │
            ├── ariza_onchange_helper   → Onchange mantığı
            ├── ariza_state_service     → State geçişleri, lock/unlock
            ├── ariza_print_service     → action_print, action_print_invoice, action_print_delivery
            ├── ariza_computed_helper   → Tüm _compute_* hesaplamaları
            ├── ariza_transfer_service  → Stok transferi oluşturma
            ├── ariza_teslim_al_service → Mağaza ürünü teslim al
            ├── ariza_create_service    → create() prepare_vals, post_create
            ├── ariza_search_helper      → _search domain genişletmesi
            ├── ariza_write_helper      → write() hedef konum koruması
            ├── sms_helper              → _send_sms_to_customer
            ├── hedef_konum_helper      → Hedef konum belirleme
            ├── location_helper         → Konum aramaları
```

### Import Zinciri (Circular Import Önleme)

- **ariza_computed_helper**: `teknik_servis_helper` sadece `compute_teknik_servis_adres` ve `compute_teknik_servis_telefon` içinde **lazy import** ile kullanılır.
- **ariza_write_helper**: Sadece `hedef_konum_helper` import eder; model'e bağımlı değildir.

---

## Ana Model: ariza.kayit

Arıza kayıtlarının tutulduğu ana model. Refactor sonrası **~657 satır** (önceden ~2100).

**Önemli alanlar:**
- `name` – Arıza numarası (sequence)
- `ariza_tipi` – Müşteri / Mağaza
- `teknik_servis` – DTL, NGaudio, Tedarikçi vb.
- `state` – İş akışı durumu
- `kaynak_konum_id`, `hedef_konum_id` – Transfer konumları
- `transfer_id` – İlişkili stock.picking
- `analitik_hesap_id` – Mağaza/depo (analytic account)

---

## Helper ve Service Özeti

| Modül | Sorumluluk |
|-------|------------|
| **ariza_onchange_helper** | Tüm onchange mantığı (invoice_line_id, marka_id, tedarikci, magaza_konumlar vb.) |
| **ariza_state_service** | personel_onayla, kabul_et, teknik_onarim_baslat, onayla, iptal, lock, unlock |
| **ariza_print_service** | action_print, action_print_invoice, action_print_delivery |
| **ariza_computed_helper** | Fatura tarihi, garanti, kalan süre, teknik servis adres/telefon, müşteri faturaları |
| **ariza_transfer_service** | Stok transferi oluşturma (build_picking_vals, create_stock_transfer) |
| **ariza_teslim_al_service** | Mağaza ürünü teslim al (Tamir Alımlar transferi) |
| **ariza_create_service** | create() öncesi prepare_vals, sonrası post_create |
| **ariza_search_helper** | _search domain genişletmesi (ürün alanı) |
| **ariza_write_helper** | write() hedef_konum_id koruması (otomatik konum değiştirilemez) |
| **ariza_cron_service** | check_onarim_deadlines, update_kalan_sure |
| **sms_helper** | send_sms, send_sms_to_ariza_customer |
| **hedef_konum_helper** | get_hedef_konum, update_hedef_konum, hedef_konum_otomatik_mi |
| **location_helper** | DTL/Arıza/NFSL konum aramaları, get_kaynak_konum_for_analitik |

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

## Genişletilen Odoo Modelleri

| Model | Dosya | Eklenenler |
|-------|-------|------------|
| account.analytic.account | account_analytic_account.py | partner_id, konum_kodu, warehouse_id |
| stock.picking | stock_picking.py | Arıza ile ilişki |
| stock.move.line | stock_move_line.py | Odoo 16 uyumluluğu (location_lot_ids) |
| hr.employee | hr_employee.py | Arıza ile ilişki |
| delivery.carrier | delivery_carrier.py | Kargo entegrasyonu |
| account.move.line | account_move_line.py | Muhasebe entegrasyonu |

---

## Sabitler (ariza_constants.py)

- **ArizaStates** – state seçenekleri
- **StateManager** – Yönetici görünümü durumları
- **TeknikServis** – Teknik servis listesi
- **ArizaTipi** – Müşteri / Mağaza
- **MagicNumbers** – Garanti ay, iş günü vb.
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
