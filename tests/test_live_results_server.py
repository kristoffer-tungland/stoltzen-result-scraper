import json
import os
import sys
import tempfile
import threading
import unittest
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from live_results_server import ResultFileHandler, make_viewer_url  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent


class YearProfileTests(unittest.TestCase):
    def test_vscode_profiles_keep_each_year_in_its_own_file(self):
        config = json.loads((ROOT / ".vscode" / "launch.json").read_text(encoding="utf-8"))
        profiles = {item["name"]: item for item in config["configurations"]}
        expected = {
            "Stoltzen: Live-resultater 2026": ("78640", "2026", "results.csv"),
            "Stoltzen: Resultater 2025": ("78991", "2025", "results_2025.csv"),
        }
        for name, (event, year, output) in expected.items():
            args = profiles[name]["args"]
            values = dict(zip(args[::2], args[1::2]))
            self.assertEqual(values["--event-id"], event)
            self.assertEqual(values["--year"], year)
            self.assertEqual(values["--output"], output)

    def test_viewer_url_identifies_active_year(self):
        url = make_viewer_url(8765, ROOT / "results_2025.csv", ROOT, 2025, "78991")
        self.assertEqual(url, "http://127.0.0.1:8765/results_viewer.html?year=2025&event=78991")

    def test_results_alias_points_to_active_year_file(self):
        handler = object.__new__(ResultFileHandler)
        handler.result_path = ROOT / "results_2025.csv"
        self.assertEqual(handler.translate_path("/results.csv?t=123"), str(handler.result_path))

    def test_http_results_alias_serves_the_selected_year(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results_2025.csv"
            output.write_text("Navn,Tid\n2025-runner,11:00\n", encoding="utf-8")
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                partial(ResultFileHandler, directory=directory, result_path=output),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/results.csv?t=1") as response:
                    self.assertIn("2025-runner,11:00", response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
