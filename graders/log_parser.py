import unittest
from parser import parse_line, parse_lines
class Grade(unittest.TestCase):
    def test_spaces(self):
        self.assertEqual(parse_line(" 2024-02-29T23:59:59Z\tWARNING  a  b \t"),
          dict(timestamp="2024-02-29T23:59:59Z",level="WARNING",message="a  b"))
    def test_invalid(self):
        for x in (None,3,"","2023-02-29T00:00:00Z INFO bad","2024-01-01T24:00:00Z INFO bad",
                  "2024-01-01T00:00:00Z TRACE bad","2024-01-01T00:00:00Z INFO "):
            self.assertIsNone(parse_line(x),repr(x))
    def test_order(self):
        lines=[f"2024-01-01T00:00:00Z INFO line {i}" for i in range(40)]
        self.assertEqual([r["message"] for r in parse_lines(["bad"]+lines)], [f"line {i}" for i in range(40)])
