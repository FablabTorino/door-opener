import json
import os
from os.path import join, dirname
from dotenv import load_dotenv, find_dotenv
#import paho.mqtt.client as mqtt
import re
import time
#import curl
import requests
import logging
from requests.structures import CaseInsensitiveDict
from collections.abc import MutableMapping
from urllib.parse import urlencode, unquote

logging_path = join(os.getcwd(), dirname(__file__), 'pysync.log')
logging.basicConfig(
    filename=logging_path,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
   # format=' %(levelname)s - %(message)s', # use only for debugging
    level=logging.INFO)

# environment variables
dotenv_path = join(os.getcwd(), dirname(__file__), '.env')
load_dotenv(find_dotenv(dotenv_path, raise_error_if_not_found=True))

TOKEN = os.getenv('WINDDOC_TOKEN')
if TOKEN is None:
    logging.error("WINDDOC_TOKEN not set in .env")
TOKEN_APP = os.getenv('WINDDOC_TOKEN_APP')
if TOKEN_APP is None:
    logging.error("WINDDOC_TOKEN_APP not set in .env")
 
def http_build_query(dictionary, parent_key=False, separator='.', separator_suffix=''):
    """
    Turn a nested dictionary into a flattened dictionary
    :param dictionary: The dictionary to flatten
    :param parent_key: The string to prepend to dictionary's keys
    :param separator: The string used to separate flattened keys
    :return: A flattened dictionary
    """

    items = []
    for key, value in dictionary.items():
        new_key = str(parent_key) + separator + key + separator_suffix if parent_key else key
        if isinstance(value, MutableMapping):
            items.extend(http_build_query(value, new_key, separator, separator_suffix).items())
        elif isinstance(value, list) or isinstance(value, tuple):
            for k, v in enumerate(value):
                items.extend(http_build_query({str(k): v}, new_key, separator, separator_suffix).items())
        else:
            items.append((new_key, value))
    return dict(items)

URL = "https://app.winddoc.com/v1/api_json.php";

logging.info("START SYNC")
headers = CaseInsensitiveDict()
headers["accept"] = "application/json"
headers["Content-Type"] = "application/x-www-form-urlencoded"

firstpage = {"method":"associazioni_soci_listaCercaSV","request":{"token_key":{"token":TOKEN, "token_app":TOKEN_APP},"query":""}}
firstpage = http_build_query(firstpage, False, '[', ']')
q_firstpage = urlencode(firstpage)

r = requests.post(URL, headers=headers, data=q_firstpage)

f_json = open("./WindDocSync/pysync.json", "w")
f_json.write(r.text) 

returnedData = json.loads(r.content)
num_pages = returnedData['numero_pagine']
logging.info("Pagina: 1/" + str(num_pages) + " CODE:" + str(r.status_code))
for page in range(2,num_pages-1):
    otherpages = {"method":"associazioni_soci_listaCercaSV","request":{"token_key":{"token":TOKEN, "token_app":TOKEN_APP},"query":"","pagina":page}}
    otherpages = http_build_query(otherpages, False, '[', ']')
    q_otherpages = urlencode(otherpages)
    r1 = requests.post(URL, headers=headers, data=q_otherpages)
    logging.info("Pagina: " + str(page) + "/" + str(num_pages)+ " CODE:" + str(r1.status_code))
    f_json.write(r.text)
    
f_json.close()
logging.info("END SYNC")

