import unittest
from gridiron_guillotine.data.processors import ScoreCalculator


class TestFantasyPointsCalculation(unittest.TestCase):
    def test_fantasy_points_calculation(self):
        test_stats = {
            'passing_yards': 250,
            'passing_tds': 2,
            'interceptions': 1,
            'rushing_yards': 50,
            'rushing_tds': 1,
            'receptions': 5,
            'receiving_yards': 50,
            'receiving_tds': 1,
            'fumbles_lost': 1,
            'extra_points': 3,
            'field_goals': 3  # 3 field goals made
        }

        # Expected points calculation based on the test_stats
        # Calculate manually to verify the correctness:
        # Passing: 250*0.04 + 2*4.0 - 1*2.0 = 10 + 8 - 2 = 16
        # Rushing: 50*0.1 + 1*6.0 = 5 + 6 = 11
        # Receiving: 5*1.0 + 50*0.1 + 1*6.0 = 5 + 5 + 6 = 16
        # Fumbles: -1*2.0 = -2
        # Kicking: 3*1.0 + 3*3.0 = 3 + 9 = 12
        # Total expected points = 16 + 11 + 16 - 2 + 12 = 53
        expected_points = 53

        # Function call
        calculator = ScoreCalculator()
        calculated_points = calculator.calculate_fantasy_points(test_stats)

        # Assert
        self.assertEqual(calculated_points, expected_points)


# If this file is run directly, run the tests
if __name__ == '__main__':
    unittest.main()
