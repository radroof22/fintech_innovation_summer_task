import os
import time
import re

import requests
import numpy as np

DEEP_INFRA_TOKEN = os.getenv("DEEP_INFRA_TOKEN")
JUMP_SIZE = 4080 # max size of context for Llama request
RATE_LIMITING = 0.50 # prevent rate limiting from DeepInfra (time to sleep (sec))

def ask_llama(messages: list[dict[str, str]]) -> str:
    """
    Uses DeepInfra API to make a request to Llama 70B-Instruct. Use roles "system", "user", and "assistant".
        Ensure that the last message is "role: user" and "content: ..." is the question or task for llama.

    Args:
    - messages: list[dict[str, str]]
        The input should be a JSON (Python dictionary) containing the relevant chat history
        the model should use to output its next response. 

    Returns:
    - string of Llama's response to your last question.
    """

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {DEEP_INFRA_TOKEN}"}
    data = {
        "model": "meta-llama/Meta-Llama-3-70B-Instruct",
        'messages': messages
    }
    resp = requests.post("https://api.deepinfra.com/v1/openai/chat/completions", json=data, headers=headers).json()
    if "choices" not in resp:
        print(resp)
    llama_response: str = resp["choices"][0]["message"]["content"]
    time.sleep(RATE_LIMITING)
    return llama_response

def summarize_operating_segments(llama_responses: list[str]):
    """
    Use in case context for llama is too large and multiple requests have to be made to llama for the same task.
    This function will try to take llama's response and ask Llama to summarize and consolidate the total list of 
    operating segments that the model proposed.

    Args:
    - llama_responses: list[str]
        List of string responses from Llama for the Operating Segment extraction task.
    """

    request_body = [
        {
            "role": "system",
            "content": "You are an expert financial advisor. Read the following 10-K Report information and answer the questions, being careful about providing the correct information"
        },
        {
            "role": "user",
            "content": f"I previously asked you to summarize the operating segments according to the 10-K report. Read your responses below. I will ask you a follow up question after: {'\n'.join(llama_responses)}"
        },
        {
            "role": "assistant",
            "content": "Okay, I have read it. What is the question?"
        },
        {
            "role": 'user',
            "content": "Summarize your responses previously into a final list of operating segments. List them in the following format: SEGMENT 1, SEGMENT 2, ..."
        }
    ]

    response:str = ask_llama(request_body)
    return response

def identify_operating_segments(context: str, company: str, year: int) -> str:
    """
    Given certain elements of the 10-K report, this function will ask Llama to identify the operating 
    segments for the company. If the context is too large. the function will use multiple requests to llama
    and then a final request to the model to consolidate the potentially multiple different operating segments
    it proposed.

    Args:
    - context: str
        The specific sections of 10-K report important for identifying the Operating Segments
    - company: str
        The name of the company the 10-K report is of
    - year: str
        The year the 10-K report was published.

    Returns:
    - string
        Llama's raw resposne to trying to identify the operating_segments
    """
    EXTRACT_OPERATING_SEGMENTS_PROMPT = f"""Read the above sections of the 10-K report for {company} in the year {year}. 
        Identify the stock's operating segments and list them outputting only the operating segments and in the following format: 
        'SEGMENT 1, SEGMENT 2, SEGMENT 3...'"""
    
    responses = []
    for i in range(0, len(context), JUMP_SIZE):
        context_chunk = context[i: i + JUMP_SIZE]
        request_body = [
            {
                "role": "system",
                "content": "You are an expert financial advisor. Read the following 10-K Report information and answer the questions, being careful about providing the correct information"
            },
            {
                "role": "user",
                "content": context_chunk
            },
            {
                "role": "assistant",
                "content": "I have read and analyzed the 10-k report. Ask me a question about it?"
            },
            {
                "role": "user",
                "content": EXTRACT_OPERATING_SEGMENTS_PROMPT
            }
        ]
        
        llama_response = ask_llama(request_body)
        responses.append(llama_response)
    if len(responses) > 1:
        return summarize_operating_segments(responses)
    elif len(responses) == 0:
        return ""
    return responses[0]


def identify_metric_10k_by_operating_segment(context: str, metric_10k: str, company: str, year: int, operating_segment: str) -> list[str]:
    """
    Given relevant sections of the 10-K report for the metric, ask llama to identify the specific metric for the specific operating segment.
    The metrics include revenue/sales, operating income, and more.
    In case the context is too large, multiple requets with sections of the context will be used and then Llama
    will be asked to consolidate its responses into a single response.

    Args:
    - context: str
        The specific sections of 10-K report important for identifying the Operating Segments
    - metric_10k: str
        The metric to find for each of the 10-K reports
    - company: str
        The name of the company the 10-K report is of
    - year: str
        The year the 10-K report was published.

    Returns:
    - string
        Llama's raw resposne to trying to identify the operating_segments

    """
    
    EXTRACT_REVENUE_BY_OPERATING_SEGMENT_PROMPT = f"""
        Read the above sections of the 10-K report for {company} in the year {year} relevant to the {operating_segment} operating segment. 
            Identify the stock's {metric_10k} for the {operating_segment} operating segment in the year {year - 1}.
            When reading the report you may encounter negative numbers which are symbolized by parentheses around them (i.e. (XX.XX)). Make sure
            you return the resulting value using a negative appropriately.
            The expected format is below (ONLY OUTPUT THE NUMBER AND DOLLAR SIGN (and possible negative sign). NO OTHER TEXT): 
            $xxxxxxxx or -$xxxxxxxx.
    """
    
    responses = []
    for i in range(0, len(context), JUMP_SIZE):
        context_chunk = context[i: i + JUMP_SIZE]
        request_body = [
            {
                "role": "system",
                "content": "You are an expert financial advisor. Read the following 10-K Report information and answer the questions, being careful about providing the correct information"
            },
            {
                "role": "user",
                "content": context_chunk
            },
            {
                "role": "assistant",
                "content": "I have read and analyzed the 10-k report. Ask me a question about it."
            },
            {
                "role": "user",
                "content": EXTRACT_REVENUE_BY_OPERATING_SEGMENT_PROMPT
            }
        ]

        llama_response = ask_llama(request_body)
        
        responses.append(llama_response)

    final_response:str = responses[-1]
    if len(responses) > 1:
        final_response: str = consolidate_metric_by_operating_segment_responses(responses, metric_10k, operating_segment, year)
    elif len(responses) == 0:
        return ""
    return parse_operating_segments_from_llama_response(final_response)


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

def consolidate_metric_by_operating_segment_responses(responses: list[str], metric_10k: str, operating_segment: str, year: int) -> float:
    """
    In the event that identifying the metric fo the operating segments requires multiple requests, use this Llama request
    to figure out what is the true answer based on the llama requests you just made.

    Args:
    - responses: list[str]
        Raw llama responses for finding the metric for the operating segments.
    - metric_10k: str
        Metric that was attempted to be extracted from the llama responses
    - operating_segment: str
        Part of the business the metric is extracted for
    - year: int
        Year of the 10-K reports release

    Return:
    - string of the consolidated response for the metric_10k according to the llama responses.


    """
    request_body = [
        {
            "role": "system",
            "content": "You are an expert financial advisor. Read the following 10-K Report information and answer the questions, being careful about providing the correct information"
        },
        {
            "role": "user",
            "content": f"I previously asked you to identify the the {operating_segment} operating segment {metric_10k} in the year {year - 1} according to the 10-K report. Read your responses below. I will ask you a follow up question after: {'\n'.join(responses)}"
        },
        {
            "role": "assistant",
            "content": "Okay, I have read it. What is the question?"
        },
        {
            "role": 'user',
            "content": f"Clearly identify a single value for the {metric_10k} for the {operating_segment} operating_segment {metric_10k}. Only output one number and nothing else: Should be in the format: $xxxxxx"
        }
    ]

    response:str = ask_llama(request_body)
    return format_monetary_from_llama_response(response)


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
    
    if line.count(",") == 1:
        line += " million"
    mark_neg = False
    if "-" in line:
        mark_neg = True
    line = line.replace("$", "").replace(",", "")

    if "million" in line:
        value = re.sub(r'[^(0-9) ]', '', line) 
        value = float(value) * 1e6
    elif "billion" in line:
        value = re.sub(r'[^(0-9) ]', '', line) 
        value = float(value) * 1e9
    else:
        if line.count(",") < 1:
            value = re.sub(r'[^(0-9) ]', '', line) 
            value = float(value) * 1e6
        else:
            value = re.sub(r'[^(0-9) ]', '', line) 
            value = float(value)
    
    # avoid exploding exponential terms due to llama instability
    if value > 1e9:
        stem = value / (10**int(np.log10(value)))
        value = stem * 1e9
    return -value if mark_neg else value