import pandas as pd
from bs4 import BeautifulSoup as bs
import requests

from .partants import Partants

import time
import concurrent
from threading import Thread,local
import requests
from requests.sessions import Session



headers = {
    'Accept-Encoding': 'gzip, deflate, sdch',
    'Accept-Language': 'en-US,en;q=0.8',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
}

hippo_letrot = ["LE MONT-SAINT-MICHEL-PONTORSON", "BORDEAUX", "LE CROISE-LAROCHE", "MARSEILLE (A BORELY)"]
hippo_pmu =  ["LE MONT SAINT MICHEL", "LE BOUSCAT", "LE CROISE LAROCHE", "BORELY"]

import nest_asyncio
nest_asyncio.apply()

thread_local = local()

def get_session() -> Session:
    if not hasattr(thread_local, 'session'):
        thread_local.session =  requests.Session()
    return thread_local.session

def get_request_with_session(url:str):
    session = get_session()
    with session.get(url, headers=headers) as response:
        return response

def gen_rows(df):
    for row in df.itertuples(index=False):
        yield row._asdict()


def get_df_partants(courses):
    info = []
    t = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        res = executor.map(Partants, gen_rows(courses))
        for i in res:
            if isinstance(i.info_partants, list):
                info.extend(i.info_partants)
    return pd.DataFrame(info)