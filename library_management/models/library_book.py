from datetime import date
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class LibraryBookTag(models.Model):
    _name = 'library.book.tag'
    _description = 'Book Tag'

    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color Index')


class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Library Book'

    # SQL Constraints (Odoo 19 Syntax)
    _check_pages_positive = models.Constraint(
        'CHECK(pages > 0)', 
        'The page count must be greater than zero!'
    )
    _name_uniq = models.Constraint(
        'UNIQUE(name)', 
        'A book with this title already exists!'
    )

    # Basic & Relational Fields
    name = fields.Char(string='Title', required=True)
    author_id = fields.Many2one('res.partner', string='Author')
    tag_ids = fields.Many2many('library.book.tag', string='Tags')
    pages = fields.Integer(string='Number of Pages')
    active = fields.Boolean(string='Active', default=True)
    publication_date = fields.Date(string='Publication Date')
    availability = fields.Selection([
        ('available', 'Available'),
        ('unavailable', 'Unavailable'),
    ], string='Availability', compute='_compute_copy_counts', store=True)

    # Computed Field (stored in database so it can be searched and filtered)
    is_classic = fields.Boolean(
        string='Is Classic',
        compute='_compute_is_classic',
        store=True
    )

    # Copies & Loans
    copy_ids = fields.One2many('library.book.copy', 'book_id', string='Copies')
    copy_count = fields.Integer(string='Total Copies', compute='_compute_copy_counts', store=True)
    available_copy_count = fields.Integer(
        string='Available Copies', compute='_compute_copy_counts', store=True
    )
    loan_count = fields.Integer(string='Loan Count', compute='_compute_loan_count')

    @api.depends('copy_ids.status')
    def _compute_copy_counts(self):
        for book in self:
            book.copy_count = len(book.copy_ids)
            book.available_copy_count = len(
                book.copy_ids.filtered(lambda c: c.status == 'available')
            )
            book.availability = 'available' if book.available_copy_count else 'unavailable'

    def _compute_loan_count(self):
        for book in self:
            book.loan_count = self.env['library.book.loan'].search_count(
                [('book_id', '=', book.id)]
            )

    def action_view_copies(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Copies',
            'res_model': 'library.book.copy',
            'view_mode': 'list,form',
            'domain': [('book_id', '=', self.id)],
            'context': {'default_book_id': self.id},
        }

    def action_view_loans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Loans',
            'res_model': 'library.book.loan',
            'view_mode': 'list,form',
            'domain': [('book_id', '=', self.id)],
        }

    @api.depends('publication_date')
    def _compute_is_classic(self):
        for record in self:
            if record.publication_date:
                years_old = date.today().year - record.publication_date.year
                record.is_classic = years_old >= 50
            else:
                record.is_classic = False

    # Python Constraint
    @api.constrains('publication_date')
    def _check_publication_date(self):
        for record in self:
            if record.publication_date and record.publication_date > date.today():
                raise ValidationError("The publication date cannot be in the future!")