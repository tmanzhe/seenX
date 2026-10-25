"""Search checks use invented text records, never personal documents."""

import unittest

from load_images import search_pdf_text


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"kind": "image", "path": "photo.jpg"},
            {"kind": "pdf", "path": "trip.pdf", "pages": [
                {"number": 1, "text": "Train\n  booking to Montréal. Train booking."},
                {"number": 2, "text": "Hotel receipt"},
                {"number": 3, "text": ""},
            ]},
            {"kind": "pdf", "path": "other.pdf", "pages": [
                {"number": 1, "text": "TRAIN BOOKING"},
            ]},
        ]

    def test_phrase_matches_across_whitespace_and_case_once_per_page(self):
        self.assertEqual(search_pdf_text(self.records, "  Train\tBooking "), [
            {"path": "trip.pdf", "page": 1},
            {"path": "other.pdf", "page": 1},
        ])

    def test_page_numbers_are_preserved(self):
        self.assertEqual(search_pdf_text(self.records, "receipt"), [
            {"path": "trip.pdf", "page": 2},
        ])

    def test_missing_phrase_and_empty_collection(self):
        self.assertEqual(search_pdf_text(self.records, "unmatched"), [])
        self.assertEqual(search_pdf_text([], "booking"), [])

    def test_blank_queries_are_rejected(self):
        for query in ("", " \n\t"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                search_pdf_text(self.records, query)

    def test_unicode_casefold(self):
        records = [{"kind": "pdf", "path": "example.pdf", "pages": [
            {"number": 1, "text": "Straße"},
        ]}]
        self.assertEqual(len(search_pdf_text(records, "STRASSE")), 1)


if __name__ == "__main__":
    unittest.main()
