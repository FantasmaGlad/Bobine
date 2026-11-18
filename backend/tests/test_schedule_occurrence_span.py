import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException

from app.api.paging import whole
from app.api.routes.schedule.schedules import MAX_OCCURRENCE_SPAN, list_occurrences


class _EmptyQuery:
    def filter(self, *_args):
        return self

    def all(self):
        return []


class _Db:
    def query(self, *_args):
        return _EmptyQuery()


class OccurrenceSpanTest(unittest.TestCase):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_span_at_the_limit_is_accepted(self):
        self.assertEqual(list_occurrences(self.start, self.start + MAX_OCCURRENCE_SPAN, db=_Db(), page=whole()), [])

    def test_span_past_the_limit_is_refused(self):
        with self.assertRaises(HTTPException) as caught:
            list_occurrences(self.start, self.start + MAX_OCCURRENCE_SPAN + timedelta(seconds=1), db=_Db(), page=whole())
        self.assertEqual(caught.exception.status_code, 422)

    def test_span_of_centuries_is_refused(self):
        with self.assertRaises(HTTPException):
            list_occurrences(datetime(1, 1, 2, tzinfo=timezone.utc), datetime(9999, 1, 1, tzinfo=timezone.utc),
                             db=_Db(), page=whole())


if __name__ == "__main__":
    unittest.main()
