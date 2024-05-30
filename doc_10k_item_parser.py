import os
import pathlib
from dataclasses import dataclass
import re

import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm
ITEMS_10K = ["ITEM 1", "ITEM 1A", "ITEM 1B", "ITEM 2", "ITEM 3", "ITEM 4", "ITEM 5", "ITEM 6",
        "ITEM 7", "ITEM 7A", "ITEM 8", "ITEM 9", "ITEM 9A", "ITEM 9B", "ITEM 10",
        "ITEM 11", "ITEM 12", "ITEM 13", "ITEM 14", "ITEM 15"]

@dataclass
class Entry:
    company: str
    year: int
    item: str
    text: str

def find_10k_doc(soup: BeautifulSoup) -> str:
    content = soup.findAll("document")

    for doc in content:
        type_soup = doc.find("type")
        type_children = type_soup.contents
        type_str = type_children[0].strip()
        if type_str == "10-K":
            string_10k = type_children[1]

    return string_10k

def parse_report(path: pathlib.Path) -> list[Entry]:
    company_name = str(path).split("/")[1]
    year_two_digit = str(path).split("/")[3].split("-")[1]
    year = "20" + year_two_digit if int(year_two_digit) < 30 else "19" + year_two_digit

    
    if company_name == "INTC" and year == '2020':
        return []
    
    soup: BeautifulSoup = None
    with open(path, "r") as f:
        raw_text = f.read()
        soup = BeautifulSoup(raw_text, 'lxml')
    if soup is None:
        print(f"unable to parse...'{path}'")
        return
    
    string_10k = find_10k_doc(soup)

    item_to_index = {}
    last_added = None
    for i, item in enumerate(ITEMS_10K):
        first, second = item.split(" ")
        
        text_regex = f"{first}(\\s|&nbsp;|\\n)*{second}"
        opts = list(re.finditer(f"{text_regex}\\.", string_10k.text))
        if len(opts) < 1:
            first = first[0] + first[1:].lower()
            text_regex = f"{first}(\\s|&nbsp;|\\n)*{second}"
            opts = list(re.finditer(f"{text_regex}\\.", string_10k.text))

        if len(opts) > 0:
            m = opts[-1]
            
            item_to_index[item] = (m.end(), len(string_10k.text))
            if i > 0:
                start, _ = item_to_index[last_added]
                item_to_index[last_added] = start, m.start()
            last_added = item

    # print(string_10k.text[item_to_index["ITEM 1"][0] - 10:item_to_index["ITEM 1"][1]])

    entries = []
    for item in item_to_index:
        start, end = item_to_index[item]
        text = string_10k.text[start:end].strip()
        
        entries.append(
            Entry(
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


def parse_reports(report_paths: list[pathlib.Path]) -> pd.DataFrame:
    columns = ["Company", "Year", "Item", "Text"]
    dictionary = {k: [] for k in columns}
    
    for path in tqdm(report_paths):
        items: list[Entry] = parse_report(path)
        for item in items:
            dictionary["Company"].append(item.company)
            dictionary["Year"].append(item.year)
            dictionary["Item"].append(item.item)
            dictionary["Text"].append(item.text)
        
        
    df = pd.DataFrame(dictionary)
    return df



if __name__ == "__main__":
    ticker = "KO"
    report_paths: list[str] = []
    for root, dirs, files in os.walk(f"sec-edgar-filings/{ticker}/"):
        for name in files:
            if name.endswith(".txt"):
                report_paths.append(os.path.join(root, name))
    # print(report_paths[46])
    # entries = parse_report("sec-edgar-filings/AAPL/10-K/0001047469-04-035975/full-submission.txt")
    # print(entries)
    # for e in entries:
    #     print(e.item, len(e.text))
    df = parse_reports(report_paths)
    df.to_json(f"sec_items_{ticker}.json", orient="records")
        