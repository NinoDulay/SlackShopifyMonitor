import sqlite3
from config import DATABASE_FILE

def open_db(db:str=DATABASE_FILE) -> dict:
    conn = sqlite3.connect(db)
    c = conn.cursor()
    return {"conn": conn, "c": c}

def createTable() -> None:
    db = open_db()
    db['c'].execute(
        'CREATE TABLE IF NOT EXISTS manual_product(handle TEXT, product_url TEXT, website TEXT, json_data TEXT)'
    )

    # Should we also monitor new products?
    db['c'].execute(
        'CREATE TABLE IF NOT EXISTS keyword_products(url TEXT, keywords TEXT, last_data TEXT)'
    )

    db['c'].execute(
        'CREATE TABLE IF NOT EXISTS voucher(url TEXT)'
    )

    db['c'].execute(
        'CREATE TABLE IF NOT EXISTS proxies(proxy TEXT, state TEXT)'
    )

    close_db(db)

def check_proxy_if_exists(proxy:str):
    db = open_db()
    c = db['c']

    c.execute('SELECT * FROM proxies WHERE proxy = ?', (proxy, ))
    data = [row for row in c.fetchall()]

    if data:
        close_db(db)
        return True
    
    close_db(db)
    return False


def add_new_proxy(proxy:str) -> bool:
    db = open_db()
    c = db['c']
    conn = db['conn']

    if not(check_proxy_if_exists(proxy)):
        c.execute(
                'INSERT INTO proxies VALUES (?,?)',
                (proxy, "unchecked"))
        conn.commit()
        close_db(db)
        return True
    close_db(db)
    return False

def edit_proxy(proxy:str, new_state:str) -> bool:
    db = open_db()
    c = db['c']
    conn = db['conn']

    if check_proxy_if_exists(proxy):
        c.execute(
                'UPDATE proxies SET state = (?) WHERE proxy = (?)',
                (new_state, proxy))
        conn.commit()
        close_db(db)
        return True
    close_db(db)
    return False

def get_all_proxies() -> list:
    db = open_db()
    c = db['c']

    c.execute(
            'SELECT * FROM proxies WHERE state = (?) OR state = (?)', ('unchecked', 'working'))
    close_db(db)
    return True


def clear_proxies() -> bool:
    db = open_db()
    c = db['c']
    conn = db['conn']

    c.execute('DELETE FROM proxies')

    conn.commit() 
    close_db(db)
    
    return True



def get_all_manual_products() -> list:
    db = open_db()
    c = db['c']

    c.execute('SELECT * FROM manual_product')
    data = [row for row in c.fetchall()]

    if len(data) == 0:
        close_db(db)
        return False
    else:
        close_db(db)
        return data

def read_manual_product(handle:str):
    db = open_db()
    c = db['c']

    c.execute('SELECT * FROM manual_product WHERE handle=(?)', (handle,))
    
    row_count = 0
    data = None
    for row in c.fetchall():
        data = row
        row_count += 1
    
    if row_count == 0:
        close_db(db)
        return False
    else:
        close_db(db)
        return data

def get_all_monitored_products():
    db = open_db()
    c = db['c']

    c.execute('SELECT * FROM manual_product')
    data = [[row[0], row[1], row[2], row[3]] for row in c.fetchall()]

    close_db(db)

    return data
    

def insert_manual_product(handle:str, product_url:str, website:str, json_data:str) -> bool: 
    db = open_db()
    c = db['c']
    conn = db['conn']
    
    if read_manual_product(handle) == False:
        c.execute(
            'INSERT INTO manual_product VALUES(?,?,?,?)',
            (handle,
            product_url.strip(),
            website.strip(),
            json_data))
        conn.commit() 
        close_db(db)
        return True
    else:
        close_db(db)
        return False

def update_manual_product(handle: str, new_json_data: str) -> bool:
    db = open_db()
    c = db['c']
    conn = db['conn']

    if read_manual_product(handle) != False:
        c.execute('UPDATE manual_product SET json_data = (?) WHERE handle = (?)', (new_json_data, handle)) 
        conn.commit()
        close_db(db)
        return True
    else:
        close_db(db)
        return False

def remove_manual_product(handle:str) -> None:
    db = open_db()
    c = db['c']
    conn = db['conn']

    if read_manual_product(handle) == False:
        return False
    c.execute('DELETE FROM manual_product WHERE handle=(?)', (handle,))

    conn.commit() 
    close_db(db)
    
    return True

def get_all_keyword_products():
    db = open_db()
    c = db['c']

    c.execute('SELECT * FROM keyword_products')
    data = [[row[0], row[1], row[2]] for row in c.fetchall()]

    close_db(db)

    return data

def read_keyword_product(url:str):
    db = open_db()
    c = db['c']

    c.execute('SELECT * FROM keyword_products WHERE url=(?)', (url,))
    
    row_count = 0
    data = None
    for row in c.fetchall():
        data = row
        row_count += 1
    if row_count == 0:
        close_db(db)
        return False
    else:
        close_db(db)
        return data


def insert_keyword_product(url:str, keywords:str, last_data:str): 
    db = open_db()
    c = db['c']
    conn = db['conn']

    print("Saving to the database.")
    c.execute(
        'INSERT INTO keyword_products VALUES(?,?,?)',
        (url.strip(),
        keywords,
        last_data)
    )
    conn.commit() 
    close_db(db)
    print("Done saving to the database.")
    return True

def update_keyword_product(url:str, new_keywords:str) -> None: 
    db = open_db()
    c = db['c']
    conn = db['conn']

    
    c.execute(
        'UPDATE keyword_products SET keywords=? WHERE url=?',
        (new_keywords,
         url.strip()))

    conn.commit() 
    close_db(db)

def update_keyword_product_data(url:str, new_data:str) -> None:
    db = open_db()
    c = db['c']
    conn = db['conn']
    c.execute(
        'UPDATE keyword_products SET last_data=? WHERE url=?',
        (new_data,
         url.strip()))

    conn.commit() 
    close_db(db)

def remove_keyword_product(url:str) -> bool:
    db = open_db()
    c = db['c']
    conn = db['conn']

    if read_keyword_product(url) == False:
        return False
    
    print("DELETING THE PRODUCT")

    c.execute('DELETE FROM keyword_products WHERE url=(?)', (url,))

    conn.commit() 
    close_db(db)
    return True

def close_db(db: dict) -> None:
    db['c'].close()
    db['conn'].close()

createTable()
    