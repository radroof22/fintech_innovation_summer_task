import re
import os
from pathlib import Path
import logging

import pandas as pd

from llm import identify_operating_segments, identify_metric_10k_by_operating_segment

# regex patterns
OPERATING_SEGMENTS_REGEX = r"(?i)(operating|business)\s+segment"
BY_OPERATING_SEGMENT_REGEX = r"(?i)by\s+(operating|business)\s+segment"
def generate_operating_segment_specific_regex(operating_segment_name: str):
    words = operating_segment_name.split(" ")
    return r"(?i)" + r"\s+".join(words)

DELTA = 200 # characters around the regex find
METRIC_10K_NAME = "Operating Income"

def load_items_dataset(sec_items_dir: Path, item_names: list[str]) -> pd.DataFrame:
    """

    Args:
    - sec_items_dir: Path
        Path to directory containing the parsed sec item reports for tickers
    - item_names: list[str]
        Name of 10-K report items to extract from parsed data

    Returns:
    - pd.DataFrame containing items text for the relevant items provided across all tickers
    """

    dfs = []
    for root, _, files in os.walk(sec_items_dir):
        for name in files:
            json_path: Path = Path(os.path.join(root, name))
            df_ticker: pd.DataFrame = pd.read_json(json_path)
            for item in item_names:
                df_spec_item = df_ticker[df_ticker.Item == item]
                dfs.append(df_spec_item)

    df = pd.concat(dfs, axis=0)
    return df

def collect_item_text(df_10k: pd.DataFrame) -> str:
    """
    For specific dataframe, collect all the text for items in it.

    Args:
    - df_10k: pd.DataFrame
        Dataframe containing subset of items from all tickers and items retrieved

    Returns:
    - string text of all of the times in the DataFrame
    """
    total_text = ""
    for i in range(len(df_10k)):
        total_text += df_10k.iloc[i].Text
    return total_text

def collect_operating_segment_snippets(text: str) -> list[str]:
    """
    Parse the text provided for mentions of "operating segments" or "business segments" and obtain DELTA
    sized window around text mentions.

    Args:
    - text: str

    Returns:
    - list[str] windowed mentions of the corresponding terms.
    """
    matches = list(re.finditer(OPERATING_SEGMENTS_REGEX, text))
    snippets = [text[m.start() - DELTA: m.end() + DELTA] for m in matches]
    return snippets

def parse_operating_segments_from_llama_response(llama_response: str) -> list[str]:
    """
    Parse operating segments from llama's response

    Args:
    - llama_response: str
        Llama's response to "identifying operating segments" prompt
    
    Returns:
    - list[str] containing names of the operating segments
    """
    report_op_segs = []
    for line in llama_response.split("\n\n"):
        if line.count(",") > 1: # correct line of response containing its proposed operating segments
            for oper_seg in line.split(","):
                # handle if llama uses and for last term
                if "and " == oper_seg.strip()[:4]:
                    oper_seg = oper_seg.split("and ")[1]
                
                # remove any paranthesized statements
                if len(oper_seg.split("(")) > 1:
                    oper_seg = oper_seg.split("(")[1]
                oper_seg = oper_seg.split(")")[0]

                oper_seg = oper_seg.strip()
                oper_seg = re.sub(r'[^(a-zA-Z|\&) ]', '', oper_seg) # remove non alphabetical
                report_op_segs.append(oper_seg)
    return report_op_segs

def extract_operating_segments(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse operating segments for each company and 10-K report year. For best results, input Item's 1, 1A, and 1B.
    Uses regex to identify mentions of operating segments in the 10-K reports as context for Llama.

    Args:
    - df: pd.DataFrame
        Contains items for all companies and years you want to parse

    Returns:
    - pd.Dataframe with columns Company, Year, and Operating Segment for each Operating Segment found by Llama during parsing.

    """
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
            operating_segments: list[str] = parse_operating_segments_from_llama_response(llama_response)
            
            logging.info("Segments found: \t" + str(operating_segments))
            for operating_segment in list(set(operating_segments)):
                operating_segment_dict["Company"].append(company)
                operating_segment_dict["Year"].append(year)
                operating_segment_dict["Operating Segment"].append(operating_segment)

    return pd.DataFrame(operating_segment_dict)

def format_monetary_from_llama_response(llama_response: str) -> float:
    """
    Extract dollar value of metric from llama's response to identifying the metric for the operating segment.

    Args:
    - llama_response: str
        Llama's raw response to trying to find the metric_10k in context for specific operating segment
    
    Returns:
    - float dollar value for metric
    """
    value = None
    # Regex pattern for $2,345 million, $2345, and $2,451,321 billion
    pattern = r"\$\d+(,\d{3})*(?:\.\d+)?(?:\s?(million|billion))?"
    matches = list(re.finditer(pattern, llama_response))
    if len(matches) == 0:
        return None
    line = llama_response[matches[-1].start():matches[-1].end()]

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

def hydrate_operating_segments_with_10k_metric(df_10k_total: pd.DataFrame, df_operating_segments: pd.DataFrame, metric_10k: str) -> pd.DataFrame:
    """
    Match operating segment with its correct numeric value for the metric_10k. Use Item 7, 7A, and 7B for best results.
    Parses and applies regex to the find mentions of the metric_10k and " by operating segments" to use as context for 
    identifying the correct matching values.

    Args:
    - df_10k_total: pd.DataFrame
        Dataframe containing text for the 10k reports to use when identifying values for the metric_10k
    - df_operating_segments: pd.DataFrame
        Dataframe of operating segments found by Llama for each of the 10-K reports.
    - metric_10k: str
        Metric to find the values of each operating segment in the 10-K reports. Ex - revenue/sales, operating income, ...

    Returns:
    - pd.DataFrame containing columns Company, Year, Operating Segment, Metric_10k
    """
    metric_10k_list = []
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
            for operating_segment in df_os_specific[metric_10k].unique():
                operating_segment_spec_regex = generate_operating_segment_specific_regex(str(operating_segment))
                operating_segment_spec_matches: list[str] = list(re.finditer(operating_segment_spec_regex, item_7_total_text))
                operating_segment_specific_snippets: list[str] = [item_7_total_text[m.start() - DELTA: m.end() + DELTA] for m in operating_segment_spec_matches] + by_operating_segment_snippets

                # NOTE: Used to avoid inputting to large of contexts
                context: str = "\n\n".join(operating_segment_specific_snippets[:100])
                logging.info(f"Segments found for\t{company, year, operating_segment}\tCount: {len(operating_segment_specific_snippets)}\tTotal Token Estimate: {len(context)}")
                llama_response: str = identify_metric_10k_by_operating_segment(context, metric_10k, company, year, operating_segment)
                metric_10k_value = format_monetary_from_llama_response(llama_response)
                logging.info(f"Llama responded with: \t{llama_response}\t{metric_10k_value}")
                metric_10k_list.append(metric_10k_value)

    df_operating_segments[METRIC_10K_NAME] = metric_10k_list
    return df_operating_segments

if __name__ == "__main__":
    logging.basicConfig(filename="find_op_segs.log", encoding='utf-8', level=logging.DEBUG)
    df_1: pd.DataFrame = load_items_dataset(Path("data/sec_items/"), ["ITEM 1", "ITEM 1A", "ITEM 1B"])
    df_7: pd.DataFrame = load_items_dataset(Path("data/sec_items/"), ["ITEM 7", "ITEM 7A", "ITEM 7B"])
    df_operating_segments = extract_operating_segments(df_1)
    df_operating_segments.to_csv("data/operating_segments/operating_segments_basic.csv")
    df_operating_segments = pd.read_csv("data/operating_segments/operating_segments_basic.csv")
    df_operating_segments_with_revenue = hydrate_operating_segments_with_10k_metric(df_7, df_operating_segments, METRIC_10K_NAME)
    df_operating_segments_with_revenue.to_csv("data/operating_segments/operating_segments_with_operating_income.csv")
