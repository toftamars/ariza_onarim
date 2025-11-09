# -*- coding: utf-8 -*-
"""
Post-install hooks - Modül yüklendikten sonra çalışacak işlemler
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """
    Modül yüklendikten sonra tüm iç kullanıcıları group_ariza_user grubuna ekler.
    Bu sayede tüm iç kullanıcılar otomatik olarak modüle erişebilir.
    
    Eğer bir kullanıcıyı bu gruptan çıkarırsanız, o kullanıcı modülü göremez.
    """
    from odoo import api, SUPERUSER_ID
    
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    try:
        # group_ariza_user grubunu bul
        group_user = env.ref('ariza_onarim.group_ariza_user', raise_if_not_found=False)
        if not group_user:
            _logger.warning("group_ariza_user grubu bulunamadı!")
            return
        
        # Tüm iç kullanıcıları bul (base.group_user grubunda olanlar)
        base_group_user = env.ref('base.group_user', raise_if_not_found=False)
        if not base_group_user:
            _logger.warning("base.group_user grubu bulunamadı!")
            return
        
        # base.group_user grubundaki tüm kullanıcıları al
        all_users = env['res.users'].search([
            ('groups_id', 'in', [base_group_user.id])
        ])
        
        # Kullanıcıları group_ariza_user grubuna ekle
        added_count = 0
        for user in all_users:
            if group_user not in user.groups_id:
                user.write({'groups_id': [(4, group_user.id)]})
                added_count += 1
        
        _logger.info(f"Post-init hook: {added_count} kullanıcı group_ariza_user grubuna eklendi.")
        
        # Commit işlemi
        cr.commit()
        
    except Exception as e:
        _logger.error(f"Post-init hook hatası: {str(e)}")
        cr.rollback()

