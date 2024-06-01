from pathlib import Path
import os
import json
import argparse

import requests
import dotenv
import pandas as pd
import time

dotenv.load_dotenv("./.env")
DEEP_INFRA_TOKEN = os.getenv("DEEP_INFRA_TOKEN")

def ask_llama(context: str, prompt: str) -> str:
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {DEEP_INFRA_TOKEN}"}
    responses = []
    for context_chunk in context[::4080]:
        
        data = {"stream": False, "input": f"{context_chunk} [INST]{prompt}[/INST]"}
        resp = requests.post("https://api.deepinfra.com/v1/inference/meta-llama/Llama-2-13b-chat-hf", json=data, headers=headers).json()
    
        llama_response:str = resp["results"][0]['generated_text']
        responses.append(llama_response)
        time.sleep(1.0)
    return responses

def extract_factors_in_7a(item_7a_text: str) -> list[str]:
    prompt = "Identify key information that is relevant to risks the company faces. Answer only in bullet points of what important insight can be taken away. If there is no insight, respond with by saying 'nothing'"
    response = ask_llama(item_7a_text, prompt)
    prompts = response
    extracted_insights = []
    for prompt_response in prompts:
        # print(prompt_response)
        bullet_index = prompt_response.index(":")
        bullets = prompt_response[bullet_index:].split("* ")
        for bullet in bullets[1:]:
            extracted_insights.append(bullet)
    return extracted_insights

def summarize_insights(all_7a_risk_factors: str) -> list[str]:
    prompt = "Give me the top risk factors for the company listed in a bullet point list. Only give me the list and no other text. It can be any number of bullets."
    final_insights = ask_llama(all_7a_risk_factors, prompt)
    bullet_list = [b.strip() for b in final_insights[0].split("\u2022")[1:]]
    return bullet_list

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Program to convert sec-edgar-filings for ticker")
    parser.add_argument("ticker", help="Ticker for stock symbol")

    args = parser.parse_args()
    ticker = args.ticker

    path_to_sec_items = Path(f"data/sec_items/sec_items_{ticker}.json")

    df = pd.read_json(path_to_sec_items)

    df_7 = df[df.Item == "ITEM 7"]
    df_7a = df[df.Item == "ITEM 7A"]

    output = {}

    for i in range(len(df_7a)):
        year = df_7a.iloc[i].Year
        context = df_7.iloc[i].Text + "\n" + df_7a.iloc[i].Text
        extracted_insights = extract_factors_in_7a(context)
        final_risk_factors = summarize_insights(extracted_insights)
        final_risk_factors = list(filter(lambda x: len(x) > 1, final_risk_factors))
        output[str(year)] = final_risk_factors
        print(f"Extracted data for {year}")

        with open(f"data/summary_7a/summary_7_{ticker}.json", 'w') as f:
            json.dump(output, f)





        
