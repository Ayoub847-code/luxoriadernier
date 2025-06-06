import discord
from discord.ext import commands
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import View, Button
import json
import asyncio
import os
from dotenv import load_dotenv
from keep_alive import keep_alive

keep_alive()  # Ça lance un petit serveur web qui maintient le bot actif


load_dotenv()  # charge les variables d'environnement depuis .env

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Chargement / sauvegarde de la base de données (produits, commandes, packs, abonnements, logs) ---
DB_FILE = "database.json"

def load_db():
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "products": {},
            "commands": {},
            "packs": {},
            "subscriptions": {},
            "logs": []
        }

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)

db = load_db()

# --- Salon commandes automatique création au démarrage ---
@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")
    for guild in bot.guilds:
        existing_channel = discord.utils.get(guild.text_channels, name="commandes")
        if not existing_channel:
            await guild.create_text_channel("commandes")
    try:
        synced = await bot.tree.sync()
        print(f"Commandes slash synchronisées ({len(synced)})")
    except Exception as e:
        print(f"Erreur sync commandes: {e}")

# --- Vérifier permissions admin simplifié ---
def is_admin(interaction: Interaction):
    return interaction.user.guild_permissions.administrator

# --- View Boutique avec pagination + boutons Acheter ---
class BoutiqueView(View):
    def __init__(self, products, interaction: Interaction):
        super().__init__(timeout=180)
        self.products = list(products.values())
        self.index = 0
        self.interaction = interaction
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        # Bouton précédent
        self.add_item(Button(label="⬅️ Précédent", style=ButtonStyle.secondary, disabled=self.index == 0, custom_id="prev"))
        # Bouton acheter
        self.add_item(Button(label="🛒 Acheter", style=ButtonStyle.green, custom_id="buy"))
        # Bouton suivant
        self.add_item(Button(label="➡️ Suivant", style=ButtonStyle.secondary, disabled=self.index >= len(self.products) -1, custom_id="next"))

    def current_product_embed(self):
        p = self.products[self.index]
        embed = discord.Embed(title=p["name"], description=p["description"], color=discord.Color.blue())
        embed.add_field(name="Prix", value=f"{p['price']} €", inline=True)
        embed.add_field(name="Stock", value=p["stock"], inline=True)
        embed.set_footer(text=f"Produit {self.index + 1} / {len(self.products)}")
        return embed

    @discord.ui.button(label="Précédent", style=ButtonStyle.secondary, custom_id="prev")
    async def previous(self, interaction: Interaction, button: Button):
        if self.index > 0:
            self.index -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.current_product_embed(), view=self)

    @discord.ui.button(label="Acheter", style=ButtonStyle.green, custom_id="buy")
    async def buy(self, interaction: Interaction, button: Button):
        # Envoyer un message dans le salon commandes
        channel = discord.utils.get(interaction.guild.text_channels, name="commandes")
        if not channel:
            await interaction.response.send_message("Salon `commandes` introuvable.", ephemeral=True)
            return
        product = self.products[self.index]
        # Créer la commande dans la DB
        user_id = str(interaction.user.id)
        commande_id = str(len(db["commands"]) + 1)
        db["commands"][commande_id] = {
            "user": user_id,
            "product": product["name"],
            "status": "En attente"
        }
        save_db(db)
        # Envoyer message dans commandes
        await channel.send(f"Nouvelle commande #{commande_id} de {interaction.user.mention} : **{product['name']}**")
        await interaction.response.send_message(f"Commande pour **{product['name']}** envoyée avec succès !", ephemeral=True)

    @discord.ui.button(label="Suivant", style=ButtonStyle.secondary, custom_id="next")
    async def next(self, interaction: Interaction, button: Button):
        if self.index < len(self.products) - 1:
            self.index += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.current_product_embed(), view=self)

# --- Commandes slash ---

# 1. Boutique
@bot.tree.command(name="boutique", description="Afficher la boutique avec les produits")
async def boutique(interaction: Interaction):
    if not db["products"]:
        await interaction.response.send_message("La boutique est vide.", ephemeral=True)
        return
    view = BoutiqueView(db["products"], interaction)
    embed = view.current_product_embed()
    await interaction.response.send_message(embed=embed, view=view)

# 2. Ajouter un produit (admin only)
@bot.tree.command(name="addproduct", description="Ajouter un produit à la boutique (admin seulement)")
@app_commands.describe(name="Nom du produit", price="Prix en €", stock="Quantité en stock", description="Description du produit")
async def addproduct(interaction: Interaction, name: str, price: float, stock: int, description: str):
    if not is_admin(interaction):
        await interaction.response.send_message("Tu n'as pas la permission d'utiliser cette commande.", ephemeral=True)
        return
    if name in db["products"]:
        await interaction.response.send_message("Ce produit existe déjà.", ephemeral=True)
        return
    db["products"][name] = {
        "name": name,
        "price": price,
        "stock": stock,
        "description": description
    }
    save_db(db)
    await interaction.response.send_message(f"Produit **{name}** ajouté à la boutique.", ephemeral=True)

# 3. Supprimer un produit (admin only)
@bot.tree.command(name="deleteproduct", description="Supprimer un produit de la boutique (admin seulement)")
@app_commands.describe(name="Nom du produit à supprimer")
async def deleteproduct(interaction: Interaction, name: str):
    if not is_admin(interaction):
        await interaction.response.send_message("Tu n'as pas la permission d'utiliser cette commande.", ephemeral=True)
        return
    if name not in db["products"]:
        await interaction.response.send_message("Produit non trouvé.", ephemeral=True)
        return
    del db["products"][name]
    save_db(db)
    await interaction.response.send_message(f"Produit **{name}** supprimé de la boutique.", ephemeral=True)

# 4. Service client (IA simulée)
@bot.tree.command(name="serviceclient", description="Pose une question au service client IA")
@app_commands.describe(question="Ta question")
async def serviceclient(interaction: Interaction, question: str):
    # Ici on simule une réponse IA (tu peux intégrer une vraie API IA)
    reponse = f"Réponse automatique à ta question : {question}\nDésolé, le service IA n'est pas encore implémenté."
    await interaction.response.send_message(reponse, ephemeral=True)


# --------- Autres commandes à rajouter ici -----------

# Exemple modération: /ban
@bot.tree.command(name="ban", description="Bannir un membre")
@app_commands.describe(user="Utilisateur à bannir", raison="Raison du ban")
async def ban(interaction: Interaction, user: discord.Member, raison: str = "Aucune raison spécifiée"):
    if not is_admin(interaction):
        await interaction.response.send_message("Tu n'as pas la permission.", ephemeral=True)
        return
    try:
        await user.ban(reason=raison)
        await interaction.response.send_message(f"{user} a été banni pour : {raison}")
    except Exception as e:
        await interaction.response.send_message(f"Erreur lors du ban : {e}", ephemeral=True)

# /kick
@bot.tree.command(name="kick", description="Expulser un membre")
@app_commands.describe(user="Utilisateur à expulser", raison="Raison de l'expulsion")
async def kick(interaction: Interaction, user: discord.Member, raison: str = "Aucune raison spécifiée"):
    if not is_admin(interaction):
        await interaction.response.send_message("Tu n'as pas la permission.", ephemeral=True)
        return
    try:
        await user.kick(reason=raison)
        await interaction.response.send_message(f"{user} a été expulsé pour : {raison}")
    except Exception as e:
        await interaction.response.send_message(f"Erreur lors de l'expulsion : {e}", ephemeral=True)

# /clear
@bot.tree.command(name="clear", description="Supprimer des messages")
@app_commands.describe(amount="Nombre de messages à supprimer")
async def clear(interaction: Interaction, amount: int):
    if not is_admin(interaction):
        await interaction.response.send_message("Tu n'as pas la permission.", ephemeral=True)
        return
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"{len(deleted)} messages supprimés.", ephemeral=True)

# /cadis - voir ses commandes
@bot.tree.command(name="cadis", description="Voir tes commandes")
async def cadis(interaction: Interaction):
    user_id = str(interaction.user.id)
    user_cmds = [cmd for cmd in db["commands"].values() if cmd["user"] == user_id]
    if not user_cmds:
        await interaction.response.send_message("Tu n'as aucune commande.", ephemeral=True)
        return
    desc = "\n".join(f"- {c['product']} : {c['status']}" for c in user_cmds)
    embed = discord.Embed(title="Tes commandes", description=desc, color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)

# /cmdencours (admin voir commandes en cours)
@bot.tree.command(name="cmdencours", description="Voir commandes en cours (admin)")
async def cmdencours(interaction: Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("Tu n'as pas la permission.", ephemeral=True)
        return
    cmds = [f"#{cid} : {c['product']} ({c['status']})" for cid,c in db["commands"].items() if c["status"] == "En attente"]
    if not cmds:
        await interaction.response.send_message("Aucune commande en cours.", ephemeral=True)
        return
    await interaction.response.send_message("\n".join(cmds), ephemeral=True)

# /cmdlivrer - enlever commande livrée
@bot.tree.command(name="cmdlivrer", description="Marquer une commande comme livrée (admin)")
@app_commands.describe(commande_id="ID de la commande livrée")
async def cmdlivrer(interaction: Interaction, commande_id: str):
    if not is_admin(interaction):
        await interaction.response.send_message("Tu n'as pas la permission.", ephemeral=True)
        return
    if commande_id not in db["commands"]:
        await interaction.response.send_message("Commande non trouvée.", ephemeral=True)
        return
    db["commands"][commande_id]["status"] = "Livrée"
    save_db(db)
    await interaction.response.send_message(f"Commande #{commande_id} marquée comme livrée.", ephemeral=True)

# /suprcmd - supprimer commande (admin)
@bot.tree.command(name="suprcmd", description="Supprimer une commande (admin)")
@app_commands.describe(commande_id="ID de la commande")
async def suprcmd(interaction: Interaction, commande_id: str):
    if not is_admin(interaction):
        await interaction.response.send_message("Tu n'as pas la permission.", ephemeral=True)
        return
    if commande_id not in db["commands"]:
        await interaction.response.send_message("Commande non trouvée.", ephemeral=True)
        return
    del db["commands"][commande_id]
    save_db(db)
    await interaction.response.send_message(f"Commande #{commande_id} supprimée.", ephemeral=True)

# /annulercmd - supprimer sa propre commande
@bot.tree.command(name="annulercmd", description="Annuler ta commande")
@app_commands.describe(commande_id="ID de ta commande")
async def annulercmd(interaction: Interaction, commande_id: str):
    user_id = str(interaction.user.id)
    if commande_id not in db["commands"]:
        await interaction.response.send_message("Commande non trouvée.", ephemeral=True)
        return
    if db["commands"][commande_id]["user"] != user_id:
        await interaction.response.send_message("Ce n'est pas ta commande.", ephemeral=True)
        return
    del db["commands"][commande_id]
    save_db(db)
    await interaction.response.send_message(f"Commande #{commande_id} annulée.", ephemeral=True)

# /addcmd - ajouter commande manuellement (admin)
@bot.tree.command(name="addcmd", description="Ajouter une commande manuellement (admin)")
@app_commands.describe(user="Utilisateur", product="Produit")
async def addcmd(interaction: Interaction, user: discord.User, product: str):
    if not is_admin(interaction):
        await interaction.response.send_message("Tu n'as pas la permission.", ephemeral=True)
        return
    if product not in db["products"]:
        await interaction.response.send_message("Produit non trouvé.", ephemeral=True)
        return
    commande_id = str(len(db["commands"]) + 1)
    db["commands"][commande_id] = {
        "user": str(user.id),
        "product": product,
        "status": "En attente"
    }
    save_db(db)
    await interaction.response.send_message(f"Commande manuelle #{commande_id} ajoutée pour {user.mention}.", ephemeral=True)

# /prix <produit>
@bot.tree.command(name="prix", description="Afficher le prix d'un produit")
@app_commands.describe(name="Nom du produit")
async def prix(interaction: Interaction, name: str):
    if name not in db["products"]:
        await interaction.response.send_message("Produit non trouvé.", ephemeral=True)
        return
    p = db["products"][name]
    await interaction.response.send_message(f"Prix de **{name}** : {p['price']} €", ephemeral=True)

# /pack - montrer les packs en vente
@bot.tree.command(name="pack", description="Afficher les packs en vente")
async def pack(interaction: Interaction):
    if not db["packs"]:
        await interaction.response.send_message("Aucun pack disponible.", ephemeral=True)
        return
    desc = "\n".join(f"- {name}: {info['description']} - {info['price']} €" for name, info in db["packs"].items())
    embed = discord.Embed(title="Packs en vente", description=desc, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

# /addpacks - ajouter un pack (admin)
@bot.tree.command(name="addpacks", description="Ajouter un pack (admin)")
@app_commands.describe(name="Nom du pack", price="Prix en €", description="Description du pack")
async def addpacks(interaction: Interaction, name: str, price: float, description: str):
    if not is_admin(interaction):
        await interaction.response.send_message("Tu n'as pas la permission.", ephemeral=True)
        return
    db["packs"][name] = {
        "price": price,
        "description": description
    }
    save_db(db)
    await interaction.response.send_message(f"Pack **{name}** ajouté.", ephemeral=True)

# /acheter <produit> - crée ticket d'achat
@bot.tree.command(name="acheter", description="Acheter un produit")
@app_commands.describe(name="Nom du produit")
async def acheter(interaction: Interaction, name: str):
    if name not in db["products"]:
        await interaction.response.send_message("Produit non trouvé.", ephemeral=True)
        return
    product = db["products"][name]
    channel = discord.utils.get(interaction.guild.text_channels, name="commandes")
    if not channel:
        await interaction.response.send_message("Salon `commandes` introuvable.", ephemeral=True)
        return
    commande_id = str(len(db["commands"]) + 1)
    db["commands"][commande_id] = {
        "user": str(interaction.user.id),
        "product": name,
        "status": "En attente"
    }
    save_db(db)
    await channel.send(f"Nouvelle commande #{commande_id} de {interaction.user.mention} : **{name}**")
    await interaction.response.send_message(f"Commande pour **{name}** enregistrée.", ephemeral=True)

# /suivi - montre état commande
@bot.tree.command(name="suivi", description="Voir l'état de ta commande")
async def suivi(interaction: Interaction):
    user_id = str(interaction.user.id)
    user_cmds = [c for c in db["commands"].values() if c["user"] == user_id]
    if not user_cmds:
        await interaction.response.send_message("Tu n'as aucune commande en cours.", ephemeral=True)
        return
    desc = "\n".join(f"- {c['product']} : {c['status']}" for c in user_cmds)
    await interaction.response.send_message(f"Voici tes commandes :\n{desc}", ephemeral=True)

# /abonnement - infos abonnement
@bot.tree.command(name="abonnement", description="Afficher infos abonnement")
async def abonnement(interaction: Interaction):
    user_id = str(interaction.user.id)
    sub = db["subscriptions"].get(user_id)
    if not sub:
        await interaction.response.send_message("Tu n'as pas d'abonnement actif.", ephemeral=True)
        return
    embed = discord.Embed(title="Ton abonnement", color=discord.Color.purple())
    embed.add_field(name="Type", value=sub["type"])
    embed.add_field(name="Durée", value=sub["duration"])
    embed.add_field(name="Fin", value=sub["end_date"])
    await interaction.response.send_message(embed=embed, ephemeral=True)

# /monprofil - affichage profil utilisateur
@bot.tree.command(name="monprofil", description="Afficher ton profil VIP et commandes")
async def monprofil(interaction: Interaction):
    user_id = str(interaction.user.id)
    # Exemple simple
    embed = discord.Embed(title=f"Profil de {interaction.user.name}", color=discord.Color.teal())
    embed.add_field(name="Rôles VIP", value="VIP, Nitro (exemple)", inline=False)
    cmds = [c for c in db["commands"].values() if c["user"] == user_id]
    embed.add_field(name="Nombre de commandes", value=str(len(cmds)))
    await interaction.response.send_message(embed=embed, ephemeral=True)

# /vip - infos VIP
@bot.tree.command(name="vip", description="Informations VIP")
async def vip(interaction: Interaction):
    embed = discord.Embed(title="Informations VIP", description="Avantages VIP et offres", color=discord.Color.gold())
    embed.add_field(name="Support dédié", value="Oui")
    embed.add_field(name="Accès exclusif", value="Oui")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# /logs - voir logs
@bot.tree.command(name="logs", description="Voir les logs (admin)")
async def logs(interaction: Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("Tu n'as pas la permission.", ephemeral=True)
        return
    if not db["logs"]:
        await interaction.response.send_message("Pas de logs disponibles.", ephemeral=True)
        return
    await interaction.response.send_message("\n".join(db["logs"][-10:]), ephemeral=True)

# Ajoute un log simple dans la DB (exemple)
def add_log(entry: str):
    db["logs"].append(entry)
    if len(db["logs"]) > 100:
        db["logs"].pop(0)
    save_db(db)

# --- Run Bot ---
bot.run(TOKEN)
