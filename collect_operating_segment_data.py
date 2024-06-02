import re
import os
from pathlib import Path
import logging

import pandas as pd

from llm import identify_operating_segments, identify_revenue_by_operating_segment

# regex patterns
OPERATING_SEGMENTS_REGEX = r"(?i)(operating|business)\s+segment"
BY_OPERATING_SEGMENT_REGEX = r"(?i)by\s+(operating|business)\s+segment"
def generate_operating_segment_specific_regex(operating_segment_name: str):
    words = operating_segment_name.split(" ")
    return r"(?i)" + r"\s+".join(words)

DELTA = 100 # characters around the regex find

def load_item_7_dataset(sec_items_dir: Path) -> pd.DataFrame:
    dfs = []
    for root, _, files in os.walk(sec_items_dir):
        for name in files:
            json_path: Path = Path(os.path.join(root, name))
            df_ticker: pd.DataFrame = pd.read_json(json_path)
            df_7 = df_ticker[(df_ticker.Item == "ITEM 7") | (df_ticker.Item == "ITEM 7A") | (df_ticker.Item == "Item 7B")]
            dfs.append(df_7)

    df = pd.concat(dfs, axis=0)
    return df

def load_item_1_dataset(sec_items_dir: Path) -> pd.DataFrame:
    dfs = []
    for root, _, files in os.walk(sec_items_dir):
        for name in files:
            json_path: Path = Path(os.path.join(root, name))
            df_ticker: pd.DataFrame = pd.read_json(json_path)
            df_1 = df_ticker[(df_ticker.Item == "ITEM 1") | (df_ticker.Item == "ITEM 1A") | (df_ticker.Item == "Item 1B")]
            dfs.append(df_1)

    df = pd.concat(dfs, axis=0)
    return df

def collect_item_text(df_10k: pd.DataFrame) -> str:
    total_text = ""
    for i in range(len(df_10k)):
        total_text += df_10k.iloc[i].Text
    return total_text

def collect_operating_segment_snippets(item_7_total_text: str) -> list[str]:
    matches = list(re.finditer(OPERATING_SEGMENTS_REGEX, item_7_total_text))
    snippets = [item_7_total_text[m.start() - DELTA: m.end() + DELTA] for m in matches]
    return snippets

def list_operating_segments_from_llama_response(llama_response: str) -> list[str]:
    report_op_segs = []
    for line in llama_response.split("\n\n"):
        if line.count(",") > 1:
            for oper_seg in line.split(","):
                if "and " == oper_seg.strip()[:4]:
                    oper_seg = oper_seg.split("and ")[1]
                if len(oper_seg.split("(")) > 1:
                    oper_seg = oper_seg.split("(")[1]
                oper_seg = oper_seg.split(")")[0]
                oper_seg = oper_seg.strip()
                oper_seg = re.sub(r'[^(a-zA-Z|\&) ]', '', oper_seg) # remove non alphabetical
                report_op_segs.append(oper_seg)
    return report_op_segs

def extract_operating_segments(df: pd.DataFrame) -> pd.DataFrame:
    operating_segment_dict = {
        "Company": [],
        "Year": [],
        "Operating Segment": []
    }

    unique_companies = df.Company.unique()
    
    for company in unique_companies:
        df_company = df[df.Company == company]
        unique_years = df_company.Year.unique()

        for year in unique_years:
            df_10k: pd.DataFrame = df_company[df_company.Year == year]
            total_text: str = collect_item_text(df_10k)
            
            operating_segment_snippets: list[str] = collect_operating_segment_snippets(total_text)
            context: str = "\n\n".join(operating_segment_snippets)

            logging.info(f"Finding segments  for\t{company, year}\t{len(operating_segment_snippets)}\t{len(" ".join(operating_segment_snippets))}")
            llama_response: str = identify_operating_segments(context, company, year)
            operating_segments: list[str] = list_operating_segments_from_llama_response(llama_response)
            
            logging.info("Segments found: \t" + str(operating_segments))
            for operating_segment in list(set(operating_segments)):
                operating_segment_dict["Company"].append(company)
                operating_segment_dict["Year"].append(year)
                operating_segment_dict["Operating Segment"].append(operating_segment)

    return pd.DataFrame(operating_segment_dict)

def format_monetary_from_llama_response(llama_response: str) -> float:
    value = None
    # Regex pattern for $2,345 million, $2345, and $2,451,321 billion
    pattern = r"\$\d+(,\d{3})*(?:\.\d+)?(?:\s?(million|billion))?"
    matches = list(re.finditer(pattern, llama_response))
    if len(matches) == 0:
        return None
    line = llama_response[matches[0].start():matches[0].end()]

    # for line in llama_response.split("\n\n"):
    # if "$" not in line:
    #     continue
    if line.count(",") == 1:
        line += " million"
    
    line = line.replace("$", "").replace(",", "")

    if "million" in line:
        value = re.sub(r'[^(0-9) ]', '', line) 
        value = float(value) * 1e6
    elif "billion" in line:
        value = re.sub(r'[^(0-9) ]', '', line) 
        value = float(value) * 1e9
        # number = line.split(" ")[0]
        # if len(number.split(".")[0]) > 2: 
        #     value = float(number) * 1e6 # probably is actually a million
        # else:
        #     value = float(number) * 1e9
    else:
        if line.count(",") < 1:
            value = re.sub(r'[^(0-9) ]', '', line) 
            value = float(value) * 1e6
        else:
            value = re.sub(r'[^(0-9) ]', '', line) 
            value = float(value)
    
    return value

def hydrate_operating_segments_with_revenue(df_10k_total: pd.DataFrame, df_operating_segments: pd.DataFrame) -> pd.DataFrame:
    revenue = []
    unique_companies = df_operating_segments.Company.unique()
    
    for company in unique_companies:
        df_company = df_operating_segments[df_operating_segments.Company == company]
        unique_years = df_company.Year.unique()

        for year in unique_years:
            df_os_specific: pd.DataFrame = df_company[df_company.Year == year]
            df_10k = df_10k_total[(df_10k_total.Year == year) & (df_10k_total.Company == company)]
            item_7_total_text: str = collect_item_text(df_10k)

            by_operating_segment_matches = list(re.finditer(BY_OPERATING_SEGMENT_REGEX, item_7_total_text))
            by_operating_segment_snippets = [item_7_total_text[m.start() - DELTA: m.end() + DELTA] for m in by_operating_segment_matches]
            for operating_segment in df_os_specific["Operating Segment"].unique():
                operating_segment_spec_regex = generate_operating_segment_specific_regex(str(operating_segment))
                operating_segment_spec_matches: list[str] = list(re.finditer(operating_segment_spec_regex, item_7_total_text))
                operating_segment_specific_snippets: list[str] = [item_7_total_text[m.start() - DELTA: m.end() + DELTA] for m in operating_segment_spec_matches] + by_operating_segment_snippets

                context: str = "\n\n".join(operating_segment_specific_snippets[:150])
                logging.info(f"Segments found for\t{company, year, operating_segment}\tCount: {len(operating_segment_specific_snippets)}\tTotal Token Estimate: {len(context)}")
                llama_response: str = identify_revenue_by_operating_segment(context, company, year, operating_segment)
                logging.info("Llama responded with: " + str(llama_response))
                revenue_value = format_monetary_from_llama_response(llama_response)
                revenue.append(revenue_value)

        print(f"{len(revenue)} / {len(df_operating_segments)}")
        df_copy = df_operating_segments.copy().iloc[:len(revenue)]
        df_copy["Revenue"] = revenue
        df_copy.to_csv("data/operating_segments/os_temp.csv")

    df_operating_segments["Revenue"] = revenue
    return df_operating_segments

if __name__ == "__main__":
    logging.basicConfig(filename="find_op_segs.log", encoding='utf-8', level=logging.DEBUG)
    df_1: pd.DataFrame = load_item_1_dataset(Path("data/sec_items/"))
    # df_operating_segments = extract_operating_segments(df_1)
    df_7: pd.DataFrame = load_item_7_dataset(Path("data/sec_items/"))
    # df_operating_segments.to_csv("data/operating_segments/operating_segments_basic.csv")
    df_operating_segments = pd.read_csv("data/operating_segments/operating_segments_basic.csv")
    df_operating_segments_with_revenue = hydrate_operating_segments_with_revenue(df_7, df_operating_segments)
    df_operating_segments_with_revenue.to_csv("data/operating_segments/operating_segments_with_operating_income.csv")
