import os
import time

import requests

DEEP_INFRA_TOKEN = os.getenv("DEEP_INFRA_TOKEN")
JUMP_SIZE = 4080
RATE_LIMITING = 0.50

def ask_llama(messages: list[dict[str, str]]) -> str:
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {DEEP_INFRA_TOKEN}"}
    data = {
        "model": "meta-llama/Meta-Llama-3-8B-Instruct",
        'messages': messages
    }
    resp = requests.post("https://api.deepinfra.com/v1/openai/chat/completions", json=data, headers=headers).json()
    if "choices" not in resp:
        print(resp)
    llama_response: str = resp["choices"][0]["message"]["content"]
    time.sleep(RATE_LIMITING)
    return llama_response

def summarize_operating_segments(llama_responses: list[str]):
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
                "content": context
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


def identify_revenue_by_operating_segment(context: str, company: str, year: int, operating_segment: str) -> str:
    EXTRACT_REVENUE_BY_OPERATING_SEGMENT_PROMPT = f"""
        Read the above sections of the 10-K report for {company} in the year {year} relevant to the {operating_segment} operating segment. 
            Identify the stock's operating income for the {operating_segment} operating segment in the year {year - 1}
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
                "content": context
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
        return consolidate_revenue_by_operating_segment_responses(responses, operating_segment, year)
    elif len(responses) == 0:
        return ""
    return responses[0]

def consolidate_revenue_by_operating_segment_responses(responses: list[str], operating_segment: str, year: int):
    request_body = [
        {
            "role": "system",
            "content": "You are an expert financial advisor. Read the following 10-K Report information and answer the questions, being careful about providing the correct information"
        },
        {
            "role": "user",
            "content": f"I previously asked you to identify the the {operating_segment} operating segment revenue in the year {year - 1} according to the 10-K report. Read your responses below. I will ask you a follow up question after: {'\n'.join(responses)}"
        },
        {
            "role": "assistant",
            "content": "Okay, I have read it. What is the question?"
        },
        {
            "role": 'user',
            "content": f"Clearly identify a single value for the revenue for the {operating_segment} operating_segment revenue. Only output one number and nothing else: Should be in the format: $xxxxxx"
        }
    ]

    response:str = ask_llama(request_body)
    return response
