from odoo import models, api, fields
from odoo.exceptions import UserError
from datetime import timedelta

HOLD_DAYS = 3
LOAN_DAYS = 14

class LibraryBookReservation(models.Model):
    _name = 'library.book.reservation'
    _description = 'Library Book Reservation'
    _inherit = ['mail.thread']
    _order = 'request_date asc'

    book_id = fields.Many2one(
        'library.book', string='Book', required=True, ondelete='restrict'
    )
    partner_id = fields.Many2one(
        'res.partner', string='Reserved By', required=True
    )
    copy_id = fields.Many2one(
        'library.book.copy', string='Assigned Copy', readonly=True
    )
    state = fields.Selection([
        ('requested', 'Requested'),
        ('ready', 'Ready for Pickup'),
        ('fulfilled', 'Fulfilled'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='requested', required=True, readonly=True)

    request_date = fields.Datetime(
        string='Requested On', default=fields.Datetime.now, required=True
    )
    ready_date = fields.Datetime(string='Ready On', readonly=True)
    hold_expiry = fields.Datetime(string='Hold Expires On', readonly=True)

    def _assign_copy(self, copy):
        self.ensure_one()
        now = fields.Datetime.now()
        self.write({
            'copy_id': copy.id,
            'state': 'ready',
            'ready_date': now,
            'hold_expiry': now + timedelta(days=HOLD_DAYS),
        })
        copy.status = 'reserved'
        self.message_post(
            body=f'"{copy.book_id.display_name}" is ready for pickup.'
        )
        template = self.env.ref('library_management.mail_template_reservation_ready')
        template.send_mail(self.id, force_send=True)

    def _cron_expire_reservations(self):
        now = fields.Datetime.now()
        expired = self.search([
            ('state', '=', 'ready'),
            ('hold_expiry', '<', now),
        ])
        for reservation in expired:
            copy = reservation.copy_id
            reservation.state = 'expired'
            copy.status = 'available'

    def action_fulfill(self):
        for reservation in self:
            if reservation.state != 'ready':
                raise UserError('Only reservations that are ready for pickup can be fulfilled.')
            today = fields.Date.context_today(reservation)
            self.env['library.book.loan'].create({
                'copy_id': reservation.copy_id.id,
                'borrower_id': reservation.partner_id.id,
                'borrow_date': today,
                'due_date': today + timedelta(days=LOAN_DAYS),
            })
            reservation.state = 'fulfilled'