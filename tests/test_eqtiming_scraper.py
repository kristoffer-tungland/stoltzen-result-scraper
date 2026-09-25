import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from eqtiming_scraper import (  # noqa: E402
    EqtimingScraper,
    StoltzenHistory,
    build_output_rows,
    calculate_difference,
    merge_eq_rows,
    parse_eq_rows,
    parse_eq_details,
    parse_eq_splits,
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
        self.assertEqual(output[0]["Bestetid"], "11:30")
        self.assertEqual(output[0]["Deltagelser"], 3)
        self.assertIsNone(output[1]["Tid"])
        self.assertEqual(output[1]["Deltagelser"], 0)

    def test_difference(self):
        self.assertEqual(calculate_difference("12:00", "11:45"), "+0:15")

    def test_first_time_participant_is_not_marked_as_new_best(self):
        rows = [{"Navn": "Ny Deltaker", "Tid": "15:00", "Klasse": "Menn", "Gruppe": "Mann"}]
        output = build_output_rows(rows, 2026, FixtureHistory())
        self.assertEqual(output[0]["Deltagelser"], 1)
        self.assertIsNone(output[0]["BesteTidligere"])
        self.assertEqual(output[0]["NyBestetid"], False)
        self.assertIsNone(output[0]["Differanse"])
        self.assertIsNone(output[0]["Bestetid"])

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

    def test_participation_count_uses_current_year_when_stoltzen_has_it(self):
        html = """
        <div id="participations">4</div>
        <table>
          <tr><td>2024</td><td>11.12</td></tr>
          <tr><td>2025</td><td>11.30</td></tr>
        </table>
        """
        history = parse_history_html(html, 2025)
        self.assertEqual(history["Deltagelser"], 4)
        self.assertTrue(history["ÅretsTidRegistrert"])
        self.assertEqual(history["BesteÅr"], 2024)

    def test_finished_current_year_is_counted_exactly_once(self):
        class History:
            def history_for(self, name, current_year):
                return {"Deltagelser": 4, "ÅretsTidRegistrert": True,
                        "BesteTidligere": "11:12", "BesteÅr": 2024}

        finished = build_output_rows([{"Navn": "Kari", "Tid": "11:30"}], 2025, History())[0]
        unfinished = build_output_rows([{"Navn": "Kari", "Tid": None}], 2025, History())[0]
        self.assertEqual(finished["Deltagelser"], 4)
        self.assertEqual(unfinished["Deltagelser"], 4)
        self.assertEqual(finished["Bestetid"], "11:12")

    def test_only_a_valid_current_finish_increments_stoltzen_count(self):
        history = parse_history_html(
            '<!-- <span id="yeartimes">2022|12.17;2024|11.12;</span> -->'
            '<div id="participations">2</div>', 2026)
        class History:
            def history_for(self, name, current_year):
                return history

        finished = build_output_rows([{"Navn": "Kari", "Tid": "11:30"}], 2026, History())[0]
        unfinished = build_output_rows([{"Navn": "Kari", "Tid": None}], 2026, History())[0]
        self.assertFalse(history["ÅretsTidRegistrert"])
        self.assertEqual(finished["Deltagelser"], 3)
        self.assertEqual(unfinished["Deltagelser"], 2)

    def test_eq_person_times_are_cumulative_and_exclude_finish(self):
        payload = {"Items": [
            {"StasjonsOppsett": {"Navn": "Mål", "Er_stopp": True, "Sortering": 3},
             "Formatert": "11:30", "Splitt": {"Formatert": "6:09"}, "StatusTekst": "TIME"},
            {"StasjonsOppsett": {"Navn": "Halvveis", "Sortering": 2},
             "Formatert": "5:21", "Splitt": {"Formatert": "3:17"}, "StatusTekst": "TIME"},
            {"StasjonsOppsett": {"Navn": "Starten", "Sortering": 1},
             "Formatert": "2:04", "Splitt": {"Formatert": "2:04"}, "StatusTekst": "TIME"},
        ]}
        self.assertEqual(parse_eq_splits(payload), "Starten 2:04 · Halvveis 5:21")

    def test_eq_details_use_stair_segment_and_finish_clock(self):
        payload = {"Items": [
            {"StasjonsOppsett": {"Navn": "Starten", "Sortering": 1},
             "Formatert": "2:04", "StatusTekst": "TIME"},
            {"StasjonsOppsett": {"Navn": "Trappene", "Sortering": 3},
             "Formatert": "9:52", "Splitt": {"Formatert": "4:31"}, "StatusTekst": "TIME"},
            {"StasjonsOppsett": {"Navn": "Mål", "Er_stopp": True},
             "Formatert": "11:30", "PasseringstidAsDateTime": "2025-09-26T16:37:40",
             "StatusTekst": "TIME"},
        ]}
        details = parse_eq_details(payload)
        self.assertEqual(details["StartenTid"], "2:04")
        self.assertEqual(details["Trappetid"], "4:31")
        self.assertEqual(details["Maalpassering"], "2025-09-26T16:37:40")
        self.assertNotIn("Mål", details["Mellomtider"])

    def test_fetch_current_enriches_result_with_person_splits(self):
        class Scraper(EqtimingScraper):
            def fetch_json(self, url):
                if "/Result/Contestant/Times/" in url:
                    return {"Items": [{"StasjonsOppsett": {"Navn": "Halvveis", "Sortering": 2},
                                       "Formatert": "5:21", "StatusTekst": "TIME"}]}
                if "/Result/Search/" in url:
                    return {"Items": [{"Deltaker": {"UID": 7, "Utover": {"NavnFormatert": "Kari"}},
                                       "Formatert": "11:30", "KlubbTeamFormatert": "COWI"}]}
                return {"Items": []}

        rows = Scraper().fetch_current("78991", "COWI")
        self.assertEqual(rows[0]["Mellomtider"], "Halvveis 5:21")

    def test_finished_result_carries_highlight_fields_into_csv_rows(self):
        class Scraper(EqtimingScraper):
            detail_calls = 0
            def fetch_json(self, url):
                if "/Result/Contestant/Times/" in url:
                    self.detail_calls += 1
                    return {"Items": [
                        {"StasjonsOppsett": {"Navn": "Starten", "Sortering": 1},
                         "Formatert": "2:04", "StatusTekst": "TIME"},
                        {"StasjonsOppsett": {"Navn": "Trappene", "Sortering": 3},
                         "Formatert": "9:52", "Splitt": {"Formatert": "4:31"}, "StatusTekst": "TIME"},
                        {"StasjonsOppsett": {"Navn": "Mål", "Er_stopp": True},
                         "Formatert": "11:30", "PasseringstidAsDateTime": "2025-09-26T16:37:40",
                         "StatusTekst": "TIME"},
                    ]}
                if "/Result/Search/" in url:
                    return {"Items": [{"Deltaker": {"UID": 7, "Utover": {"NavnFormatert": "Kari"}},
                                       "Formatert": "11:30", "KlubbTeamFormatert": "COWI"}]}
                return {"Items": []}

        scraper = Scraper()
        row = build_output_rows(scraper.fetch_current("78991", "COWI"), 2025, no_history=True)[0]
        self.assertEqual(row["Trappetid"], "4:31")
        self.assertEqual(row["StartenTid"], "2:04")
        self.assertEqual(row["Maalpassering"], "2025-09-26T16:37:40")
        scraper.fetch_current("78991", "COWI")
        self.assertEqual(scraper.detail_calls, 1)

    def test_unfinished_runner_gets_updated_split_on_next_refresh(self):
        class Scraper(EqtimingScraper):
            split_time = "2:04"
            def fetch_json(self, url):
                if "/Result/Contestant/Times/" in url:
                    return {"Items": [{"StasjonsOppsett": {"Navn": "Starten", "Sortering": 1},
                                       "Formatert": self.split_time, "StatusTekst": "TIME"}]}
                if "/Result/Search/" in url:
                    return {"Items": [{"Deltaker": {"UID": 7, "Utover": {"NavnFormatert": "Kari"}},
                                       "StatusTekst": "TIME", "KlubbTeamFormatert": "COWI"}]}
                return {"Items": []}

        scraper = Scraper()
        self.assertEqual(scraper.fetch_current("78640", "COWI")[0]["Mellomtider"], "Starten 2:04")
        scraper.split_time = "2:10"
        self.assertEqual(scraper.fetch_current("78640", "COWI")[0]["Mellomtider"], "Starten 2:10")

    def test_finished_runner_is_refetched_until_goal_passage_is_available(self):
        class Scraper(EqtimingScraper):
            include_goal = False
            def fetch_json(self, url):
                if "/Result/Contestant/Times/" in url:
                    items = [{"StasjonsOppsett": {"Navn": "Halvveis", "Sortering": 1},
                              "Formatert": "5:21", "StatusTekst": "TIME"}]
                    if self.include_goal:
                        items.append({"StasjonsOppsett": {"Navn": "Mål", "Er_stopp": True},
                                      "Formatert": "11:30", "StatusTekst": "TIME"})
                    return {"Items": items}
                if "/Result/Search/" in url:
                    return {"Items": [{"Deltaker": {"UID": 7, "Utover": {"NavnFormatert": "Kari"}},
                                       "Formatert": "11:30", "KlubbTeamFormatert": "COWI"}]}
                return {"Items": []}

        scraper = Scraper()
        self.assertEqual(scraper.fetch_current("78640", "COWI")[0]["Mellomtider"], "Halvveis 5:21")
        self.assertEqual(scraper._split_cache, {})
        scraper.include_goal = True
        self.assertEqual(scraper.fetch_current("78640", "COWI")[0]["Mellomtider"], "Halvveis 5:21")
        self.assertTrue(scraper._split_cache)

    def test_commented_year_times_use_final_times_not_splits(self):
        html = """
        <!-- <span id="yeartimes">2023|15.54;2024|14.48;2025|15.12;</span> -->
        <table><tr><td>2024</td><td>01:09</td><td>14:48</td></tr></table>
        """
        history = parse_history_html(html, 2025)
        self.assertEqual(history["BesteTidligere"], "14:48")
        self.assertEqual(history["BesteÅr"], 2024)


if __name__ == "__main__":
    unittest.main()
