from odoo.tests.common import TransactionCase


class TestLibraryBookCopyNumbering(TransactionCase):
    """Auto-numbering of `library.book.copy.copy_number`.

    Every case here collides with the `UNIQUE(book_id, copy_number)`
    constraint if the numbering in `create()` gets it wrong.
    """

    def setUp(self):
        super().setUp()
        self.Copy = self.env['library.book.copy']
        self.book = self.env['library.book'].create({
            'name': 'Numbering Test Title',
            'pages': 100,
        })
        self.other_book = self.env['library.book'].create({
            'name': 'Another Numbering Test Title',
            'pages': 200,
        })

    def test_sequential_creates_increment(self):
        """Copies created one at a time get 1, 2, 3."""
        numbers = [
            self.Copy.create({'book_id': self.book.id}).copy_number
            for _ in range(3)
        ]
        self.assertEqual(numbers, [1, 2, 3])

    def test_batch_create_gets_distinct_numbers(self):
        """Copies created in a single batch must not all reuse the same number.

        This is what happens when several copies are added inline on the book
        form before saving.
        """
        copies = self.Copy.create([
            {'book_id': self.book.id},
            {'book_id': self.book.id},
            {'book_id': self.book.id},
        ])
        self.assertEqual(sorted(copies.mapped('copy_number')), [1, 2, 3])

    def test_numbering_is_per_book(self):
        """Each book numbers its own copies from 1."""
        first = self.Copy.create({'book_id': self.book.id})
        second = self.Copy.create({'book_id': self.other_book.id})
        self.assertEqual(first.copy_number, 1)
        self.assertEqual(second.copy_number, 1)

    def test_archived_copy_number_is_not_reused(self):
        """An archived copy still occupies its number.

        The UNIQUE constraint ignores `active`, so numbering has to search with
        active_test=False or this raises an IntegrityError.
        """
        first = self.Copy.create({'book_id': self.book.id})
        self.assertEqual(first.copy_number, 1)
        first.active = False
        second = self.Copy.create({'book_id': self.book.id})
        self.assertEqual(second.copy_number, 2)

    def test_explicit_copy_number_is_respected(self):
        """A caller-supplied number wins, and numbering continues past it."""
        explicit = self.Copy.create({'book_id': self.book.id, 'copy_number': 42})
        self.assertEqual(explicit.copy_number, 42)
        following = self.Copy.create({'book_id': self.book.id})
        self.assertEqual(following.copy_number, 43)

    def test_numbering_survives_client_supplied_defaults(self):
        """Reproduces how the web client actually creates a copy.

        The client calls `default_get()` and posts the result back as part of
        `vals`, so any `default=` on `copy_number` arrives as a real value and
        would bypass the auto-numbering, colliding on the second copy. Calling
        `create()` directly does not exercise this, because ORM defaults are
        applied inside `super().create()` -- after the override reads `vals`.
        """
        fields_list = ['book_id', 'copy_number', 'status']
        for expected in (1, 2, 3):
            vals = self.Copy.default_get(fields_list)
            vals['book_id'] = self.book.id
            copy = self.Copy.create(vals)
            self.assertEqual(
                copy.copy_number, expected,
                "copy_number must be auto-assigned even when the client sends "
                "a default for it"
            )

    def test_available_copy_triggers_reservation_assignment(self):
        """Creating an available copy hands it to the oldest waiting hold."""
        borrower = self.env['res.partner'].create({'name': 'Numbering Borrower'})
        reservation = self.env['library.book.reservation'].create({
            'book_id': self.book.id,
            'partner_id': borrower.id,
        })
        self.assertEqual(reservation.state, 'requested')
        copy = self.Copy.create({'book_id': self.book.id, 'status': 'available'})
        self.assertEqual(reservation.state, 'ready')
        self.assertEqual(reservation.copy_id, copy)
        self.assertEqual(copy.status, 'reserved')
