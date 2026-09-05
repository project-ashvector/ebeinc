import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dj_status_logic", ROOT / "tools/dj_app.py")
DJ_APP = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(DJ_APP)


class StationDisplayStatusTests(unittest.TestCase):
    def test_live_stream_with_healthy_cache_is_live(self):
        self.assertEqual(
            DJ_APP.station_display_status({"online": True}, {"status": "healthy"})[0],
            "STATION LIVE",
        )

    def test_live_stream_with_degraded_cache_stays_live(self):
        self.assertEqual(
            DJ_APP.station_display_status({"online": True}, {"status": "degraded"})[0],
            "STATION LIVE   •   HOT CACHE DEGRADED",
        )

    def test_live_stream_with_unknown_cache_stays_live(self):
        self.assertEqual(
            DJ_APP.station_display_status({"online": True}, {})[0],
            "STATION LIVE   •   HOT CACHE DEGRADED",
        )

    def test_offline_stream_is_unavailable_even_with_healthy_cache(self):
        self.assertEqual(
            DJ_APP.station_display_status({"online": False}, {"status": "healthy"})[0],
            "STATION UNAVAILABLE",
        )


if __name__ == "__main__":
    unittest.main()
