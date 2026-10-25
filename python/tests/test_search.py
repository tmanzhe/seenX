"""Search checks use invented text records, never personal documents."""

import unittest

from seenx.load_images import search_text


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
        self.assertEqual(search_text(self.records, "  Train\tBooking "), [
            {"path": "trip.pdf", "page": 1},
            {"path": "other.pdf", "page": 1},
        ])

    def test_page_numbers_are_preserved(self):
        self.assertEqual(search_text(self.records, "receipt"), [
            {"path": "trip.pdf", "page": 2},
        ])

    def test_missing_phrase_and_empty_collection(self):
        self.assertEqual(search_text(self.records, "unmatched"), [])
        self.assertEqual(search_text([], "booking"), [])

    def test_blank_queries_are_rejected(self):
        for query in ("", " \n\t"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                search_text(self.records, query)

    def test_unicode_casefold(self):
        records = [{"kind": "pdf", "path": "example.pdf", "pages": [
            {"number": 1, "text": "Straße"},
        ]}]
        self.assertEqual(len(search_text(records, "STRASSE")), 1)

    def test_image_and_pdf_results_share_the_same_search(self):
        records = [
            {"kind": "image", "path": "screenshot.png", "text": "TRAIN booking"},
            {"kind": "image", "path": "unread.jpg"},
            {"kind": "image", "path": "failed.jpg", "ocr_error": "failed"},
            *self.records,
        ]
        matches = search_text(records, "train booking")
        self.assertEqual(matches[0], {"path": "screenshot.png", "page": None})
        self.assertEqual(len(matches), 3)


if __name__ == "__main__":
    unittest.main()
