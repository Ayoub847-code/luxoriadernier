import json
import threading

lock = threading.Lock()

DATABASE_PATH = "database.json"

def load_db():
    with lock:
        try:
            with open(DATABASE_PATH, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "products": {},
                "orders": {},
                "packs": {},
                "subscriptions": {},
                "users": {},
                "logs": []
            }

def save_db(db):
    with lock:
        with open(DATABASE_PATH, "w") as f:
            json.dump(db, f, indent=4)

def add_product(name, description, price, stock):
    db = load_db()
    db["products"][name] = {
        "description": description,
        "price": price,
        "stock": stock
    }
    save_db(db)

def delete_product(name):
    db = load_db()
    if name in db["products"]:
        del db["products"][name]
        save_db(db)
        return True
    return False

def get_product(name):
    db = load_db()
    return db["products"].get(name)

# Ajoute ici d’autres fonctions (orders, packs, abonnements, etc.) similaires.

