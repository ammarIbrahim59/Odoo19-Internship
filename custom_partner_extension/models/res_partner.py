from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_vip = fields.Boolean(
        string='VIP Member', 
        default=False,
        help='Check if this contact is a VIP member.'
    )
    instructor_bio = fields.Text(
        string='Instructor Bio',
        help='Short biography if the contact is an instructor.'
    )
    
    #  New Computed Field
    bio_character_count = fields.Integer(
    string='Bio Character Count',
    compute='_compute_bio_character_count',
    store=True,
    help='Total number of characters in the instructor bio.'
    )

    @api.depends('instructor_bio')
    def _compute_bio_character_count(self):
        """ Calculates the length of the instructor_bio string """
        for partner in self:
            if partner.instructor_bio:
                partner.bio_character_count = len(partner.instructor_bio)
            else:
                partner.bio_character_count = 0

    @api.onchange('instructor_bio')
    def _onchange_instructor_bio(self):
        """ Automatically mark as VIP if the bio contains key words """
        if self.instructor_bio:
            bio_lower = self.instructor_bio.lower()
            if 'vip' in bio_lower or 'partner' in bio_lower:
                self.is_vip = True

    def _apply_vip_from_bio(self):
        """ Server-side enforcement of the VIP-from-bio rule, so it also
        applies to writes/imports/automations that bypass the UI onchange. """
        for partner in self:
            if partner.instructor_bio and not partner.is_vip:
                bio_lower = partner.instructor_bio.lower()
                if 'vip' in bio_lower or 'partner' in bio_lower:
                    partner.is_vip = True

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._apply_vip_from_bio()
        return partners

    def write(self, vals):
        res = super().write(vals)
        if 'instructor_bio' in vals:
            self._apply_vip_from_bio()
        return res
