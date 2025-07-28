import http.client
import logging
import os
import random
import string
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
        content = response.read()
        logging.info(f"Successfully fetched content from {url}")
        return content
    else:
        logging.error(
            f"Failed to retrieve webpage, Status Code: {response.status}")
        return None


def scrape_players(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    # Since the table is a div that mimics a table, we find all divs that act as rows
    table_container = soup.find('div', class_='divtable divtable-striped')
    if not table_container:
        logging.error("No divtable found in the fetched content")
        return None, None

    # Assuming the first div is the header and subsequent divs are the rows
    headers = [div.get_text(strip=True) for div in table_container.find_all('div', recursive=False)[0].find_all('div')]
    rows = [
        [div.get_text(strip=True) for div in row.find_all('div')]
        for row in table_container.find_all('div', recursive=False)[1:]
    ]
    
    logging.info("Table data extracted successfully")
    return headers, rows

def save_to_csv(df, letter):
    directory = "data"
    if not os.path.exists(directory):
        os.makedirs(directory)
    file_path = os.path.join(directory, f"players_{letter}.csv")
    df.to_csv(file_path, index=False)
    logging.info(f"Saved DataFrame to {file_path}")


def scrape_letters():
    alphabet = string.ascii_uppercase
    for letter in tqdm(alphabet, desc="Letters"):
        url = f"https://www.footballdb.com/players/current.html?letter={letter}"
        html_content = fetch(url)
        if html_content:
            headers, rows = scrape_players(html_content)
            if headers is not None and rows is not None:
                df = pd.DataFrame(rows, columns=headers)
                save_to_csv(df, letter)
            else:
                print(f'Data missing for letter: {letter}')
        else:
            print(f'Failed to fetch data for letter: {letter}')
        time.sleep(random.uniform(1, 3))


if __name__ == "__main__":
    scrape_letters()
