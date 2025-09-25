#!/usr/bin/env python3
"""
Stoltzen Result Scraper

This script fetches race results from stoltzen.no, parses participant data,
and outputs structured JSON with participant profiles including historical data.
"""

import re
import json
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple
import time
import argparse
import sys


class StoltzenScraper:
    def __init__(self):
        self.base_url = "http://stoltzen.no"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Charset': 'utf-8'
        })
    
    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a web page."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            # Force UTF-8 encoding to handle Norwegian characters
            response.encoding = 'utf-8'
            return BeautifulSoup(response.text, 'html.parser')
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def parse_time(self, time_str: str) -> Optional[str]:
        """Parse and normalize time string."""
        if not time_str:
            return None
        
        # Clean up the time string
        time_str = time_str.strip()
        
        # Match time patterns like "1:23:45" or "23:45" or "1.23.45"
        time_pattern = r'(\d{1,2})[.:](\d{2})[.:](\d{2})'
        match = re.search(time_pattern, time_str)
        
        if match:
            hours, minutes, seconds = match.groups()
            # If hours > 23, it's probably minutes:seconds format
            if int(hours) > 23:
                return f"{minutes}:{seconds}"
            return f"{hours}:{minutes}:{seconds}" if int(hours) > 0 else f"{minutes}:{seconds}"
        
        # Try minutes:seconds pattern
        time_pattern = r'(\d{1,3})[.:](\d{2})'
        match = re.search(time_pattern, time_str)
        if match:
            minutes, seconds = match.groups()
            return f"{minutes}:{seconds}"
        
        return time_str
    
    def extract_participant_id(self, link: str) -> Optional[str]:
        """Extract participant ID from profile link."""
        if not link:
            return None
        
        # Look for id parameter in URL
        match = re.search(r'id=(\d+)', link)
        if match:
            return match.group(1)
        return None
    
    def parse_results_table(self, soup: BeautifulSoup) -> Dict[str, List[Dict]]:
        """Parse the main results table and categorize participants."""
        results = {"Mann": [], "Dame": [], "Pluss": []}
        
        # Find the results table - look for table with participant data
        tables = soup.find_all('table')
        results_table = None
        
        for table in tables:
            # Look for table that contains participant links
            if table.find('a', href=re.compile(r'stat\.php')):
                results_table = table
                break
        
        if not results_table:
            print("No results table found on the page")
            return results
        
        rows = results_table.find_all('tr')
        print(f"Found {len(rows)} rows in results table", file=__import__('sys').stderr)
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 3:  # Need at least position, name, time
                continue
            
            try:
                # Extract data from row - typical format: position, name, time, category
                position_text = cells[0].get_text().strip()
                
                # Skip if first cell doesn't look like a position number
                if not re.match(r'^\d+\.?$', position_text):
                    continue
                
                # Get name and profile link from second cell
                name_cell = cells[1]
                name = name_cell.get_text().strip()
                profile_link = None
                
                name_link = name_cell.find('a')
                if name_link and 'stat.php' in str(name_link.get('href', '')):
                    profile_link = name_link.get('href')
                
                # Get time from third cell
                time_cell = cells[2]
                time_2024 = time_cell.get_text().strip()
                
                # Get category from fourth cell (if exists)
                category_text = ""
                full_class = ""
                if len(cells) > 3:
                    full_class = cells[3].get_text().strip()
                    category_text = full_class.lower()
                
                # Determine category based on category text
                current_category = None
                if 'kvinner' in category_text:
                    current_category = "Dame"
                elif 'pluss 90kg' in category_text or 'pluss90kg' in category_text:
                    current_category = "Pluss"
                elif 'menn' in category_text or 'herrer' in category_text:
                    current_category = "Mann"
                else:
                    # Default to Mann if no clear category
                    current_category = "Mann"
                
                if name and len(name) > 1:  # Valid name
                    participant = {
                        "Navn": name,
                        "Tid": self.parse_time(time_2024) or time_2024,
                        "Klasse": full_class,
                        "ProfileLink": profile_link,
                        "Deltagelser": None,
                        "BesteTidligere": None,
                        "BesteÅr": None,
                        "NyBestetid": None,
                        "Differanse": None
                    }
                    results[current_category].append(participant)
                    print(f"Added {name} to {current_category} with time {time_2024}", file=__import__('sys').stderr)
                        
            except Exception as e:
                print(f"Error parsing row: {e}", file=__import__('sys').stderr)
                continue
        
        return results
    
    def fetch_participant_profile(self, participant: Dict) -> Dict:
        """Fetch and parse individual participant profile."""
        if not participant.get("ProfileLink"):
            return participant
        
        profile_url = participant["ProfileLink"]
        if not profile_url.startswith('http'):
            profile_url = self.base_url + "/" + profile_url.lstrip('/')
        
        soup = self.fetch_page(profile_url)
        if not soup:
            return participant
        
        try:
            # Look for participation count
            page_text = soup.get_text()
            
            # Try to find number of participations in table
            participation_found = False
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        first_cell_text = cells[0].get_text().strip().lower()
                        second_cell_text = cells[1].get_text().strip()
                        
                        if 'antall deltagelser' in first_cell_text or 'deltagelser' in first_cell_text:
                            # Extract number from second cell
                            match = re.search(r'(\d+)', second_cell_text)
                            if match:
                                participant["Deltagelser"] = int(match.group(1))
                                participation_found = True
                                break
                if participation_found:
                    break
            
            # Look for historical times in tables
            tables = soup.find_all('table')
            best_time = None
            best_year = None
            best_time_seconds = None
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        for i, cell in enumerate(cells):
                            cell_text = cell.get_text().strip()
                            
                            # Look for year (but not 2024)
                            year_match = re.search(r'(20\d{2})', cell_text)
                            if year_match and year_match.group(1) != '2024':
                                year = int(year_match.group(1))
                                
                                # Look for time in adjacent cells
                                for j in range(max(0, i-2), min(len(cells), i+3)):
                                    if j != i:
                                        time_text = cells[j].get_text().strip()
                                        time_match = re.search(r'\d+[.:]\d+[.:]\d+|\d+[.:]\d+', time_text)
                                        if time_match:
                                            parsed_time = self.parse_time(time_match.group())
                                            if parsed_time:
                                                time_seconds = self.time_to_seconds(parsed_time)
                                                # Find the FASTEST (lowest) time, not the most recent year
                                                if time_seconds and (best_time_seconds is None or time_seconds < best_time_seconds):
                                                    best_time = parsed_time
                                                    best_year = year
                                                    best_time_seconds = time_seconds
            
            participant["BesteTidligere"] = best_time
            participant["BesteÅr"] = best_year
            
            # Determine if 2024 time is a new best time
            participant["NyBestetid"] = self.is_new_best_time(
                participant.get("Tid"), best_time, best_year
            )
            
            # Calculate time difference (current - best previous)
            participant["Differanse"] = self.calculate_time_difference(
                participant.get("Tid"), best_time
            )
            
        except Exception as e:
            print(f"Error parsing profile for {participant['Navn']}: {e}")
        
        # Remove ProfileLink from final output
        participant.pop("ProfileLink", None)
        return participant
    
    def is_new_best_time(self, current_time: Optional[str], best_previous: Optional[str], best_year: Optional[int]) -> bool:
        """Determine if current time is a new personal best."""
        if not current_time:
            return False
        
        # If no previous best time, current time is automatically new best
        if not best_previous or best_year is None:
            return True
        
        # If best year is 2024 or later, it means the "best previous" is actually from current year or future
        if best_year >= 2024:
            return False
        
        try:
            # Convert times to seconds for comparison
            current_seconds = self.time_to_seconds(current_time)
            previous_seconds = self.time_to_seconds(best_previous)
            
            if current_seconds is None or previous_seconds is None:
                return False
            
            # Current time is better if it's LESS (faster) than previous best
            return current_seconds < previous_seconds
        except:
            return False
    
    def time_to_seconds(self, time_str: str) -> Optional[int]:
        """Convert time string to seconds for comparison."""
        if not time_str:
            return None
        
        try:
            # Handle different time formats
            parts = re.split(r'[.:]', time_str.strip())
            if len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            elif len(parts) == 3:  # HH:MM:SS or MM:SS:MS
                if int(parts[0]) > 59:  # Probably MM:SS:MS format
                    minutes, seconds, ms = map(int, parts)
                    return minutes * 60 + seconds
                else:  # HH:MM:SS format
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds
            return None
        except:
            return None
    
    def calculate_time_difference(self, current_time: Optional[str], best_previous: Optional[str]) -> Optional[str]:
        """Calculate the difference between current time and best previous time."""
        if not current_time or not best_previous:
            return None
        
        try:
            current_seconds = self.time_to_seconds(current_time)
            previous_seconds = self.time_to_seconds(best_previous)
            
            if current_seconds is None or previous_seconds is None:
                return None
            
            # Calculate difference (positive means slower, negative means faster)
            diff_seconds = current_seconds - previous_seconds
            
            # Convert back to time format
            if diff_seconds == 0:
                return "0:00"
            
            abs_diff = abs(diff_seconds)
            minutes = abs_diff // 60
            seconds = abs_diff % 60
            
            sign = "-" if diff_seconds < 0 else "+"
            return f"{sign}{minutes}:{seconds:02d}"
        except:
            return None


def main():
    """Main function to scrape and output results."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Scrape Stoltzen race results')
    parser.add_argument('url', help='URL to the results page to scrape')
    parser.add_argument('--timeout', type=int, default=10, help='Request timeout in seconds')
    
    args = parser.parse_args()
    
    scraper = StoltzenScraper()
    
    # Fetch the main results page
    url = args.url
    print(f"Fetching results from: {url}", file=sys.stderr)
    
    soup = scraper.fetch_page(url)
    if not soup:
        print("Failed to fetch the main page")
        return
    
    # Parse the results table
    results = scraper.parse_results_table(soup)
    
    # Count total participants
    total_participants = sum(len(category) for category in results.values())
    print(f"Found {total_participants} participants", file=__import__('sys').stderr)
    
    # Fetch profile data concurrently
    def fetch_profile_wrapper(participant):
        return scraper.fetch_participant_profile(participant)
    
    all_participants = []
    for category, participants in results.items():
        for participant in participants:
            all_participants.append((category, participant))
    
    print("Fetching participant profiles...", file=__import__('sys').stderr)
    
    # Use ThreadPoolExecutor for concurrent requests
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_participant = {}
        
        for category, participant in all_participants:
            future = executor.submit(fetch_profile_wrapper, participant)
            future_to_participant[future] = (category, participant)
        
        processed_results = {"Mann": [], "Dame": [], "Pluss": []}
        
        for future in as_completed(future_to_participant):
            category, original_participant = future_to_participant[future]
            try:
                updated_participant = future.result()
                processed_results[category].append(updated_participant)
            except Exception as e:
                print(f"Error processing {original_participant['Navn']}: {e}", file=__import__('sys').stderr)
                # Add original participant without profile data
                original_participant.pop("ProfileLink", None)
                processed_results[category].append(original_participant)
    
    # Sort results by best time within each category
    def get_sort_key(participant):
        # Use current time for sorting, convert to seconds for proper comparison
        current_time = participant.get("Tid")
        if current_time:
            time_seconds = scraper.time_to_seconds(current_time)
            return time_seconds if time_seconds is not None else float('inf')
        return float('inf')
    
    for category in processed_results:
        processed_results[category].sort(key=get_sort_key)
    
    # Output JSON with proper encoding
    json_output = json.dumps(processed_results, indent=2, ensure_ascii=False)
    print(json_output.encode('utf-8').decode('utf-8'))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScraping interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)