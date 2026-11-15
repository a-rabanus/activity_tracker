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
    parse_session,
    parse_trial_id,
)

DAY = date(2026, 11, 15)


class BuildTrialId(unittest.TestCase):
    def test_example(self):
        self.assertEqual(build_trial_id(DAY, 3, 1, "SC02"), "20261115_P03_S01_SC02")

    def test_loose_input_is_normalized(self):
        for person in (3, "3", "03", "P3", "p03", " P03 "):
            for session in (1, "1", "01", "S1", "s01"):
                for scenario in (2, "2", "02", "SC2", "sc02", " SC02 "):
                    with self.subTest(person=person, session=session, scenario=scenario):
                        self.assertEqual(build_trial_id(DAY, person, session, scenario), "20261115_P03_S01_SC02")

    def test_two_digit_bounds(self):
        self.assertEqual(build_trial_id(DAY, 99, 99, 1), "20261115_P99_S99_SC01")
        self.assertEqual(build_trial_id(DAY, "P01", "S10", "SC01"), "20261115_P01_S10_SC01")

    def test_invalid_person(self):
        for person in ("0", "P00", "00", "100", "P100", "", "abc", "X3", "3.0", "-1", "１"):
            with self.subTest(person=person), self.assertRaises(ValueError):
                build_trial_id(DAY, person, 1, "SC01")

    def test_invalid_session(self):
        for session in ("0", "S00", "100", "", "abc", "SC01", "P01", "1.5"):
            with self.subTest(session=session), self.assertRaises(ValueError):
                build_trial_id(DAY, 3, session, "SC01")

    def test_invalid_scenario(self):
        for scenario in ("0", "SC00", "SC03", "3", "99", "", "scenario01", "S01", "SC1x"):
            with self.subTest(scenario=scenario), self.assertRaises(ValueError):
                build_trial_id(DAY, 3, 1, scenario)

    def test_result_matches_convention(self):
        trial_id = build_trial_id(DAY, 42, 7, "SC02")
        self.assertRegex(trial_id, r"^\d{8}_P\d{2}_S\d{2}_SC\d{2}$")
        self.assertEqual(parse_trial_id(trial_id), (DAY, 42, 7, "SC02"))


class ParseTrialId(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_trial_id("20261115_P03_S01_SC02"), (DAY, 3, 1, "SC02"))
        self.assertEqual(parse_trial_id("20240229_P99_S99_SC01"), (date(2024, 2, 29), 99, 99, "SC01"))

    def test_invalid_format(self):
        for text in (
            "20261115_P3_S01_SC02",  # person not two digits
            "20261115_P03_S1_SC02",  # session not two digits
            "20261115_P03_S01_SC2",  # scenario not two digits
            "20261115_p03_S01_SC02",  # lower-case p
            "20261115_P03_s01_SC02",  # lower-case s
            "20261115_P03_S01_sc02",  # lower-case sc
            "20261115_P03_SC02_S01",  # wrong order
            "20261115_P03_S01",  # scenario missing
            "20261115_P03_SC02",  # session missing
            "2026111_P03_S01_SC02",  # 7-digit date
            "20261115-P03-S01-SC02",  # wrong separator
            "20261115_P03_EVT-scenario01_T01",  # old format
            "20261115_P03_S01_SC02 x",
            "",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_trial_id(text)

    def test_date_must_exist(self):
        for text in ("20261315_P03_S01_SC02", "20261132_P03_S01_SC02", "20250229_P03_S01_SC02"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_trial_id(text)

    def test_ranges(self):
        for text in (
            "20261115_P00_S01_SC01",
            "20261115_P03_S00_SC01",
            "20261115_P03_S01_SC00",
            "20261115_P03_S01_SC03",
            "20261115_P03_S01_SC99",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_trial_id(text)


class ParseParts(unittest.TestCase):
    def test_person(self):
        self.assertEqual(parse_person("3"), 3)
        self.assertEqual(parse_person("P07"), 7)

    def test_session(self):
        self.assertEqual(parse_session("1"), 1)
        self.assertEqual(parse_session("s12"), 12)

    def test_scenario(self):
        self.assertEqual(parse_scenario("1"), "SC01")
        self.assertEqual(parse_scenario("sc2"), "SC02")

    def test_scenarios_constant(self):
        self.assertEqual(SCENARIOS, ["SC01", "SC02"])
        for s in SCENARIOS:
            self.assertRegex(s, r"^SC\d{2}$")


class OutputFiles(unittest.TestCase):
    def test_names_start_with_trial_id(self):
        csv_path, db_path = output_paths(Path("data"), "20261115_P03_S01_SC02")
        self.assertEqual(csv_path.name, "20261115_P03_S01_SC02_labels.csv")
        self.assertEqual(db_path.name, "20261115_P03_S01_SC02_labels.sqlite")

    def test_is_taken_per_person_session_scenario(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(is_taken(Path(d), "20261115_P03_S01_SC02"))
            (Path(d) / "20261115_P03_S01_SC02_labels.sqlite").touch()
            self.assertTrue(is_taken(Path(d), "20261115_P03_S01_SC02"))
            self.assertFalse(is_taken(Path(d), "20261115_P03_S02_SC02"))  # other session
            self.assertFalse(is_taken(Path(d), "20261115_P03_S01_SC01"))  # other scenario


if __name__ == "__main__":
    unittest.main()
