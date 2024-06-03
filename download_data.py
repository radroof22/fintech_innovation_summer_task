from datetime import datetime
import pathlib

from sec_edgar_downloader import Downloader


class SECDownloader:
    def __init__(self, personal_company_name: str, email: str):
        """
        Args:
            - personal_company_name: str
                Name of company you represent and requesting SEC data from
            - email: str
                Your email from for SEC to identify who is requesting data
        """
        self.downloader = Downloader(personal_company_name, email)

    def download_10_k_historical(self, ticker: str, from_timestamp: datetime, to_timestamp: datetime):
        """
        Download 10-K data for ticker between the from timestamp and to timestamp. Will write to a folder
        `sec-edgar-filings`. If you download multiple tickers, there will be a subfolder `sec-edgar-filings/TICKER`
        but otherwise will be all under `sec-edgar-filings`.

        Args:
        - ticker: str
            Stock ticker you want to download 10K data for
        - from_timestamp: datetime
            Download all 10-K reports after this timestamp
        - to_timestamp: datetime
            Download all 10-K reports before this timestamp
        """
        self.downloader.get("10-K", ticker,
                            after=from_timestamp.strftime("%Y-%m-%d"), 
                            before=to_timestamp.strftime('%Y-%m-%d'))

if __name__ == "__main__":
    TICKERS: list[str] = [
        "AAPL",
        "KO",
        "INTC",
    ]

    FROM_TIMESTAMP = datetime(1995, 1, 1)
    TO_TIMESTAMP = datetime(2024, 1, 1)
 
    sec_downloader = SECDownloader("Georgia Tech", "rmehta98@gatech.edu")
    for ticker in TICKERS:
        sec_downloader.download_10_k_historical(ticker, FROM_TIMESTAMP, TO_TIMESTAMP)
        print(f"Finished Downloading: {ticker}")
    
