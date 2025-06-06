import json
import os

class Database:
    def __init__(self):
        self.path = "database.json"
        if not os.path.exists(self.path):
            with open(self.path, "w") as f:
                json.dump({"products": [], "packs": []}, f)

    def load(self):
        with open(self.path, "r") as f:
            return json.load(f)

    def save(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f, indent=4)

    def add_product(self, product):
        data = self.load()
        data["products"].append(product)
        self.save(data)

    def remove_product(self, name):
        data = self.load()
        data["products"] = [p for p in data["products"] if p["name"].lower() != name.lower()]
        self.save(data)

    def get_products(self):
        return self.load()["products"]

    def add_pack(self, pack):
        data = self.load()
        data["packs"].append(pack)
        self.save(data)

    def remove_pack(self, name):
        data = self.load()
        data["packs"] = [p for p in data["packs"] if p["name"].lower() != name.lower()]
        self.save(data)

    def get_packs(self):
        return self.load()["packs"]
