import requests
from bs4 import BeautifulSoup as bs
import psycopg2
from urllib.parse import urlparse
import os

# from dotenv import load_dotenv
# load_dotenv()

SITE_URL = "https://explorer.mainnet.near.org"
PLATFORM_ID = "lolcoin_platform.near"

background_tasks = set()

# database setup
DB_URL = os.getenv('DATABASE_URL')
db_parse = urlparse(DB_URL)
db_username = db_parse.username
db_password = db_parse.password
db_name = db_parse.path[1:]
db_hostname = db_parse.hostname
db_port = db_parse.port
conn = psycopg2.connect(
    database=db_name,
    user=db_username,
    password=db_password,
    host=db_hostname,
    port=db_port
)
cur = conn.cursor()


def parsing():
    URL = SITE_URL + "/accounts/lolcoin.qbit.near"
    page = requests.get(URL)
    soup = bs(page.text, "html.parser")
    transactions = []
    for element in soup.find_all('div', class_='c-ActionRowTransaction-lbSlCc col'):
        transaction = element.find('a', href=True)
        transaction_url = transaction['href']
        cur.execute(f"""SELECT * FROM transfer_list WHERE transfers_url = '{transaction_url}'""")
        result = cur.fetchone()
        if result:
            break
        else:
            cur.execute(f"""INSERT INTO transfer_list VALUES('{transaction_url}')""")
        transactions.append(transaction['href'])
        # if len(transactions) == 5:
        #     break
    conn.commit()
    transactions_parameters = []
    amount = 0
    sender = ''
    for TRANSACTION_URL in transactions:
        URL = SITE_URL + TRANSACTION_URL
        page = requests.get(URL)
        soup = bs(page.text, "html.parser")
        result = soup.find('div', class_='c-ReceiptRowStatus-cQiaau col')
        if result.text != 'Empty result':
            continue
        transactions_code = soup.find('div', class_='c-CodePreviewWrapper-gJFGlx').text.split('\n')[1:-1]
        for line in transactions_code:
            try:
                line = line.split(': ')
                if line[0].strip() == '"amount"':
                    amount = int(line[1][1:-2])
                elif line[0].strip() == '"receiver_id"':
                    receiver = line[1][1:-2]
                    if receiver != PLATFORM_ID:
                        break
                elif line[0].strip() == '"sender_id"':
                    sender = line[1][1:-1]
            except IndexError:
                break
        else:
            transactions_parameters.append({"amount": amount,
                                            "sender": sender})
    return transactions_parameters


if __name__ == "__main__":
    transactions_list = parsing()
    print(transactions_list)
