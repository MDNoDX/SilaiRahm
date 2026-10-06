"""The code itself: no unused imports, no names that are used but never defined."""
from django.test import SimpleTestCase

from tools import check_code


class CodeTests(SimpleTestCase):
    def test_code_check_is_clean(self):
        problems = check_code.run()
        self.assertEqual(problems, [], "\n".join(problems))
