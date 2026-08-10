{
    'name': 'Library Management',
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'Manage books, physical copies, loans and reservation holds',
    'description': """
Library Management
==================

A library catalog built around per-copy lending:

* Titles (``library.book``) with authors and tags, and a *derived* availability
  computed from the state of their physical copies.
* Physical copies (``library.book.copy``) as the unit of lending, with
  auto-incremented copy numbers per book.
* Loans (``library.book.loan``) with a searchable overdue filter.
* A request -> hold -> fulfillment reservation workflow that automatically
  assigns a freed copy to the longest-waiting member (FIFO), holds it for
  pickup, and expires the hold on a schedule.
* A daily cron that emails borrowers whose loan is due tomorrow.
""",
    'author': 'Ammar Ibrahim',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'data/library_book_reservation_cron.xml',
        'data/library_book_loan_cron.xml',
        'views/library_book_copy_views.xml',
        'views/library_book_loan_views.xml',
        'views/library_book_reservation_views.xml',
        'views/library_book_views.xml',
    ],
    'installable': True,
    'application': True,
}
