from monitor_handle import check_new_variants, check_product_prices, check_for_new_products
import logging


## LOGGING SETUP
logging.basicConfig(
    level = logging.INFO,
    format = "[{asctime}] {levelname:<8} | {message}",
    style = "{",
    # filename = "shopify_monitor.txt",
    # filemode = 'a'
)

msg = "Starting Jobs:"
logging.info(msg)
print(msg, flush=True)

msg = "Checking new variants"
logging.info(msg)
print(msg, flush=True)
check_new_variants()
logging.info(f"Done {msg}")
print(f"Done {msg}", flush=True)

msg = "Checking Product Prices"
logging.info(msg)
print(msg, flush=True)
check_product_prices()
logging.info(f"Done {msg}")
print(f"Done {msg}", flush=True)

msg = "Checking keyword based products"
logging.info(msg)
check_for_new_products()
logging.info(f"Done {msg}")
print(f"Done {msg}", flush=True)
