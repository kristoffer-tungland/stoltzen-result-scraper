#!/usr/bin/env python3
"""
Stoltzen Stat URL Scraper

This script fetches race results from a list of stoltzen.no stat.php URLs,
parses participant data, and outputs structured CSV with participant profiles.
"""

import re
import csv
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
import sys
import argparse
import os


class StoltzenStatScraper:
    def __init__(self):
        self.base_url = "http://stoltzen.no"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'nb-NO,nb;q=0.9,no;q=0.8,nn;q=0.7,en;q=0.6',
            'Accept-Charset': 'utf-8,iso-8859-1;q=0.7'
        })
    
    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a web page."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Handle Norwegian character encoding properly
            # Force encoding detection for better Norwegian character handling
            raw_content = response.content
            
            # Test different encodings to find the best one
            for encoding in ['utf-8', 'iso-8859-1', 'windows-1252']:
                try:
                    decoded_content = raw_content.decode(encoding)
                    # Check for Norwegian characters or words
                    if ('ø' in decoded_content or 'æ' in decoded_content or 'å' in decoded_content or 
                        'Thorbjørn' in decoded_content or 'statistikk' in decoded_content.lower()):
                        response.encoding = encoding
                        break
                    # Check if no mojibake patterns exist
                    elif ('Ã¦' not in decoded_content and 'Ã¸' not in decoded_content and 
                          'Ã¥' not in decoded_content):
                        response.encoding = encoding
                        break
                except UnicodeDecodeError:
                    continue
            else:
                # Fallback to iso-8859-1
                response.encoding = 'iso-8859-1'
            
            return BeautifulSoup(response.text, 'html.parser')
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}", file=sys.stderr)
            return None
    
    def parse_time(self, time_str: str) -> Optional[str]:
        """Parse and normalize time string."""
        if not time_str:
            return None
        
        # Clean up the time string
        time_str = time_str.strip()
        
        # Match time patterns like "1:23:45" or "23:45" or "1.23.45" or "07.54"
        time_pattern = r'(\d{1,2})[.:](\d{2})[.:](\d{2})'
        match = re.search(time_pattern, time_str)
        
        if match:
            first, second, third = match.groups()
            first_num = int(first)
            
            # For race times, determine if it's HH:MM:SS or MM:SS:Hundredths
            if first_num <= 60 and int(third) < 100:
                # Likely MM:SS:Hundredths format (e.g., "07.54.23" = 7:54)
                return f"{first}:{second}"
            elif first_num > 23:
                # Definitely minutes:seconds:hundredths
                return f"{first}:{second}"
            else:
                # Could be HH:MM:SS format
                return f"{first}:{second}:{third}" if first_num > 0 else f"{second}:{third}"
        
        # Try minutes:seconds pattern (e.g., "07.54" or "7:54")
        time_pattern = r'(\d{1,3})[.:](\d{2})'
        match = re.search(time_pattern, time_str)
        if match:
            minutes, seconds = match.groups()
            return f"{minutes}:{seconds}"
        
        return time_str
    
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
            elif len(parts) == 3:  # Could be HH:MM:SS or MM:SS:Hundredths
                first, second, third = map(int, parts)
                
                # For race times, if first number is reasonable for minutes (0-60), 
                # and third number is < 100, treat as MM:SS:Hundredths
                if first <= 60 and third < 100:
                    # MM:SS:Hundredths - ignore hundredths for comparison
                    return first * 60 + second
                else:
                    # HH:MM:SS format
                    return first * 3600 + second * 60 + third
            return None
        except:
            return None
    
    def fix_norwegian_encoding(self, text: str) -> str:
        """Fix common Norwegian character encoding issues."""
        if not text:
            return text
        
        # Common encoding fixes for Norwegian characters
        replacements = {
            'Ã¦': 'æ',     # æ
            'Ã¸': 'ø',     # ø  
            'Ã¥': 'å',     # å
            'Ã†': 'Æ',     # Æ
            'Ã˜': 'Ø',     # Ø
            'Ã…': 'Å',     # Å
            'Ã°': 'ð',     # ð
            'Ã¶': 'ö',     # ö
            'Ã¤': 'ä',     # ä
            'ThorbjoÌrn': 'Thorbjørn',
            'Thorbj�rn': 'Thorbjørn',
        }
        
        # Apply replacements
        for bad, good in replacements.items():
            text = text.replace(bad, good)
        
        # Try to decode if it looks like it's been double-encoded
        try:
            # Check if text contains UTF-8 byte sequences incorrectly decoded as Latin-1
            if any(ord(c) > 127 for c in text):
                # Try to re-encode as Latin-1 and decode as UTF-8
                fixed = text.encode('latin-1').decode('utf-8')
                # Only use if it seems better (contains proper Norwegian chars)
                if any(c in fixed for c in 'æøåÆØÅ'):
                    text = fixed
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        
        return text
    
    def determine_group_from_class(self, class_text: str) -> str:
        """Determine participant group based on class text."""
        if not class_text:
            return "Mann"  # Default
        
        class_lower = class_text.lower()
        
        if 'kvinner' in class_lower or 'kvinne' in class_lower or 'dame' in class_lower:
            return "Dame"
        elif 'pluss 90kg' in class_lower or 'pluss90kg' in class_lower or 'pluss' in class_lower:
            return "Pluss"
        elif ('menn' in class_lower or 'mann' in class_lower or 'herrer' in class_lower or 
              'herre' in class_lower):
            return "Mann"
        else:
            return "Mann"  # Default
    
    def parse_participant_profile(self, url: str) -> Optional[Dict]:
        """Parse a single participant profile from stat.php URL."""
        soup = self.fetch_page(url)
        if not soup:
            return None
        
        try:
            participant = {
                "Navn": None,
                "Tid": None,
                "Klasse": None,
                "Deltagelser": None,
                "BesteTidligere": None,
                "BesteÅr": None,
                "NyBestetid": None,
                "Differanse": None,
                "Gruppe": None
            }
            
            # Extract participant name from page title or h1/h2 tags
            title = soup.find('title')
            if title:
                title_text = title.get_text().strip()
                # Extract name from title like "Statistikk for Kristoffer Tungland"
                name_match = re.search(r'for\s+(.+?)(?:\s*-|\s*$)', title_text)
                if name_match:
                    name = name_match.group(1).strip()
                    # Remove common prefixes/suffixes that shouldn't be part of name
                    name = re.sub(r'^(StoltzeStatistikk\s+for\s+|Statistikk\s+for\s+)', '', name, flags=re.IGNORECASE)
                    participant["Navn"] = self.fix_norwegian_encoding(name)
            
            # Also try to find name in h1/h2 tags
            if not participant["Navn"] or len(participant["Navn"]) < 3:
                for header in soup.find_all(['h1', 'h2', 'h3']):
                    header_text = header.get_text().strip()
                    # Clean up header text
                    header_text = re.sub(r'^(StoltzeStatistikk\s+for\s+|Statistikk\s+for\s+)', '', header_text, flags=re.IGNORECASE)
                    if len(header_text) > 3 and ' ' in header_text and not header_text.lower().startswith('statistikk'):
                        participant["Navn"] = self.fix_norwegian_encoding(header_text)
                        break
            
            # If still no good name, try to find it in table headers or cells
            if not participant["Navn"] or len(participant["Navn"]) < 3:
                # Look for name patterns in tables
                for table in soup.find_all('table'):
                    for row in table.find_all('tr'):
                        for cell in row.find_all(['td', 'th']):
                            cell_text = cell.get_text().strip()
                            # Look for name-like patterns (first name + last name)
                            if re.match(r'^[A-ZÆØÅ][a-zæøå]+\s+[A-ZÆØÅ][a-zæøå]+', cell_text):
                                participant["Navn"] = self.fix_norwegian_encoding(cell_text)
                                break
                        if participant["Navn"] and len(participant["Navn"]) > 3:
                            break
                    if participant["Navn"] and len(participant["Navn"]) > 3:
                        break
            
            # Look for participant data in tables
            current_year_time = None
            current_year_class = None
            participation_count = 0
            best_time = None
            best_year = None
            best_time_seconds = None
            
            tables = soup.find_all('table')
            
            # First, look for specific data using ID attributes (more reliable)
            personal_best_td = soup.find('td', id='personal_best')
            if personal_best_td:
                text = personal_best_td.get_text().strip()
                # Extract time and year from "07.54 (2016)" format
                match = re.search(r'(\d+)\.(\d+)\s*\((\d{4})\)', text)
                if match:
                    minutes, seconds, year = match.groups()
                    best_time = f"{minutes}:{seconds}"
                    best_year = int(year)
                    best_time_seconds = int(minutes) * 60 + int(seconds)
            
            participations_td = soup.find('td', id='participations')
            if participations_td:
                text = participations_td.get_text().strip()
                match = re.search(r'(\d+)', text)
                if match:
                    participation_count = int(match.group(1))
            
            last_time_td = soup.find('td', id='last_time')
            if last_time_td:
                text = last_time_td.get_text().strip()
                # Extract time and year from "08.11 (2024)" format
                match = re.search(r'(\d+)\.(\d+)\s*\((\d{4})\)', text)
                if match:
                    minutes, seconds, year = match.groups()
                    if year == '2024':  # Current year
                        current_year_time = f"{minutes}:{seconds}"
            
            # Look for class information in the details table
            # The class is typically found in a table with structure like:
            # <td><b>Klasse</b></td><td>Herrer</td>
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        first_cell_text = cells[0].get_text().strip().lower()
                        if 'klasse' in first_cell_text:
                            class_text = cells[1].get_text().strip()
                            if class_text and len(class_text) > 1:
                                current_year_class = self.fix_norwegian_encoding(class_text)
                                break
                if current_year_class:
                    break
            
            # Fallback: look for data in table structure
            for table in tables:
                rows = table.find_all('tr')
                
                # Look for participation count (if not found via ID)
                if participation_count == 0:
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            first_cell_text = cells[0].get_text().strip().lower()
                            second_cell_text = cells[1].get_text().strip()
                            
                            if 'antall deltagelser' in first_cell_text or 'deltagelser' in first_cell_text:
                                match = re.search(r'(\d+)', second_cell_text)
                                if match:
                                    participation_count = int(match.group(1))
                
                # Look for yearly results (only if not found via ID)
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        for i, cell in enumerate(cells):
                            cell_text = cell.get_text().strip()
                            
                            # Look for 2024 (current year) - only if not found via ID
                            if '2024' in cell_text and not current_year_time:
                                # Look for time in adjacent cells
                                for j in range(max(0, i-2), min(len(cells), i+3)):
                                    if j != i:
                                        time_text = cells[j].get_text().strip()
                                        time_match = re.search(r'\d+[.:]\d+(?:[.:]\d+)?', time_text)
                                        if time_match:
                                            current_year_time = self.parse_time(time_match.group())
                                            
                                            # Look for class in nearby cells
                                            for k in range(max(0, i-2), min(len(cells), i+3)):
                                                if k != i and k != j:
                                                    class_text = cells[k].get_text().strip()
                                                    if any(word in class_text.lower() for word in ['kvinner', 'menn', 'pluss']):
                                                        current_year_class = self.fix_norwegian_encoding(class_text)
                                            break
                            
                            # Look for other years (not 2024) for best time - only if not found via ID
                            if not best_time:
                                year_match = re.search(r'(20\d{2})', cell_text)
                                if year_match and year_match.group(1) != '2024':
                                    year = int(year_match.group(1))
                                    
                                    # Look for time in adjacent cells
                                    for j in range(max(0, i-2), min(len(cells), i+3)):
                                        if j != i:
                                            time_text = cells[j].get_text().strip()
                                            time_match = re.search(r'\d+[.:]\d+(?:[.:]\d+)?', time_text)
                                            if time_match:
                                                parsed_time = self.parse_time(time_match.group())
                                                if parsed_time:
                                                    time_seconds = self.time_to_seconds(parsed_time)
                                                    # Find the FASTEST (lowest) time
                                                    if time_seconds and (best_time_seconds is None or time_seconds < best_time_seconds):
                                                        best_time = parsed_time
                                                        best_year = year
                                                        best_time_seconds = time_seconds
            
            # Set participant data
            participant["Tid"] = current_year_time
            participant["Klasse"] = current_year_class or ""
            participant["Deltagelser"] = participation_count if participation_count > 0 else None
            participant["BesteTidligere"] = best_time
            participant["BesteÅr"] = best_year
            participant["Gruppe"] = self.determine_group_from_class(current_year_class)
            
            # Determine if 2024 time is a new best time
            participant["NyBestetid"] = self.is_new_best_time(
                current_year_time, best_time, best_year
            )
            
            # Calculate time difference
            participant["Differanse"] = self.calculate_time_difference(
                current_year_time, best_time
            )
            
            # Only return participant if we have at least a name and current year time
            if participant["Navn"] and participant["Tid"]:
                return participant
            else:
                print(f"Incomplete data for URL {url}: Name={participant['Navn']}, Time={participant['Tid']}", file=sys.stderr)
                return None
                
        except Exception as e:
            print(f"Error parsing profile {url}: {e}", file=sys.stderr)
            return None
    
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
    
    def load_urls_from_file(self, file_path: str) -> List[str]:
        """Load URLs from a text file."""
        urls = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):  # Skip comments and empty lines
                        # Ensure it's a valid stat.php URL
                        if 'stat.php?id=' in line:
                            urls.append(line)
                        else:
                            print(f"Skipping invalid URL: {line}", file=sys.stderr)
        except Exception as e:
            print(f"Error reading URL file {file_path}: {e}", file=sys.stderr)
        
        return urls


def main():
    """Main function to scrape and output results."""
    parser = argparse.ArgumentParser(description='Scrape Stoltzen results from stat.php URLs')
    parser.add_argument('url_file', help='Text file containing stat.php URLs (one per line)')
    parser.add_argument('--timeout', type=int, default=10, help='Request timeout in seconds')
    parser.add_argument('--output', '-o', default='results.csv', help='Output CSV file path')
    
    args = parser.parse_args()
    
    scraper = StoltzenStatScraper()
    
    # Check if URL file exists
    if not os.path.exists(args.url_file):
        print(f"Error: URL file '{args.url_file}' not found", file=sys.stderr)
        return
    
    # Load URLs from file
    urls = scraper.load_urls_from_file(args.url_file)
    if not urls:
        print("No valid URLs found in file", file=sys.stderr)
        return
    
    print(f"Loaded {len(urls)} URLs from {args.url_file}", file=sys.stderr)
    print(f"Output will be saved to: {args.output}", file=sys.stderr)
    
    # Fetch profile data concurrently
    print("Fetching participant profiles...", file=sys.stderr)
    
    participants = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(scraper.parse_participant_profile, url): url for url in urls}
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                participant = future.result()
                if participant:
                    participants.append(participant)
                    print(f"Processed {participant['Navn']} ({participant['Gruppe']}) - {participant['Tid']}", file=sys.stderr)
                else:
                    print(f"Failed to process URL: {url}", file=sys.stderr)
            except Exception as e:
                print(f"Error processing {url}: {e}", file=sys.stderr)
    
    if not participants:
        print("No participants found", file=sys.stderr)
        return
    
    # Sort by group (Dame, Mann, Pluss) and then by time
    def get_sort_key(participant):
        # Group priority: Dame=1, Mann=2, Pluss=3
        group_priority = {'Dame': 1, 'Mann': 2, 'Pluss': 3}
        group_order = group_priority.get(participant.get('Gruppe'), 4)
        
        # Time sorting (convert to seconds for proper comparison)
        current_time = participant.get("Tid")
        time_seconds = float('inf')  # Default for invalid times
        if current_time:
            time_seconds = scraper.time_to_seconds(current_time)
            if time_seconds is None:
                time_seconds = float('inf')
        
        return (group_order, time_seconds)
    
    participants.sort(key=get_sort_key)
    
    # Output to CSV file
    try:
        with open(args.output, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Gruppe', 'Navn', 'Tid', 'Klasse', 'Deltagelser', 'BesteTidligere', 'BesteÅr', 'NyBestetid', 'Differanse']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write header
            writer.writeheader()
            
            # Write participant data
            for participant in participants:
                row_data = {key: participant.get(key) for key in fieldnames}
                writer.writerow(row_data)
            
            print(f"Results saved to {args.output}")
            print(f"Total participants: {len(participants)}")
            
            # Show summary by group
            group_counts = {}
            for participant in participants:
                group = participant.get('Gruppe')
                group_counts[group] = group_counts.get(group, 0) + 1
            
            print("\nGroup summary:")
            for group in ['Dame', 'Mann', 'Pluss']:
                count = group_counts.get(group, 0)
                if count > 0:
                    print(f"  {group}: {count} participants")
                    
    except Exception as e:
        print(f"Error writing CSV file: {e}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScraping interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)