/**
 * Safe guard for optional debranding_settings
 * Prevents: undefined is not an object (odoo.debranding_settings.*)
 */
(function () {
    try {
        window.odoo = window.odoo || {};
        window.odoo.debranding_settings = window.odoo.debranding_settings || {
            odoo_text_replacement: '',
            odoo_support_url: '',
            odoo_documentation_url: '',
        };
    } catch (e) {
        // no-op
    }
})();


