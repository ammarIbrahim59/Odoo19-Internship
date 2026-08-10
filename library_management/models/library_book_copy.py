from odoo import models, fields, api


class LibraryBookCopy(models.Model):
    _name = 'library.book.copy'
    _description = 'Library Book Copy'
    _order = 'book_id, copy_number'

    book_id = fields.Many2one(
        'library.book', string='Book', required=True,
        ondelete='cascade', index=True
    )
    copy_number = fields.Integer(string='Copy Number', required=True, default=1)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('borrowed', 'Borrowed'),
        ('lost', 'Lost'),
    ], string='Status', default='draft', required=True)
    active = fields.Boolean(string='Active', default=True)

    _copy_number_uniq = models.Constraint(
        'UNIQUE(book_id, copy_number)',
        'This copy number already exists for this book!'
    )
    
    @api.depends('book_id.name', 'copy_number')
    def _compute_display_name(self):
        for copy in self:
            copy.display_name = f"{copy.book_id.name} - Copy #{copy.copy_number}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('copy_number') and vals.get('book_id'):
                last = self.search(
                    [('book_id', '=', vals['book_id'])],
                    order='copy_number desc', limit=1
                )
                vals['copy_number'] = (last.copy_number + 1) if last else 1
        copies = super().create(vals_list)
        copies.filtered(lambda c: c.status == 'available')._assign_pending_reservations()
        return copies
    
    def write(self, vals):
        result = super().write(vals)
        if vals.get('status') == 'available':
            self._assign_pending_reservations()
        return result

    def _assign_pending_reservations(self):
        Reservation = self.env['library.book.reservation']
        for copy in self:
            if copy.status != 'available':
                continue
            reservation = Reservation.search([
                ('book_id', '=', copy.book_id.id),
                ('state', '=', 'requested'),
            ], order='request_date asc', limit=1)
            if reservation:
                reservation._assign_copy(copy)