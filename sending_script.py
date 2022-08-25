import os

import requests
import json

url = 'https://coins.summerschool.lol/send-transfer'
MNEMONIC_PHRASE = os.getenv("MNEMONIC_PHRASE")


async def send_lolcoin(receiver_id, amount):
    body = {
        "transfer_amount": str(amount),
        "sender_account_id": "lolcoin_platform.near",
        "sender_seed_phrase": MNEMONIC_PHRASE,
        "receiver_account_id": receiver_id
    }
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "en-US,en;q=0.5",
        "connection": "keep-alive",
        "content-length": "207",
        "content-type": "application/json",
        "host": "coins.summerschool.lol",
        "origin": "https://coins.summerschool.lol",
        "referer": "https://coins.summerschool.lol/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:103.0) Gecko/20100101 Firefox/103.0}"
    }

    return requests.post(url, data=json.dumps(body), headers=headers)
