import requests
from bs4 import BeautifulSoup as bs
import os

SITE_URL = "https://explorer.mainnet.near.org"
PLATFORM_ID = "lolcoin_platform.near"
PORT = int(os.getenv("PORT", default=5000))

file = open('transictions_list.txt', 'r+')
file_transactions = file.read().split('\n')


def parsing():
    URL = SITE_URL + "/accounts/lolcoin.qbit.near"
    page = requests.get(URL)
    soup = bs(page.text, "html.parser")
    transactions = []
    for element in soup.find_all('div', class_='c-ActionRowTransaction-lbSlCc col'):
        transaction = element.find('a', href=True)
        transaction_url = transaction['href']
        if transaction_url in file_transactions:
            break
        else:
            file.write(transaction_url + '\n')
        transactions.append(transaction['href'])
        # if len(transactions) == 5:
        #     break
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
