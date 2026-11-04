import unittest
import numpy as np
import build_regional_dashboards as b


class EPSAggregationTests(unittest.TestCase):
    def test_share_issuance_does_not_turn_unchanged_eps_into_growth(self):
        # One stock doubles its shares and earnings, but EPS remains 2.
        result, *_ = b.aggregate_share_weighted_eps_change(
            np.array([[2., 2.]]), np.array([[10., 10.]]),
            np.array([[100., 200.]]), 1, 0)
        self.assertEqual(result, 0.)

    def test_each_date_has_its_own_share_denominator(self):
        eps = np.array([[2., 3.], [4., 5.]])
        price = np.full((2, 2), 10.)
        cap = np.array([[100., 200.], [300., 200.]])
        result, changes, weights, valid = b.aggregate_share_weighted_eps_change(eps, price, cap, 1, 0)
        self.assertAlmostEqual(result, 4. / 3.5 - 1)
        self.assertAlmostEqual(result, np.sum(changes[valid] * weights[valid]) / weights[valid].sum())

    def test_missing_endpoint_uses_matched_universe(self):
        result, *_ = b.aggregate_share_weighted_eps_change(
            np.array([[2., 3.], [100., np.nan]]), np.full((2, 2), 10.),
            np.full((2, 2), 100.), 1, 0)
        self.assertEqual(result, .5)

    def test_fy2_vs_fy1_uses_levels_without_clipping(self):
        result = b.aggregate_forward_eps_growth(np.array([1., 2.]), np.array([10., 2.]),
                                               np.array([10., 10.]), np.array([100., 100.]))
        self.assertEqual(result, 3.)


if __name__ == '__main__':
    unittest.main()
