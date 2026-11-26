# -*- coding: utf-8 -*-
"""
Chatter mesaj yardımcıları.

Kural: her olay tek satır, tek mesaj; "Konu" başlığı yok; durum değişikliğini
Odoo'nun takip satırı zaten gösterir, mesaj bunu tekrarlamaz. Transfer ve
kayıt numaraları tıklanabilir bağlantıdır (Odoo içinde açılır).
"""

from markupsafe import escape

UYARI = '⚠️'


class ChatterHelper:
    """Arıza kaydı chatter'ına sade, tutarlı mesaj yazar."""

    @staticmethod
    def link(record):
        """Kaydın Odoo içinde açılan bağlantısı (yoksa '-')."""
        if not record:
            return '-'
        record = record[:1]
        ad = escape(record.display_name or record.name or '')
        return (
            f'<a href="/web#id={record.id}&amp;model={record._name}&amp;view_type=form" '
            f'data-oe-model="{record._name}" data-oe-id="{record.id}">{ad}</a>'
        )

    @staticmethod
    def metin(deger):
        """Kullanıcı girdisini HTML'e güvenli koyar."""
        return escape(deger or '')

    @staticmethod
    def yaz(record, govde):
        """Tek satırlık bilgi mesajı."""
        record.message_post(body=govde, message_type='notification')

    @staticmethod
    def uyari(record, govde):
        """Tek satırlık uyarı mesajı (⚠️ ile başlar)."""
        ChatterHelper.yaz(record, f"{UYARI} {govde}")
