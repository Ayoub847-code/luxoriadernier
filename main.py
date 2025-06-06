import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from keep_alive import keep_alive  # ton fichier avec le serveur Flask

keep_alive()

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
TREE = bot.tree

# --- Gestion database (charge et sauvegarde) ---
if not os.path.exists("database.json"):
    with open("database.json", "w") as f:
        json.dump({"commands": [], "products": [], "packs": [], "subscriptions": {}}, f)

def load_db():
    with open("database.json", "r") as f:
        return json.load(f)

def save_db(db):
    with open("database.json", "w") as f:
        json.dump(db, f, indent=4)

db = load_db()

# --- Utilitaires pour gestion boutique / commandes ---

def add_command(user_id, product_name):
    db["commands"].append({"user": user_id, "product": product_name, "status": "en attente"})
    save_db(db)

def remove_command(user_id, product_name):
    db["commands"] = [c for c in db["commands"] if not (c["user"] == user_id and c["product"].lower() == product_name.lower())]
    save_db(db)

def update_command_status(user_id, product_name, status):
    for c in db["commands"]:
        if c["user"] == user_id and c["product"].lower() == product_name.lower():
            c["status"] = status
            save_db(db)
            return True
    return False

def add_product(name, description, stock, price):
    db["products"].append({"name": name, "description": description, "stock": stock, "price": price})
    save_db(db)

def remove_product(name):
    before = len(db["products"])
    db["products"] = [p for p in db["products"] if p["name"].lower() != name.lower()]
    save_db(db)
    return len(db["products"]) < before

def remove_pack(name):
    before = len(db["packs"])
    db["packs"] = [p for p in db["packs"] if p["name"].lower() != name.lower()]
    save_db(db)
    return len(db["packs"]) < before

def get_product(name):
    for p in db["products"]:
        if p["name"].lower() == name.lower():
            return p
    return None

# --- Création du salon commandes au démarrage ---
async def ensure_commandes_channel(guild):
    existing = discord.utils.get(guild.text_channels, name="commandes")
    if existing:
        return existing
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
    }
    channel = await guild.create_text_channel("commandes", overwrites=overwrites)
    return channel

# --- Vue interactive pour la boutique ---
class BoutiqueView(View):
    def __init__(self, interaction, products):
        super().__init__(timeout=180)
        self.products = products
        self.index = 0
        self.interaction = interaction
        self.message = None

    def get_embed(self):
        p = self.products[self.index]
        embed = discord.Embed(title=f"Produit {self.index+1} / {len(self.products)}", color=0x00ffcc)
        embed.add_field(name=p["name"], value=p["description"], inline=False)
        embed.add_field(name="Prix", value=f"{p['price']} €", inline=True)
        embed.add_field(name="Stock", value=str(p["stock"]), inline=True)
        return embed

    async def update_message(self):
        if self.message:
            await self.message.edit(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Précédent", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        self.index = (self.index - 1) % len(self.products)
        await self.update_message()
        await interaction.response.defer()

    @discord.ui.button(label="Acheter", style=discord.ButtonStyle.green)
    async def buy_button(self, interaction: discord.Interaction, button: Button):
        product = self.products[self.index]
        if product["stock"] <= 0:
            await interaction.response.send_message("Désolé, ce produit est en rupture de stock.", ephemeral=True)
            return

        # On décrémente le stock
        product["stock"] -= 1
        save_db(db)

        # Ajout commande
        add_command(interaction.user.id, product["name"])

        # Envoyer message dans channel commandes
        commandes_channel = discord.utils.get(interaction.guild.text_channels, name="commandes")
        if commandes_channel:
            await commandes_channel.send(f"Nouvelle commande de {interaction.user.mention} : **{product['name']}**")

        await interaction.response.send_message(f"Commande pour **{product['name']}** prise en compte. Merci !", ephemeral=True)

    @discord.ui.button(label="Suivant", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        self.index = (self.index + 1) % len(self.products)
        await self.update_message()
        await interaction.response.defer()

# ====================== COMMANDES ======================

@TREE.command(name="boutique", description="Afficher la boutique avec produits et boutons")
async def boutique(interaction: discord.Interaction):
    if not db["products"]:
        await interaction.response.send_message("La boutique est vide.", ephemeral=True)
        return

    view = BoutiqueView(interaction, db["products"])
    embed = view.get_embed()
    message = await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    # On récupère le message pour pouvoir le modifier ensuite
    view.message = await interaction.original_response()

@TREE.command(name="addproduits", description="Ajouter un produit dans la boutique (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def addproduits(interaction: discord.Interaction):
    await interaction.response.send_message("Démarrage de l'ajout de produit. Je vais te poser quelques questions en messages privés.", ephemeral=True)

    def check(m):
        return m.author == interaction.user and isinstance(m.channel, discord.DMChannel)

    try:
        # Nom
        await interaction.user.send("Quel est le nom du produit ?")
        nom = await bot.wait_for("message", check=check, timeout=120)

        # Description
        await interaction.user.send("Donne la description du produit.")
        desc = await bot.wait_for("message", check=check, timeout=120)

        # Stock
        await interaction.user.send("Combien de stock pour ce produit ? (nombre entier)")
        stock_msg = await bot.wait_for("message", check=check, timeout=120)
        stock = int(stock_msg.content)

        # Prix
        await interaction.user.send("Quel est le prix ? (en €)")
        price_msg = await bot.wait_for("message", check=check, timeout=120)
        price = float(price_msg.content)

        add_product(nom.content, desc.content, stock, price)
        await interaction.user.send(f"Produit **{nom.content}** ajouté avec succès !")

    except Exception as e:
        await interaction.user.send(f"Erreur ou délai dépassé : {str(e)}")

@TREE.command(name="suprproduits", description="Supprimer un produit de la boutique (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def suprproduits(interaction: discord.Interaction, produit: str):
    if remove_product(produit):
        await interaction.response.send_message(f"Produit **{produit}** supprimé.")
    else:
        await interaction.response.send_message(f"Produit **{produit}** introuvable.")

@TREE.command(name="suprpack", description="Supprimer un pack (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def suprpack(interaction: discord.Interaction, pack: str):
    if remove_pack(pack):
        await interaction.response.send_message(f"Pack **{pack}** supprimé.")
    else:
        await interaction.response.send_message(f"Pack **{pack}** introuvable.")

# === commandes existantes adaptées (extraits) ===

@TREE.command(name="cadis", description="Voir les produits que vous avez commandés")
async def cadis(interaction: discord.Interaction):
    cmds = [cmd for cmd in db["commands"] if cmd["user"] == interaction.user.id]
    if not cmds:
        await interaction.response.send_message("Aucune commande trouvée.", ephemeral=True)
        return
    embed = discord.Embed(title="🛒 Vos commandes", color=0x00ffcc)
    for cmd in cmds:
        embed.add_field(name=cmd["product"], value=f"Statut : {cmd['status']}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@TREE.command(name="cmdencours", description="Voir les commandes en cours")
@app_commands.checks.has_permissions(administrator=True)
async def cmdencours(interaction: discord.Interaction):
    cmds = [cmd for cmd in db["commands"] if cmd["status"] != "livrée"]
    if not cmds:
        await interaction.response.send_message("Aucune commande en cours.", ephemeral=True)
        return
    embed = discord.Embed(title="📦 Commandes en cours", color=0xffcc00)
    for cmd in cmds:
        embed.add_field(name=cmd["product"], value=f"Par <@{cmd['user']}> - Statut : {cmd['status']}", inline=False)
    await interaction.response.send_message(embed=embed)

@TREE.command(name="cmdlivrer", description="Marquer une commande comme livrée")
@app_commands.checks.has_permissions(administrator=True)
async def cmdlivrer(interaction: discord.Interaction, user: discord.Member, produit: str):
    if update_command_status(user.id, produit, "livrée"):
        await interaction.response.send_message("Commande livrée.")
    else:
        await interaction.response.send_message("Commande introuvable.")

@TREE.command(name="suprcmd", description="Supprimer une commande")
@app_commands.checks.has_permissions(administrator=True)
async def suprcmd(interaction: discord.Interaction, user: discord.Member, produit: str):
    remove_command(user.id, produit)
    await interaction.response.send_message("Commande supprimée.")

@TREE.command(name="annulercmd", description="Annuler votre commande")
async def annulercmd(interaction: discord.Interaction, produit: str):
    remove_command(interaction.user.id, produit)
    await interaction.response.send_message("Commande annulée.", ephemeral=True)

@TREE.command(name="addcmd", description="Ajouter une commande (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def addcmd(interaction: discord.Interaction, user: discord.Member, produit: str):
    add_command(user.id, produit)
    await interaction.response.send_message("Commande ajoutée manuellement.")

@TREE.command(name="prix", description="Voir le prix d’un produit")
async def prix(interaction: discord.Interaction, produit: str):
    p = get_product(produit)
    if p:
        await interaction.response.send_message(f"Le prix de **{produit}** est **{p['price']} €**.", ephemeral=True)
    else:
        await interaction.response.send_message("Produit introuvable.", ephemeral=True)

@TREE.command(name="pack", description="Afficher les packs disponibles")
async def pack(interaction: discord.Interaction):
    if not db["packs"]:
        await interaction.response.send_message("Aucun pack disponible.", ephemeral=True)
        return
    embed = discord.Embed(title="🎁 Packs disponibles", color=0x33cc33)
    for p in db["packs"]:
        embed.add_field(name=p["name"], value=f"{p['price']}€ - {p['description']}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@TREE.command(name="acheter", description="Acheter un produit et créer un ticket")
async def acheter(interaction: discord.Interaction, produit: str):
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    channel = await interaction.guild.create_text_channel(name=f"ticket-{interaction.user.name}", overwrites=overwrites)
    await channel.send(f"<@{interaction.user.id}> a acheté **{produit}**. Merci de patienter.")
    await interaction.response.send_message("Ticket créé.", ephemeral=True)

@TREE.command(name="suivi", description="Voir l’état de votre commande")
async def suivi(interaction: discord.Interaction):
    cmds = [cmd for cmd in db["commands"] if cmd["user"] == interaction.user.id]
    if not cmds:
        await interaction.response.send_message("Aucune commande trouvée.", ephemeral=True)
        return
    embed = discord.Embed(title="Suivi de vos commandes", color=0x0088ff)
    for c in cmds:
        embed.add_field(name=c["product"], value=f"Statut : {c['status']}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- Events ---

@bot.event
async def on_ready():
    print(f"{bot.user} est connecté!")
    for guild in bot.guilds:
        await ensure_commandes_channel(guild)
    await TREE.sync()
    print("Commandes synchronisées.")

bot.run(TOKEN)
