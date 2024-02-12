import os
import json

from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, Response
from flask_apscheduler import APScheduler

import slack_sdk
from slackeventsapi import SlackEventAdapter

from monitor_handle import get_info_by_url, get_all_products_data, check_new_variants, check_product_prices, check_for_new_products
from database_handle import insert_manual_product, get_all_monitored_products, remove_manual_product, insert_keyword_product, read_keyword_product, get_all_keyword_products, remove_keyword_product, update_keyword_product, add_new_proxy
'''
NOTES:
RUN WITH NGROK
CHANGE SLASHCOMMANDS LINK
CHANGE EVENT SUBSCRIPTIONS LINK
ALWAYS CHECK OAUTH AND PERMISSIONS
'''

# ngrok http --domain=brightly-open-possum.ngrok-free.app 5000

# Load the .env variable file
env_path = Path(".") / '.env'
load_dotenv(dotenv_path=env_path)

# Setup a flask app for slackeventsapi
app = Flask(__name__)
scheduler = APScheduler()

# Add a slack event adapter that will allow us to handle different events that are sent from slack api
# Create an endpoint for the handling of events
slack_event_adapter = SlackEventAdapter(
    os.environ['G_SIGNING_SECRET'],'/slack/events', app
)

disable_unfurling = {"unfurl_links":False, "unfurl_media": False}

# Create a slack webclient
client = slack_sdk.WebClient(token=os.environ["G_SLACK_TOKEN"])
BOT_ID = client.api_call("auth.test")['user_id']

# View Monitored Products
@app.route('/view-monitored-products', methods=['POST'])
def view_monitored_products():
    data = request.form
    channel_id = data.get('channel_id')
    ack_payload = {"text": "Viewing products that are monitored..."}
    client.chat_postMessage(channel=channel_id, **ack_payload)
    
    monitored_products = get_all_monitored_products(client)
    display_data = ""
    for handle, url, website, data in monitored_products:
        data = f"<{url.strip()}|{handle.replace('-',' ').title().strip()}>\n"
        display_data += data

    if len(monitored_products) > 0:
        client.chat_postMessage(channel=channel_id, mrkdwn=True,text=f"*Monitored Products*:\n{display_data}", **disable_unfurling)
    else:
        client.chat_postMessage(channel=channel_id, mrkdwn=True,text=f"*Monitored Products: None*", **disable_unfurling)

    return Response(), 200

# Delete monitored product
@app.route('/delete-product', methods=['POST'])
def delete_product():
    data = request.form
    urls = data.get("text").strip().split(",")
    channel_id = data.get('channel_id')
    ack_payload = {"text": "Deleting product/s that are supplied..."}
    client.chat_postMessage(channel=channel_id, **ack_payload)
    
    deleted = []
    if len(urls) > 0 and urls[0] != '':
        for url in urls:
            if "https://" in url or ".com" in url:
                data = url[7:].split("/")[1:]
                product_handle = data[-1].split("?")[0]
            else:
                product_handle = url.replace(" ", "-").lower().strip()
            if (remove_manual_product(product_handle.strip())):
                deleted.append(product_handle.replace(" ", "-").title().strip())
            else:
                client.chat_postMessage(channel=channel_id,mrkdwn=True, text="*Product is not on the monitor's database*")
        
        if len(deleted) > 0:
            deleted_products = '\n'.join(deleted)
            client.chat_postMessage(channel=channel_id,mrkdwn=True, text=f"*Deleted Product/s:*\n{deleted_products}", **disable_unfurling)
        else:
            client.chat_postMessage(channel=channel_id,mrkdwn=True, text=f"*Deleted Product/s: None*")
    else:
        client.chat_postMessage(channel=channel_id,mrkdwn=True, text=f"*You did not pass any product to delete.*")

    return Response(), 200

# Add a product to monitor
@app.route('/add-monitored-product', methods=['POST'])
def add_monitored_product():
    data = request.form
    urls = data.get('text').strip().split(",")
    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    response_url = data.get("response_url")
    
    ack_payload = {"text": "Adding products to monitor..."}
    client.chat_postMessage(channel=channel_id, **ack_payload)

    done_url = []
    if len(urls) > 0:
        for url in urls:
            if ("https://" in url) or (".com" in url):
                product_url = url
                data = url[7:].split("/")[1:]
                final_url = "https://"
                product_handle = data[-1]
                for point in data:
                    if "products" in data:
                        if point != "products":
                            final_url += point + "/"
                        elif point == "products":
                            final_url += point + ".json"
                            break
                    else:
                        final_url += point + "/products.json"
                        break
                if "?" in product_handle:
                    product_handle = product_handle.split("?")[0]
                
                product_info = get_info_by_url(product_url)

                if "handle" not in product_info:
                    client.chat_postMessage(channel=channel_id, text=f"The provided URL is not a valid shopify site")
                    return Response(), 200

                data = [product_handle.strip(), product_url.strip(), final_url.strip(), json.dumps(product_info)]
                
                
                if (insert_manual_product(data[0], data[1], data[2], data[3])):
                    done_url.append(f'<{data[1]}|{product_handle.replace("-", " ").title()}>')
                else:
                    client.chat_postMessage(channel=channel_id, text=f"The provided URL is already in the monitored products.")
            else:
                client.chat_postMessage(channel=channel_id, text=f"Not a valid URL, please try again")
            
        if len(done_url) > 0:
            done_urls = '\n'.join(done_url)
            client.chat_postMessage(channel=channel_id, text=f"Added the following products to be monitored:\n{done_urls}", **disable_unfurling)

    return Response(), 200

@app.route('/add-url-keywords', methods=['POST'])
def add_url_keywords():
    # Get info from user (POST method)
    data = request.form
    text = data.get('text').split(",")
    channel_id = data.get('channel_id')
    website = text[0].strip()
    keywords = ','.join(map(lambda x: x.strip(),text[1:]))
    ack_payload = {'mrkdwn': True, "text": f"Adding new products monitor with the following keywords: {keywords}"}
    client.chat_postMessage(channel=channel_id, **ack_payload)
    if read_keyword_product(website) == False:
        ack_payload = {'mrkdwn': True, "text": f"_ps. This might take a few minutes, please wait until you receive a confirmation_\n_ps. You might see an 'operation_timeout' error but please disregard it_"}
        client.chat_postMessage(channel=channel_id, **ack_payload)
        try:
            products_data = get_all_products_data(website)
        except:
            client.chat_postMessage(channel=channel_id, text=f"Website is not valid. Please try again.")
            return Response(), 200
        
        insert_keyword_product(website, keywords, json.dumps(products_data))
        client.chat_postMessage(channel=channel_id, text=f"Gathered Total Number of Products from {website}: {len(products_data)}\nWebsite Saved to Monitor!")
    else:
        ack_payload = {'mrkdwn': True, "text": f"*Website is already on the monitor*"}
        client.chat_postMessage(channel=channel_id, **ack_payload)

    return Response(), 200

@app.route('/view-keywords-websites', methods=['POST'])
def view_keyword_websites():
    data = request.form
    channel_id = data.get('channel_id')
    ack_payload = {"text": "Viewing sites that are monitored..."}
    client.chat_postMessage(channel=channel_id, **ack_payload)

    monitored_products = get_all_keyword_products()
    display_data = ""
    for url, keyword, data in monitored_products:
        if "https://" not in url:
            url = f"https://{url}"
            
        data = f"SITE: <{url.strip()}|{url.replace('https://', ''). strip()}> | KEYWORDS: {keyword}\n"
        display_data += data

    if len(monitored_products) > 0:
        client.chat_postMessage(channel=channel_id, mrkdwn=True,text=f"*Monitored Sites by Keywords*:\n{display_data}", **disable_unfurling)
    else:
        client.chat_postMessage(channel=channel_id, mrkdwn=True,text=f"*Monitored Sites by Keywords: None*", **disable_unfurling)

    return Response(), 200

@app.route('/edit-keywords-websites', methods=['POST'])
def edit_keyword_websites():
    data = request.form
    text = data.get("text").split(",")
    channel_id = data.get('channel_id')

    website = text[0].strip()
    keywords = ','.join(map(lambda x: x.strip(),text[1:]))

    ack_payload = {"text": "Changing keywords/s from site that is monitored..."}
    client.chat_postMessage(channel=channel_id, **ack_payload)


    if read_keyword_product(website):
        ack_payload = {'mrkdwn': True, "text": f"_ps. This might take a few minutes, please wait until you receive a confirmation_\n_ps. You might see an 'operation_timeout' error but please disregard it_"}
        client.chat_postMessage(channel=channel_id, **ack_payload)

        update_keyword_product(website, keywords)
        client.chat_postMessage(channel=channel_id, text=f"Updated keywords on {website}, New Keywords: {keywords}!")
    else:
        ack_payload = {'mrkdwn': True, "text": f"*Website is not on the monitor*"}
        client.chat_postMessage(channel=channel_id, **ack_payload)

    return Response(), 200

@app.route('/delete-keywords-websites', methods=['POST'])
def delete_keyword_websites():
    data = request.form
    urls = data.get("text").strip().split(",")
    channel_id = data.get('channel_id')
    ack_payload = {"text": "Deleting site/s that are monitored..."}
    client.chat_postMessage(channel=channel_id, **ack_payload)
    
    deleted = []
    if len(urls) > 0 and urls[0] != '':
        for url in urls:
            print(url)
            if (remove_keyword_product(url.strip())):
                deleted.append(url.strip())
            else:
                client.chat_postMessage(channel=channel_id,mrkdwn=True, text=f"*Site is not on the monitor's database: {url.strip()}*", **disable_unfurling)
        
        if len(deleted) > 0:
            deleted_products = '\n'.join(deleted)
            client.chat_postMessage(channel=channel_id,mrkdwn=True, text=f"*Deleted Sites/s:*\n{deleted_products}", **disable_unfurling)
        else:
            client.chat_postMessage(channel=channel_id,mrkdwn=True, text=f"*Deleted Product/s: None*")
    else:
        client.chat_postMessage(channel=channel_id,mrkdwn=True, text=f"*You did not pass any product to delete.*")

    return Response(), 200

@app.route('/add-proxy', methods=['POST'])
def add_proxy():
    data = request.form
    urls = data.get("text").strip().split(",")
    proxy_url = urls[-1].strip()
    channel_id = data.get('channel_id')
    ack_payload = {"text": "Adding a new proxy to the database..."}
    client.chat_postMessage(channel=channel_id, **ack_payload)
    
    add_new_proxy(proxy_url)

    ack_payload = {"text": f"Added {proxy_url} to the database..."}
    client.chat_postMessage(channel=channel_id, **ack_payload)

    return Response(), 200

# if __name__ == "__main__":
    # scheduler.add_job(id='Check New Variants', func=check_new_variants, trigger="interval", seconds=600)
    # scheduler.add_job(id='Check Product Prices', func=check_product_prices, trigger="interval", seconds=600)
    # scheduler.add_job(id='Check for New Products', func=check_for_new_products, trigger="interval", seconds=1800)
    # scheduler.start()
    #app.run()






######
# KEYWORD PRODUCT REPEATS (DATABASE ??)
# CANT ASSURE PRICE/AVAILABILITY
# FIX ISSUES ON STOCKS IF SITES ARE NOT ACCESSIBLE