import pandas as pd
import streamlit as st


if __name__ == "__main__":
    df = pd.read_csv("operating_segments_with_revenue_v1.csv")

    list_of_tickers: list[str] = ["INTC", "KO", 'AAPL']
    option = st.selectbox(
        "Ticker to view 10-K information for.",
        list_of_tickers,
        index=2
    )
    
    st.header("Revenue by Operating Segment")
    c = st.container()
    df_ticker = df[df.Company == option]
    df_ticker = df_ticker.dropna(axis=0)
    unique_operating_segments = df_ticker["Operating Segment"].unique()
    st.bar_chart(df_ticker, x="Year", y="Revenue", color="Operating Segment")
    st.markdown("*Note missing years are due to LLAMA instability in parsing 10-K reports*. Updates will be made.")
    