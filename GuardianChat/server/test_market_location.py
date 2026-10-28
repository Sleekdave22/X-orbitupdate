"""Location-filter contracts that must survive readability-only edits."""
import copy
import unittest

import market_location


class MarketLocationTest(unittest.TestCase):
    def test_absent_and_zero_coordinates_are_distinct(self):
        self.assertEqual(market_location.coordinates(None, ""), (None, None))
        self.assertEqual(market_location.coordinates("0", "0"), (0.0, 0.0))
        self.assertEqual(market_location.coordinates("6.52448", "3.37923"), (6.52, 3.38))

    def test_validation_retains_the_public_error_message(self):
        for latitude, longitude in [(None, 0), (False, 0), (0, 181), ("nan", 0), ([], 0)]:
            with self.subTest(latitude=latitude, longitude=longitude):
                with self.assertRaisesRegex(ValueError, "Supply valid approximate latitude and longitude together"):
                    market_location.coordinates(latitude, longitude)

    def test_refinement_copies_rows_preserves_order_and_keeps_unknowns(self):
        items = [
            {"id": "near", "latitude": 0, "longitude": .1},
            {"id": "unknown", "distance_km": 999},
            {"id": "far", "latitude": 0, "longitude": 1},
        ]
        before = copy.deepcopy(items)
        result = market_location.refine(items, {"latitude": ["0"], "longitude": ["0"]}, "worldwide")
        self.assertEqual([item["id"] for item in result], ["near", "unknown", "far"])
        self.assertIsNone(result[1]["distance_km"])
        self.assertEqual(result[0]["distance_km"], 11.1)
        self.assertEqual(items, before)
        self.assertTrue(all(edited is not original for edited, original in zip(result, items)))

    def test_only_radius_mode_excludes_unknown_and_outside_distances(self):
        items = [
            {"id": "near", "latitude": 0, "longitude": .1},
            {"id": "unknown"},
            {"id": "far", "latitude": 0, "longitude": 1},
        ]
        query = {"latitude": ["0"], "longitude": ["0"], "radius_km": ["25"]}
        self.assertEqual([item["id"] for item in market_location.refine(items, query, "distance")], ["near"])
        self.assertEqual(len(market_location.refine(items, query, "worldwide")), 3)
        self.assertEqual(len(market_location.refine(items, {}, "worldwide")), 3)

    def test_radius_validation_and_origin_requirement(self):
        with self.assertRaisesRegex(ValueError, "Choose your approximate search location first"):
            market_location.refine([], {}, "distance")
        for radius in ("0", "20001", "nan", "bad"):
            with self.subTest(radius=radius):
                with self.assertRaisesRegex(ValueError, "Choose a distance between 1 and 20,000 km"):
                    market_location.refine([], {"latitude": ["0"], "longitude": ["0"], "radius_km": [radius]}, "distance")
        for radius in ("1", "20000"):
            self.assertEqual(market_location.refine([], {"latitude": ["0"], "longitude": ["0"], "radius_km": [radius]}, "distance"), [])


if __name__ == "__main__":
    unittest.main()
