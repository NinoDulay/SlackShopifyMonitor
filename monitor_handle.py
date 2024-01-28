import requests as rq
import urllib3
import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from jsondiff import diff
import random

from pprint import pprint
from random_user_agent.params import SoftwareName, HardwareType
from random_user_agent.user_agent import UserAgent

from database_handle import get_all_manual_products, update_manual_product, get_all_keyword_products, insert_keyword_product, edit_proxy, get_all_proxies
from config import USERNAME, COLOR, CHANNEL

## SETUP USER AGENTS RANDOMIZER
urllib3.disable_warnings()
software_names = [SoftwareName.CHROME.value]
hardware_type = [HardwareType.MOBILE__PHONE]
user_agent_rotator = UserAgent(software_names=software_names, hardware_type=hardware_type)

## LOGGING SETUP
logging.basicConfig(
    level = logging.INFO,
    format = "[{asctime}] {levelname:<8} | {message}",
    style = "{",
    filename = "shopify_monitor.txt",
    filemode = 'a'
)

TIMEOUT = 20
HEADERS = {
        'User-Agent': user_agent_rotator.get_random_user_agent(),
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }
env_path = Path(".") / '.env'
load_dotenv(dotenv_path=env_path)
WEBHOOK = os.environ['G_WEBHOOK']

def variants_checker(product_url:str, old_data: dict, new_data: dict) -> dict:
    option_index = 0
    stock = None
    is_tshirt = False
    tshirt_sizes = ['XXXXXS', '5XS','XXXXS', '4XS', 'XXXS', '3XS', '2XS', 'XXS', 'XS', 'S', 'SM', 'SMALL', 'M', 'MD', 'MEDIUM', 'L', 'LG', 'LARGE', 'XL', 'XXL', '2XL', 'XXXL', '3XL', 'XXXXL', '4XL', 'XXXXXL', '5XL', 'XXXXXXL', '6XL']

    old_variants = old_data['variants']
    new_variants = new_data['variants']

    restocks = {
        'title': new_data['title'],
        'new_variants': []
    }
    for old, new in zip(old_variants, new_variants):
        for c, option in enumerate(new['options']):
            if option.upper() in tshirt_sizes:
                option_index = c
                is_tshirt = True
                break
        
        if is_tshirt:
            size = new['options'][option_index]
        else:
            for c, option in enumerate(new['options']):
                if option.replace(".","").isnumeric() and ((len(option) < 3 and "." not in option) or (len(option) < 5 and "." in option)):
                    size = option
                else:
                    size = new['title']
        if old != new:
            for key in old:
                # Find out if tshirt or not (for sizing)
                if old[key] != new[key]:
                    # Find out how many stock
                    if key == 'inventory_quantity':
                        
                        try:
                            if new['inventory_quantity'] > 0:
                                stock = new['inventory_quantity']
                            elif new['inventory_quantity'] < 1:
                                stock = "Quantity unknown"
                        except:
                            stock = "Quantity unknown"
            if old['available'] and not(new['available']):
                restocks['new_variants'].append({'what':'OUT OF STOCK','size': size, 'stock': stock, 'atc_url': product_url[:product_url.find('/', 10)] + '/cart/' + str(new['id']) + ":1", 'sku': new['sku'], 'variant_id': new['id'], 'available': new['available']})
            else:
                restocks['new_variants'].append({'what':'RESTOCK','size': size, 'stock': stock, 'atc_url': product_url[:product_url.find('/', 10)] + '/cart/' + str(new['id']) + ":1", 'sku': new['sku'], 'variant_id': new['id'], 'available': new['available']})
        else:
            if new['available']:
                try:
                    if new['inventory_quantity'] > 0:
                        stock = new['inventory_quantity']
                    elif new['inventory_quantity'] < 1:
                        stock = "Quantity unknown"
                except:
                    stock = "Quantity unknown"

                restocks['new_variants'].append({'what':'REMAIN','size': size, 'stock': stock, 'atc_url': product_url[:product_url.find('/', 10)] + '/cart/' + str(new['id']) + ":1", 'sku': new['sku'], 'variant_id': new['id'], 'price': new['price']/100, 'available': new['available']})

    return restocks

def variant_finder(product_url:str, data: dict) -> dict:
    option_index = 0
    stock = None
    is_tshirt = False
    tshirt_sizes = ['XXXXXS', '5XS','XXXXS', '4XS', 'XXXS', '3XS', '2XS', 'XXS', 'XS', 'S', 'SM', 'SMALL', 'M', 'MD', 'MEDIUM', 'L', 'LG', 'LARGE', 'XL', 'XXL', '2XL', 'XXXL', '3XL', 'XXXXL', '4XL', 'XXXXXL', '5XL', 'XXXXXXL', '6XL']

    variants = data['variants']

    restocks = {
        'title': data['title'],
        'new_variants': []
    }
    for new in variants:
        for c, option in enumerate(new['options']):
            if option.upper() in tshirt_sizes:
                option_index = c
                is_tshirt = True
                break
        
        if is_tshirt:
            size = new['options'][option_index]
        else:
            for c, option in enumerate(new['options']):
                if option.replace(".","").isnumeric() and ((len(option) < 3 and "." not in option) or (len(option) < 5 and "." in option)):
                    size = option
                else:
                    size = new['title']

            for key in new:

                # Find out how many stock
                if key == 'inventory_quantity':
                    
                    try:
                        if new['inventory_quantity'] > 0:
                            stock = new['inventory_quantity']
                        elif new['inventory_quantity'] < 1:
                            stock = "Quantity unknown"
                    except:
                        stock = "Quantity unknown"

            restocks['new_variants'].append({'size': size, 'stock': stock, 'atc_url': product_url[:product_url.find('/', 10)] + '/cart/' + str(new['id']) + ":1", 'sku': new['sku'], 'variant_id': new['id'], 'available': new['available']})

    return restocks

def slack_webhook_restock(product_url:str, restock_data:dict):
    product_data = get_info_by_url(product_url)
    product_url = product_url.split("?")[0]

    image = f"https://" + product_data['image'][2:]
    image = image.strip()

    website_name = product_url.replace("https://", "").replace("www.", "").split("/")[0].replace(".com", "").upper().strip()
    
    product_price = product_data['price']/100

    stocks = ""
    sizes = ""

    for data in restock_data['new_variants']:
        if data['what'] != "REMAIN":
            if str(data[ 'stock']).lower() == "quantity unknown" and not(data['available']):
                stocks += "*~OUT OF STOCK~*" + "\n"
            elif str(data['stock']).lower() == "quantity unknown" and data['available']:
                stocks += "_Quantity Unknown_" + "\n"
            else:
                stocks += str(data['stock']) + "\n"
        
            sizes = '\n'.join([f"<{i['atc_url'].strip()}|{str(i['size'])}>" for i in restock_data['new_variants']])

    slack_msg = {
        "username": USERNAME,
        "icon_emoji": "money_with_wings",
        "channel": CHANNEL,
        "attachments":[{
            "color": COLOR,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*<{product_url.strip()} | RESTOCK [{len(restock_data['new_variants'])} sizes]: {restock_data['title']} | {website_name} | ${product_price}>*",
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"""*Total Stock:*\n{stocks}"""
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Size/Stock Level:*\n{sizes}"
                        }
                    ]
                },
            ]
        }
        ]
    }

    if image:
        slack_msg['attachments'][0]['blocks'][0]["accessory"] = {
                        "type": "image",
                        "image_url": image,
                        "alt_text": restock_data['title']
                    }

    if len(stocks) > 0:
        result = rq.post(WEBHOOK, data=json.dumps(slack_msg))

def slack_webhook_price_drop(product_url:str, restock_data:dict, old_price: float):
    product_data = get_info_by_url(product_url)
    product_url = product_url.split("?")[0]

    image = f"https://" + product_data['image'][2:]
    image = image.strip()

    website_name = product_url.replace("https://", "").replace("www.", "").split("/")[0].replace(".com", "").upper().strip()
    
    product_price = product_data['price']/100

    stocks = ""
    sizes = ""

    # Print restock data even if for price drop
    for data in restock_data['new_variants']:
        if str(data[ 'stock']).lower() == "quantity unknown" and not(data['available']):
            stocks += "*~OUT OF STOCK~*" + "\n"
        elif str(data['stock']).lower() == "quantity unknown" and data['available']:
            stocks += "_Quantity Unknown_" + "\n"
        else:
            stocks += str(data['stock']) + "\n"
    
        sizes = '\n'.join([f"<{i['atc_url'].strip()}|{str(i['size'])}>" for i in restock_data['new_variants']])


    slack_msg = {
        "username": USERNAME,
        "icon_emoji": "money_with_wings",
        "channel": CHANNEL,
        "attachments":[{
            "color": COLOR,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*<{product_url.strip()} | PRICE DROP: {restock_data['title']} | {website_name} | ${old_price/100} → ${product_price}>*",
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"""*Total Stock:*\n{stocks}"""
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Size/Stock Level:*\n{sizes}"
                        }
                    ]
                },
            ]
        }
        ]
    }

    if image:
        slack_msg['attachments'][0]['blocks'][0]["accessory"] = {
                        "type": "image",
                        "image_url": image,
                        "alt_text": restock_data['title']
                    }

    if len(stocks) > 0:
        result = rq.post(WEBHOOK, data=json.dumps(slack_msg))

def slack_webhook_new_product(product_url:str):
    product_data = get_info_by_url(product_url)
    product_url = product_url.split("?")[0]
    restock_data = variant_finder(product_url, product_data)
    print(restock_data)
    
    image = f"https://" + product_data['image'][2:]
    image = image.strip()

    website_name = product_url.replace("https://", "").replace("www.", "").split("/")[0].replace(".com", "").upper().strip()
    
    product_price = product_data['price']/100

    stocks = ""
    sizes = ""

    # Print restock data even if for price drop
    for data in restock_data['new_variants']:
        if str(data[ 'stock']).lower() == "quantity unknown" and not(data['available']):
            stocks += "*~OUT OF STOCK~*" + "\n"
        elif str(data['stock']).lower() == "quantity unknown" and data['available']:
            stocks += "_Quantity Unknown_" + "\n"
        else:
            stocks += str(data['stock']) + "\n"
    
        sizes = '\n'.join([f"<{i['atc_url'].strip()}|{str(i['size'])}>" for i in restock_data['new_variants']])


    slack_msg = {
        "username": USERNAME,
        "icon_emoji": "money_with_wings",
        "channel": CHANNEL,
        "attachments":[{
            "color": COLOR,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*<{product_url.strip()} | NEW PRODUCT: {restock_data['title']} | {website_name} | ${product_price}>*",
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"""*Total Stock:*\n{stocks}"""
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Size/Stock Level:*\n{sizes}"
                        }
                    ]
                },
            ]
        }
        ]
    }

    if image:
        slack_msg['attachments'][0]['blocks'][0]["accessory"] = {
                        "type": "image",
                        "image_url": image,
                        "alt_text": restock_data['title']
                    }

    if len(stocks) > 0:
        result = rq.post(WEBHOOK, data=json.dumps(slack_msg))

def get_random_proxy():
    pass

def get_info_by_url(product_url:str) -> dict:
    s = rq.Session()
    finding_product = True
    product_item = dict()
    failed = False
    while finding_product:
        html = None
        # Gather proxy from database
        proxies = get_all_proxies()
        while True:
            if len(proxies) == 0:
                failed = True
            proxy = random.choice(proxies)
            try:
                html = s.get(product_url.split("?")[0]+'.js', headers=HEADERS, proxies=proxy,verify=False, timeout=TIMEOUT)
                if proxy[1] == "unchecked":
                    edit_proxy(proxy, "working")
                break
            except Exception as e:
                edit_proxy(proxy[0], "not working")
                logging.info(proxy[0], "not working")
                proxies.remove(proxy)
                continue
        if failed:
            logging.info("No more usable proxies")
            break

        if html.text:
            product = json.loads(html.text)

            product_item = {
                'id': product['id'],
                'title': product['title'],
                'handle': product['handle'],
                'vendor': product['vendor'],
                'type': product['type'],
                'tags': product['tags'],
                'price': product['price'],
                'variants': product['variants']
            }
            try:
                product_item['image'] = product['images'][0]
            except:
                product_item['image'] = None
        break
        
    return product_item

def get_all_products_data(url:str) -> list:
    items = []
    s = rq.Session()
    page = 1
    failed = False
    final_url = "https://" + url.replace("https://", "").split("/")[0]+"/products.json"

    while True:
        html = None
        # Gather proxy from database
        proxies = get_all_proxies()
        while True:
            if len(proxies) == 0:
                failed = True
            proxy = random.choice(proxies)
            try:
                html = s.get(final_url + f'?page={page}&limit=250', proxies=proxy, headers=HEADERS, verify=False, timeout=20)
                if proxy[1] == "unchecked":
                    edit_proxy(proxy, "working")
                break
            except Exception as e:
                edit_proxy(proxy[0], "not working")
                logging.info(proxy[0], "not working")
                proxies.remove(proxy)
                continue
        
        if failed:
            logging.info("No more usable proxy")
            break
        
        output = json.loads(html.text)['products']
        if output == []:
            break
        else:
            # Stores particular details in array
            for product in output:
                product_item = {
                    'id': product['id'],
                    'title': product['title'],
                    'handle': product['handle'],
                    'vendor': product['vendor'],
                    'type': product['product_type'],
                    'tags': product['tags'],
                    'variants': product['variants']
                }
                try:
                    product_item['image'] = product['images'][0]
                except:
                    product_item['image'] = None

                items.append(product_item)
            if page == 3:
                break
            page += 1
    
    s.close()
    return items

# print(data)

# Do all tasks that checks for voucher, new products, product prices, and then voucher
def check_vouchers():
    pass

def compare_keyword_products(old_data, new_data, keywords):
    old_data_titles = []
    new_data_titles = []
    new_products_titles = []
    new_products = []
    filtered_new_products = []
    for row in new_data:
        new_data_titles.append(row['title'])
    for row in old_data:
        old_data_titles.append(row['title'])

    for title in new_data_titles:
        if title not in old_data_titles:
            new_products_titles.append(title)

    for title in new_products_titles:
        for row in new_data:
            if title == row['title']:
                new_products.append(row)
            
    for product in new_products:
        for keyword in keywords:
            if keyword.lower() in product['title'].lower() or keyword in product['tags']:
                filtered_new_products.append(product)
    
    return filtered_new_products
            
 
def check_for_new_products():
    all_sites_data = get_all_keyword_products()
    old_data = list()
    new_data = list()
    new_products_by_keyword = list()
    for url, keywords, data in all_sites_data:
        new_data = get_all_products_data(url.strip())
        old_data = json.loads(data)
        print(f"Done gathering data from: {url}")

        # Get difference from two data]
        new_products_by_keyword = compare_keyword_products(old_data, new_data, keywords.split(","))
        insert_keyword_product(url, keywords, json.dumps(new_data))

        print("Done comparing two data")

        for new_product in new_products_by_keyword:
            # POST IN SLACK
            product_url = ""
            if "https://" in url:
                product_url = url+"/products/"+new_product['handle']
            else:
                product_url = "https://"+url+"/products/"+new_product['handle']
            slack_webhook_new_product(product_url)
        
        old_data = []
        new_data = []
    

def check_product_prices():
    data = get_all_manual_products()
    new_data = list()

    # Get new data from scraping
    for row in data:
        updated_product_data = get_info_by_url(row[1])
        new_data.append(updated_product_data)

        if (update_manual_product(updated_product_data['handle'], json.dumps(updated_product_data))):
            print(f"Updated {updated_product_data['handle']} in Database")
        else:
            print(f"THERE IS NO {updated_product_data['handle']} IN THE MONITOR.")


    # Cross-match those products with new prices
    for row, new_row in zip(data, new_data):
        old_row = json.loads(row[3])
        product_url = row[1]
        # If old row and new row are diferent (!=), post webhook
        if old_row['price']/100 < new_row['price']/100:
            restocks = variants_checker(product_url, old_row, new_row)
            slack_webhook_price_drop(product_url, restocks, old_row['price'])
        

def check_new_variants():
    data = get_all_manual_products()
    new_data = list()
    
    # Get new data from scraping
    for row in data:
        updated_product_data = get_info_by_url(row[1])
        new_data.append(updated_product_data)
        
        if (update_manual_product(updated_product_data['handle'], json.dumps(updated_product_data))):
            print(f"Updated {updated_product_data['handle']} in Database")
        else:
            print(f"THERE IS NO {updated_product_data['handle']} IN THE MONITOR.")


    # Cross-match those products with new attributes
    for row, new_row in zip(data, new_data):
        # FIX SO THAT IT COULD ACKNOWLEDGE OUT OF STOCK VS QUANTITY UNKNOWN
        product_url = row[1]
        old_row = json.loads(row[3])
        restocks = variants_checker(product_url, old_row, new_row)
        #pprint(new_row)
        if len(restocks) > 0:
            slack_webhook_restock(product_url, restocks)

