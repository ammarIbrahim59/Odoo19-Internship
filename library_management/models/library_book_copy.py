from odoo import models, fields, api


class LibraryBookCopy(models.Model):
    _name = 'library.book.copy'
    _description = 'Library Book Copy'
    _order = 'book_id, copy_number'

    book_id = fields.Many2one(
        'library.book', string='Book', required=True,
        ondelete='cascade', index=True
    )
    # No `default` on purpose: a default value is sent by the client on every
    # create, which would bypass the auto-numbering in `create()` below and
    # collide with `_copy_number_uniq`. Left blank, `create()` assigns it.
    copy_number = fields.Integer(string='Copy Number', required=True)
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
        # Highest copy number already used per book, so that several copies
        # created in the same batch (e.g. added inline on the book form) each
        # get a distinct number instead of all reading the same `last`.
        highest_per_book = {}
        for vals in vals_list:
            book_id = vals.get('book_id')
            if vals.get('copy_number') or not book_id:
                continue
            if book_id not in highest_per_book:
                # active_test=False: an archived copy still occupies its number
                # as far as the UNIQUE constraint is concerned, so it has to
                # count when picking the next one.
                last = self.with_context(active_test=False).search(
                    [('book_id', '=', book_id)],
                    order='copy_number desc', limit=1
                )
                highest_per_book[book_id] = last.copy_number if last else 0
            highest_per_book[book_id] += 1
            vals['copy_number'] = highest_per_book[book_id]
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