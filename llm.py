import os
import time

import requests

DEEP_INFRA_TOKEN = os.getenv("DEEP_INFRA_TOKEN")
JUMP_SIZE = 4080
RATE_LIMITING = 0.50

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


def identify_operating_income_by_operating_segment(context: str, metric_10k: str, company: str, year: int, operating_segment: str) -> str:
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
            Identify the stock's {metric_10k} for the {operating_segment} operating segment in the year {year - 1}
            The expected format is below (ONLY OUTPUT THE NUMBER AND DOLLAR SIGN. NO OTHER TEXT): 
            $xxxxxxxx
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

    if len(responses) > 1:
        return consolidate_metric_by_operating_segment_responses(responses, metric_10k, operating_segment, year)
    elif len(responses) == 0:
        return ""
    return responses[0]

def consolidate_metric_by_operating_segment_responses(responses: list[str], metric_10k: str, operating_segment: str, year: int) -> str:
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
    return response