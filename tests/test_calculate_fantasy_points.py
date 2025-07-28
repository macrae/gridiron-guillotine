import unittest

# Make sure to import the function from your script
from fantasy_points import calculate_fantasy_points


class TestFantasyPointsCalculation(unittest.TestCase):
    def test_fantasy_points_calculation(self):
        test_stats = {
            'Passing Yards': 250,
            'Passing TDs': 2,
            'Passing Interceptions': 1,
            'Passing 2-Point Conversions': 0,
            'Rushing Yards': 50,
            'Rushing TDs': 1,
            'Rushing 2-Point Conversions': 0,
            'Receptions': 5,
            'Receiving Yards': 50,
            'Receiving TDs': 1,
            'Receiving 2-Point Conversions': 0,
            'Offensive Fumble Recovery TD': 0,
            'Fumbles Lost': 1,
            'Kicking PATs': 3,
            'Kicking FGs': 9  # Assume 3 FGs made, none 50+ yards
        }

        # Expected points calculation based on the test_stats
        # Calculate manually to verify the correctness:
        # Passing: 250/25 * 10 + 2*6 - 1*2 + 0*2 = 10 + 12 - 2 + 0 = 20
        # Rushing: 50/10 * 5 + 1*6 + 0*2 = 5 + 6 + 0 = 11
        # Receiving: 5*1 + 50/10 * 5 + 1*6 + 0*2 = 5 + 5 + 6 + 0 = 16
        # Fumbles: 0*6 - 1*2 = -2
        # Kicking: 3*1 + 9*3 = 3 + 27 = 30
        # Total expected points = 20 (Passing) + 11 (Rushing) + 16 (Receiving) - 2 (Fumbles) + 30 (Kicking) = 75
        expected_points = 51

        # Function call
        calculated_points = calculate_fantasy_points(test_stats)

        # Assert
        self.assertEqual(calculated_points, expected_points)


# If this file is run directly, run the tests
if __name__ == '__main__':
    unittest.main()
