import json
import os

class Database:
    def __init__(self, path="database.json"):
        self.path = path
        if not os.path.exists(self.path):
            with open(self.path, "w") as f:
                json.dump({"commands": [], "products": [], "packs": [], "subscriptions": {}}, f)
        with open(self.path, "r") as f:
            self.db = json.load(f)

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.db, f, indent=4)

    def get_commands(self):
        return self.db["commands"]

    def add_command(self, command):
        self.db["commands"].append(command)
        self.save()

    def remove_command(self, user_id, product_name):
        self.db["commands"] = [c for c in self.db["commands"] if not (c["user"] == user_id and c["product"].lower() == product_name.lower())]
        self.save()

    def mark_delivered(self, user_id, product_name):
        for cmd in self.db["commands"]:
            if cmd["user"] == user_id and cmd["product"].lower() == product_name.lower():
                cmd["status"] = "livrée"
                self.save()
                return True
        return False

    def get_products(self):
        return self.db["products"]

    def add_product(self, product):
        self.db["products"].append(product)
        self.save()

    def remove_product(self, product_name):
        self.db["products"] = [p for p in self.db["products"] if p["name"].lower() != product_name.lower()]
        self.save()

    def get_packs(self):
        return self.db["packs"]

    def add_pack(self, pack):
        self.db["packs"].append(pack)
        self.save()

    def remove_pack(self, pack_name):
        self.db["packs"] = [p for p in self.db["packs"] if p["name"].lower() != pack_name.lower()]
        self.save()

    def get_subscription(self, user_id):
        return self.db["subscriptions"].get(str(user_id))

    def set_subscription(self, user_id, sub_type, end_date):
        self.db["subscriptions"][str(user_id)] = {"type": sub_type, "end": end_date}
        self.save()

    def get_all(self):
        return self.db
