import json

DATABASE_FILE = "database.json"

# Chargement de la base de données
def load_db():
    with open(DATABASE_FILE, "r") as f:
        return json.load(f)

# Sauvegarde de la base de données
def save_db(db):
    with open(DATABASE_FILE, "w") as f:
        json.dump(db, f, indent=4)

# Ajouter une commande
def add_command(user_id, product_name):
    db = load_db()
    db["commands"].append({
        "user": user_id,
        "product": product_name,
        "status": "en attente"
    })
    save_db(db)

# Obtenir les commandes d'un utilisateur
def get_user_commands(user_id):
    db = load_db()
    return [cmd for cmd in db["commands"] if cmd["user"] == user_id]

# Obtenir toutes les commandes en cours
def get_pending_commands():
    db = load_db()
    return [cmd for cmd in db["commands"] if cmd["status"] != "livrée"]

# Marquer une commande comme livrée
def mark_command_delivered(user_id, product_name):
    db = load_db()
    for cmd in db["commands"]:
        if cmd["user"] == user_id and cmd["product"].lower() == product_name.lower():
            cmd["status"] = "livrée"
    save_db(db)

# Supprimer une commande (admin)
def delete_command(user_id, product_name):
    db = load_db()
    db["commands"] = [cmd for cmd in db["commands"] if not (cmd["user"] == user_id and cmd["product"].lower() == product_name.lower())]
    save_db(db)

# Supprimer sa propre commande
def delete_own_command(user_id):
    db = load_db()
    db["commands"] = [cmd for cmd in db["commands"] if cmd["user"] != user_id]
    save_db(db)

# Ajouter un produit
def add_product(name, description, stock, price):
    db = load_db()
    db["products"].append({
        "name": name,
        "description": description,
        "stock": stock,
        "price": price
    })
    save_db(db)

# Supprimer un produit
def delete_product(name):
    db = load_db()
    db["products"] = [p for p in db["products"] if p["name"].lower() != name.lower()]
    save_db(db)

# Ajouter un pack
def add_pack(name, description, price):
    db = load_db()
    db["packs"].append({
        "name": name,
        "description": description,
        "price": price
    })
    save_db(db)

# Supprimer un pack
def delete_pack(name):
    db = load_db()
    db["packs"] = [p for p in db["packs"] if p["name"].lower() != name.lower()]
    save_db(db)

# Ajouter un abonnement
def add_subscription(user_id, sub_type, duration):
    db = load_db()
    db["subscriptions"][str(user_id)] = {
        "type": sub_type,
        "duration": duration
    }
    save_db(db)

# Obtenir un abonnement
def get_subscription(user_id):
    db = load_db()
    return db["subscriptions"].get(str(user_id), None)
