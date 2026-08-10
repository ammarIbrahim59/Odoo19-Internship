from datetime import datetime, timedelta

import pytz

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

LIBRARY_TIMEZONE = pytz.timezone('Africa/Cairo')


class LibraryBookLoan(models.Model):
    _name = 'library.book.loan'
    _description = 'Library Book Loan'
    _order = 'borrow_date desc'

    copy_id = fields.Many2one(
        'library.book.copy', string='Book Copy', required=True,
        ondelete='restrict', domain="[('status', '=', 'available')]"
    )
    book_id = fields.Many2one(
        'library.book', string='Book', related='copy_id.book_id',
        store=True, readonly=True
    )
    borrower_id = fields.Many2one('res.partner', string='Borrower', required=True)
    borrow_date = fields.Date(string='Borrow Date', default=fields.Date.context_today, required=True)
    due_date = fields.Date(string='Due Date', required=True)
    return_date = fields.Date(string='Return Date', readonly=True)
    state = fields.Selection([
        ('ongoing', 'Ongoing'),
        ('returned', 'Returned'),
        ('lost', 'Lost'),
    ], string='Status', default='ongoing', required=True, readonly=True)
    is_overdue = fields.Boolean(
        string='Overdue', compute='_compute_is_overdue', search='_search_is_overdue'
    )

    @api.depends('state', 'due_date')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for loan in self:
            loan.is_overdue = (
                loan.state == 'ongoing' and bool(loan.due_date) and loan.due_date < today
            )

    def _search_is_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        if operator in ('in', 'not in'):
            includes_true = True in value
        else:
            includes_true = bool(value)
        negate = operator in ('!=', 'not in')
        want_overdue = includes_true != negate
        if want_overdue:
            return [('state', '=', 'ongoing'), ('due_date', '<', today)]
        return ['|', ('state', '!=', 'ongoing'), ('due_date', '>=', today)]

    @api.constrains('borrow_date', 'due_date')
    def _check_dates(self):
        for loan in self:
            if loan.due_date and loan.borrow_date and loan.due_date < loan.borrow_date:
                raise ValidationError('The due date cannot be before the borrow date!')

    @api.model_create_multi
    def create(self, vals_list):
        loans = super().create(vals_list)
        for loan in loans:
            if loan.copy_id.status not in ('available', 'reserved'): 
                raise UserError(
                    f'"{loan.copy_id.display_name}" is not available for lending.'
                )
            loan.copy_id.status = 'borrowed'
        return loans

    def action_mark_returned(self):
        for loan in self:
            if loan.state != 'ongoing':
                raise UserError('Only ongoing loans can be marked as returned.')
            loan.write({
                'state': 'returned',
                'return_date': fields.Date.context_today(loan),
            })
            loan.copy_id.status = 'available'

    def action_mark_lost(self):
        for loan in self:
            if loan.state != 'ongoing':
                raise UserError('Only ongoing loans can be marked as lost.')
            loan.state = 'lost'
            loan.copy_id.status = 'lost'

    def _cron_send_due_date_reminders(self):
        # Odoo pins the server process to UTC, and context_today() would
        # otherwise resolve "today" via whichever user runs this cron
        # (base.user_root), neither of which matches the library's actual
        # operating day. Anchor explicitly to the library's timezone instead.
        now_utc = pytz.utc.localize(datetime.utcnow())
        today = now_utc.astimezone(LIBRARY_TIMEZONE).date()
        tomorrow = today + timedelta(days=1)
        loans = self.search([('state', '=', 'ongoing'), ('due_date', '=', tomorrow)])
        template = self.env.ref('library_management.mail_template_loan_due_reminder')
        for loan in loans:
            template.send_mail(loan.id, force_send=True)
