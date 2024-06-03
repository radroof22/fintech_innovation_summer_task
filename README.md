# Operating Segment Operating Income Analysis of 10-K using LLAMA

[Hosted Site](https://fintechinnovationsummertask-bpeezzw2zoye8uhzardcjx.streamlit.app/)

## Tech Stack

1. BeautifulSoup + Regex: Beautiful soup allows for extremely easy manipulation of HTML/XML data formats which is especially useful in latter published 10-K reports which adopt a similar format. Regex was important in identifying key terms such as Item names through the text and where they occur in the text.

2. Pandas: Pandas was vital for storing and organizing all of the tabular data related to companies, the year their 10-k report was published etc. Pandas was used over other tools or custom implementations because of its speed of merging rows with similar columns and compatibility with a variety of file types.

3. DeepInfra: Deep Infra was used for LLM inference because of its generous free tier. In addition, it supports the OpenAI LLM API format which abstracts away special tokens increasing developer velocity.

4. Llama-3 70B Instruct: This LLM was chosen because of its free tier offering on DeepInfra as well as its high ranking on QA tasks according to HuggingFace OpenLLM leaderboards.

5. sec-edgar-downloader: This package was used because of its ease-of-use when downloading 10-K files, increasing development speed.

6. Streamlit: This package was used for our frontend because of its compatibility with pandas Dataframes as well as built in BarChart support. In addition, the hosted service for streamlit makes deployment extremely easy.

## Insight Explanation

Users will be wary if they glimpse decreasing operating income in key operating segments (especially those that make up a majorty of the companies overall operating income). User's can use this graph to visualize the change in operating income over time across different operating segments.