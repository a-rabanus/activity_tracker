"""Tests for the trial ID functions. Run: python -m unittest discover -s tests"""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from activity_timestamps.naming import (
    SCENARIOS,
    build_trial_id,
    is_taken,
    output_paths,
    parse_person,
    parse_scenario,
    parse_trial_id,
)

DAY = date(2026, 11, 15)


class BuildTrialId(unittest.TestCase):
    def test_example(self):
        self.assertEqual(build_trial_id(DAY, 3, "S01"), "20261115_P03_S01")

    def test_loose_input_is_normalized(self):
        for person in (3, "3", "03", "P3", "p03", " P03 "):
            for scenario in (1, "1", "01", "S1", "s01", " S01 "):
                with self.subTest(person=person, scenario=scenario):
                    self.assertEqual(build_trial_id(DAY, person, scenario), "20261115_P03_S01")

    def test_two_digit_bounds(self):
        self.assertEqual(build_trial_id(DAY, 99, 2), "20261115_P99_S02")
        self.assertEqual(build_trial_id(DAY, "P01", "S02"), "20261115_P01_S02")

    def test_invalid_person(self):
        for person in ("0", "P00", "00", "100", "P100", "", "abc", "X3", "3.0", "-1", "１"):
            with self.subTest(person=person), self.assertRaises(ValueError):
                build_trial_id(DAY, person, "S01")

    def test_invalid_scenario(self):
        for scenario in ("0", "S00", "S03", "3", "99", "", "scenario01", "T01", "S1x"):
            with self.subTest(scenario=scenario), self.assertRaises(ValueError):
                build_trial_id(DAY, 3, scenario)

    def test_result_matches_convention(self):
        trial_id = build_trial_id(DAY, 42, "S02")
        self.assertRegex(trial_id, r"^\d{8}_P\d{2}_S\d{2}$")
        self.assertEqual(parse_trial_id(trial_id), (DAY, 42, "S02"))


class ParseTrialId(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_trial_id("20261115_P03_S01"), (DAY, 3, "S01"))
        self.assertEqual(parse_trial_id("20240229_P99_S02"), (date(2024, 2, 29), 99, "S02"))

    def test_invalid_format(self):
        for text in (
            "20261115_P3_S01",  # person not two digits
            "20261115_P03_S1",  # scenario not two digits
            "20261115_p03_S01",  # lower-case p
            "20261115_P03_s01",  # lower-case s
            "2026111_P03_S01",  # 7-digit date
            "20261115-P03-S01",  # wrong separator
            "20261115_P03_S01_T01",  # old trial number
            "20261115_P03_EVT-scenario01_T01",  # old format
            "20261115_P03_S01 x",
            "",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_trial_id(text)

    def test_date_must_exist(self):
        for text in ("20261315_P03_S01", "20261132_P03_S01", "20250229_P03_S01", "20260000_P03_S01"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_trial_id(text)

    def test_person_and_scenario_ranges(self):
        for text in ("20261115_P00_S01", "20261115_P03_S00", "20261115_P03_S03", "20261115_P03_S99"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_trial_id(text)


class ParseParts(unittest.TestCase):
    def test_person(self):
        self.assertEqual(parse_person("3"), 3)
        self.assertEqual(parse_person("P07"), 7)

    def test_scenario(self):
        self.assertEqual(parse_scenario("1"), "S01")
        self.assertEqual(parse_scenario("s2"), "S02")

    def test_scenarios_constant(self):
        self.assertEqual(SCENARIOS, ["S01", "S02"])
        for s in SCENARIOS:
            self.assertRegex(s, r"^S\d{2}$")


class OutputFiles(unittest.TestCase):
    def test_names_start_with_trial_id(self):
        csv_path, db_path = output_paths(Path("data"), "20261115_P03_S01")
        self.assertEqual(csv_path.name, "20261115_P03_S01_labels.csv")
        self.assertEqual(db_path.name, "20261115_P03_S01_labels.sqlite")

    def test_is_taken(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(is_taken(Path(d), "20261115_P03_S01"))
            (Path(d) / "20261115_P03_S01_labels.sqlite").touch()
            self.assertTrue(is_taken(Path(d), "20261115_P03_S01"))
            self.assertFalse(is_taken(Path(d), "20261115_P03_S02"))


if __name__ == "__main__":
    unittest.main()
