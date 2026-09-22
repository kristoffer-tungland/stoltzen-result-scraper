import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from eqtiming_scraper import (  # noqa: E402
    StoltzenHistory,
    build_output_rows,
    calculate_difference,
    merge_eq_rows,
    parse_eq_rows,
    parse_history_html,
)


class FixtureHistory:
    def history_for(self, name, current_year):
        if name == "Åse Ødegård":
            return {"BesteTidligere": "11:30", "BesteÅr": 2022, "Deltagelser": 2}
        return {"BesteTidligere": None, "BesteÅr": None, "Deltagelser": 0}


class EqtimingParserTests(unittest.TestCase):
    def test_current_result_format_and_startlist_are_merged(self):
        result_payload = {
            "Items": [{
                "Deltaker": {"UID": "a", "Navn": "Åse Ødegård", "Klasse": "Kvinner 35-39"},
                "Formatert": "10:01", "StatusTekst": "Fullført",
            }]
        }
        start_payload = {
            "Items": [{
                "Deltaker": {"UID": "a", "Navn": "Åse Ødegård", "Klasse": "Kvinner 35-39"},
            }, {
                "Id": "b", "Utover": {"NavnFormatert": "Ole Hansen"},
                "Klasse": {"Navn": "Menn 40-44"}, "KlubbTeamFormatert": "COWI",
            }]
        }
        merged = merge_eq_rows(parse_eq_rows(result_payload), parse_eq_rows(start_payload))
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["Tid"], "10:01")
        self.assertIsNone(merged[1]["Tid"])
        self.assertEqual(merged[1]["Gruppe"], "Mann")

    def test_realistic_nested_eq_2025_shape(self):
        payload = {"Items": [{
            "Deltaker": {
                "Id": 77,
                "Utover": {"NavnFormatert": "Kari Nordmann", "Fornavn": "Kari", "Etternavn": "Nordmann"},
                "Klasse": {"Navn": "Kvinner 30-39"},
            },
            "Formatert": "00:09:12", "StatusTekst": "Fullført",
        }]}
        row = parse_eq_rows(payload)[0]
        self.assertEqual(row["_uid"], "77")
        self.assertEqual(row["Navn"], "Kari Nordmann")
        self.assertEqual(row["Klasse"], "Kvinner 30-39")
        self.assertEqual(row["Tid"], "9:12")

    def test_direct_profile_search_response_is_parsed(self):
        class Response:
            encoding = "utf-8"
            text = '<div id="participations">5</div><div id="yeartimes"><table><tr><td>2024</td><td>10.55</td></tr></table></div>'
            def raise_for_status(self):
                pass

        class Session:
            def get(self, url, timeout):
                return Response()

        history = StoltzenHistory(session=Session())
        parsed = history.history_for("Kari Nordmann", 2026)
        self.assertEqual(parsed["BesteTidligere"], "10:55")
        self.assertEqual(parsed["Deltagelser"], 5)

    def test_history_uses_best_pre_current_year_and_counts_entries(self):
        html = """
        <div id="yeartimes"><table>
          <tr><th>År</th><th>Tid</th></tr>
          <tr><td>2022</td><td>11.30</td></tr>
          <tr><td>2023</td><td>12.10</td></tr>
          <tr><td>2024</td><td>10.55</td></tr>
        </table></div>
        """
        history = parse_history_html(html, 2026)
        self.assertEqual(history["BesteTidligere"], "10:55")
        self.assertEqual(history["BesteÅr"], 2024)
        self.assertEqual(history["Deltagelser"], 3)

    def test_output_calculates_new_best_and_leaves_history_for_unfinished(self):
        rows = [{"Navn": "Åse Ødegård", "Tid": "10:01", "Klasse": "Kvinner", "Gruppe": "Dame"},
                {"Navn": "Ole Hansen", "Tid": None, "Klasse": "Menn", "Gruppe": "Mann"}]
        output = build_output_rows(rows, 2026, FixtureHistory())
        self.assertEqual(output[0]["NyBestetid"], True)
        self.assertEqual(output[0]["Differanse"], "-1:29")
        self.assertIsNone(output[1]["Tid"])
        self.assertEqual(output[1]["Deltagelser"], 0)

    def test_difference(self):
        self.assertEqual(calculate_difference("12:00", "11:45"), "+0:15")

    def test_zero_time_is_not_a_finished_result(self):
        payload = {"Items": [{
            "Deltaker": {
                "UID": 12,
                "Utover": {"NavnFormatert": "Ikke fullført"},
                "Klasse": {"Navn": "Menn 40-44 år"},
            },
            "Formatert": "0:00",
            "StatusTekst": "DNS",
        }]}
        self.assertIsNone(parse_eq_rows(payload)[0]["Tid"])


if __name__ == "__main__":
    unittest.main()
