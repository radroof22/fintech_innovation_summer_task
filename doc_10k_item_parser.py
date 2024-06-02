import os
import pathlib
from dataclasses import dataclass
import re
import argparse

import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm

ITEMS_10K = ["ITEM 1", "ITEM 1A", "ITEM 1B", "ITEM 2", "ITEM 3", "ITEM 4", "ITEM 5", "ITEM 6",
        "ITEM 7", "ITEM 7A", "ITEM 8", "ITEM 9", "ITEM 9A", "ITEM 9B", "ITEM 10",
        "ITEM 11", "ITEM 12", "ITEM 13", "ITEM 14", "ITEM 15"]

@dataclass
class Item:
    company: str
    year: int
    name: str
    text: str

def find_10k_doc(soup: BeautifulSoup) -> str:
    """
    Iterate through report xml and to find <DOCUMENT> tag with the relevant Items

    Args:
    - soup: BeautifulSouped text from the report

    Returns:
    - text of the document containing relevant 10-K report Items
    """
    content = soup.findAll("document")

    for doc in content:
        type_soup = doc.find("type")
        type_children = type_soup.contents
        type_str = type_children[0].strip()
        if type_str == "10-K":
            string_10k = type_children[1]
    return string_10k

def parse_report(path: pathlib.Path) -> list[Item]:
    """
    Given the path of a report, read the report and extract the text for each of the items and their corresponding text

    Args:
    - path: Path
        The path to the report
    
    Returns:
    - list of text for the Items in the 10-k report
    """
    company_name = str(path).split("/")[1]
    year_two_digit = str(path).split("/")[3].split("-")[1]
    year = "20" + year_two_digit if int(year_two_digit) < 30 else "19" + year_two_digit
    
    # NOTE:  Beatiful Soup unable to parse the INTC 2020 due to size
    if year == "2020" and company_name == "INTC":
        return []
    
    soup: BeautifulSoup = None
    with open(path, "r") as f:
        raw_text = f.read()
        soup = BeautifulSoup(raw_text, 'lxml')
    if soup is None:
        print(f"unable to parse...'{path}'")
        return
    
    string_10k = find_10k_doc(soup)
    tags_in_doc = len(string_10k.findAll())
    if tags_in_doc > 500:
        item_to_index = handle_html_format(string_10k.text)
    else:
        item_to_index = handle_nonhtml_format(string_10k.text)

    entries = []
    for item in item_to_index:
        start, end = item_to_index[item]
        text = string_10k.text[start:end].strip()
        
        entries.append(
            Item(
                company_name,
                year,
                item,
                text
            )
        )

    for e in entries:
        if len(e.text) < 1:
            print(f"Missing Text for {e.company} - {e.year} - {e.item}")

    return entries

def handle_html_format(string_10k_text: str):
    """
    Extracting indices for each of the 10-K report items for the specific report.
    The html is for newer reports that use the standardized xml/html formatting.

    Args:
    - string_10k_text: str
        Raw text of the document containing the document elements from the 10k report.
    
    Retuns:
    - dictionary mapping "ITEM #" to start_index and end_index of section to the report
    """
    item_to_index = {}
    last_added = None
    for i, item in enumerate(ITEMS_10K):
        first, second = item.split(" ")
        
        text_regex = f"{first}(\\s|&nbsp;|\\n)*{second}\\."
        opts = list(re.finditer(text_regex, string_10k_text))
        if len(opts) < 1:
            first_lowercase = first[0] + first[1:].lower()
            text_regex = f"{first_lowercase}(\\s|&nbsp;|\\n)*{second}\\."
            opts = list(re.finditer(text_regex, string_10k_text))

        last_start, _ = item_to_index[last_added] if last_added is not None else (0, None)
        if len(opts) > 0:
            m = opts[0]
            for o in opts:
                if o.start() - last_start > 100:
                    m = o
                    break
            item_to_index[item] = (m.end(), len(string_10k_text))
            if i > 0:
                start, _ = item_to_index[last_added]
                item_to_index[last_added] = start, m.start()
            last_added = item
    return item_to_index

def handle_nonhtml_format(string_10k_text: str) -> dict[str, tuple[int, int]]:
    """
    Extracting indices for each of the 10-K report items for the specific report.
    The non-html is for older reports that don't use the standardized xml/html formatting.

    Args:
    - string_10k_text: str
        Raw text of the document containing the document elements from the 10k report.
    
    Retuns:
    - dictionary mapping "ITEM #" to start_index and end_index of section to the report
    """
    item_to_index = {}
    last_added = None

    for i, item in enumerate(ITEMS_10K):
        first, second = item.split(" ")
        
        text_regex = f"{first}(\\s|&nbsp;|\\n)*{second}\\."
        opts = list(re.finditer(f"{text_regex}", string_10k_text))
        if len(opts) < 1:
            first_lowercase = first[0] + first[1:].lower()
            text_regex = f"{first_lowercase}(\\s|&nbsp;|\\n)*{second}\\."
            opts = list(re.finditer(f"{text_regex}", string_10k_text))
        if len(opts) > 0:
            m = opts[0]
            item_to_index[item] = (m.end(), len(string_10k_text))
            if i > 0:
                start, _ = item_to_index[last_added]
                item_to_index[last_added] = start, m.start()
            last_added = item

    return item_to_index

def parse_reports(report_paths: list[pathlib.Path]) -> pd.DataFrame:
    """
    Iterate through all of the report paths, read the reports, extract the 
    item document, and create list of items with the correct text in the document

    Args:
    - report_paths: list[Path]
        List of paths to reports for tickers to extract item information from

    Returns:
    - pd.DataFrame of 10K reports organized with columns Company, Year, Item, and Text
    """
    columns = ["Company", "Year", "Item", "Text"]
    dictionary = {k: [] for k in columns}
    
    for path in tqdm(report_paths):
        items: list[Item] = parse_report(path)
        for item in items:
            dictionary["Company"].append(item.company)
            dictionary["Year"].append(item.year)
            dictionary["Item"].append(item.name)
            dictionary["Text"].append(item.text)
        
    df = pd.DataFrame(dictionary)
    return df



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Program to convert sec-edgar-filings for ticker")
    parser.add_argument("ticker", help="Ticker for stock symbol")

    args = parser.parse_args()
    ticker = args.ticker

    report_paths: list[str] = []
    for root, dirs, files in os.walk(f"sec-edgar-filings/{ticker}/"):
        for name in files:
            if name.endswith(".txt"):
                report_paths.append(os.path.join(root, name))

    df = parse_reports(report_paths)
    df.to_json(f"sec_items_{ticker}.json", orient="records")
        