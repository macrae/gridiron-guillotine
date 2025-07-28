import http.client
import logging
import os
import random
import time
from urllib.parse import urlparse

import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm

# Setup logging
logging.basicConfig(filename='scraping.log', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')


def fetch(url):
    parsed_url = urlparse(url)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    conn = http.client.HTTPSConnection(parsed_url.netloc)
    conn.request("GET", parsed_url.path + "?" +
                 parsed_url.query, headers=headers)
    response = conn.getresponse()
    if response.status == 200:
        return response.read()
    else:
        logging.error(
            f"Failed to retrieve webpage, Status Code: {response.status}")
        return None


def scrape_table(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')
    if not table:
        logging.error("No table found")
        return None
    # Define headers manually to avoid complications
    headers = ['Player', 'Game', 'Pts*', 'Passing_Att', 'Passing_Cmp',
               'Passing_Yds', 'Passing_TD', 'Passing_Int', 'Passing_2Pt',
               'Rushing_Att', 'Rushing_Yds', 'Rushing_TD', 'Rushing_2Pt',
               'Receiving_Rec', 'Receiving_Yds', 'Receiving_TD', 'Receiving_2Pt',
               'Fumble_FL', 'Fumble_TD']
    rows = [[td.get_text(strip=True) for td in tr.find_all('td')]
            for tr in table.find_all('tr')[2:]]
    return headers, rows


def create_dataframe(headers, rows):
    if headers and rows:
        return pd.DataFrame(rows, columns=headers)
    else:
        logging.error("No data available to create DataFrame.")
        return None


def save_to_csv(df, year, week):
    directory = "data"
    if not os.path.exists(directory):
        os.makedirs(directory)
    file_path = os.path.join(directory, f"offense_{year}_{week}.csv")
    df.to_csv(file_path, index=False)
    logging.info(f"Saved DataFrame to {file_path}")

# Main scraping function


def scrape_years_weeks(start_year, end_year):
    for year in tqdm(range(start_year, end_year + 1), desc="Years"):
        for week in tqdm(range(1, 18), desc="Weeks"):
            url = f"https://www.footballdb.com/fantasy-football/index.html?pos=OFF&yr={year}&wk={week}"
            html_content = fetch(url)
            if html_content:
                headers, rows = scrape_table(html_content)
                if headers and rows:
                    df = create_dataframe(headers, rows)
                    if df is not None:
                        save_to_csv(df, year, week)
            # Random sleep between 1 to 3 seconds
            time.sleep(random.uniform(1, 3))


if __name__ == "__main__":
    scrape_years_weeks(2022, 2024)  # Scrape from 2022 to 2024
