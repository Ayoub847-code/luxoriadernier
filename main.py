import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
from dotenv import load_dotenv
import database  # ton fichier database.py

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
TREE = bot.tree

# ----- Salon commandes (sera créé si inexistant) -----
commandes_channel_name = "commandes"
commandes_channel = None

@bot.event
async def on_ready():
    global commandes_channel
    guild = bot.guilds[0] if bot.guilds else None
    if guild is None:
        print("Le bot n'est dans aucun serveur.")
        return

    # Cherche le channel commandes
    commandes_channel = discord.utils.get(guild.text_channels, name=commandes_channel_name)
    if commandes_channel is None:
        # Création du channel commandes
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False)
        }
        commandes_channel = await guild.create_text_channel(commandes_channel_name, overwrites=overwrites)
        print(f"Salon #{commandes_channel_name} créé.")
    else:
        print(f"Salon #{commandes_channel_name} trouvé.")

    await TREE.sync()
    print(f"{bot.user} est connecté !")

# ------------------ COMMANDES -------------------

# --- Commandes de gestion des commandes ---

@TREE.command(name="cadis", description="Voir les produits que vous avez commandés")
async def cadis(interaction: discord.Interaction):
    cmds = database.get_commands_by_user(interaction.user.id)
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
    cmds = database.get_commands_not_livree()
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
    ok = database.update_command_status(user.id, produit, "livrée")
    if ok:
        await interaction.response.send_message("Commande livrée.")
    else:
        await interaction.response.send_message("Commande introuvable.")

@TREE.command(name="suprcmd", description="Supprimer une commande")
@app_commands.checks.has_permissions(administrator=True)
async def suprcmd(interaction: discord.Interaction, user: discord.Member, produit: str):
    database.remove_command(user.id, produit)
    await interaction.response.send_message("Commande supprimée.")

@TREE.command(name="annulercmd", description="Annuler votre commande")
async def annulercmd(interaction: discord.Interaction, produit: str):
    database.remove_command(interaction.user.id, produit)
    await interaction.response.send_message("Commande annulée.", ephemeral=True)

@TREE.command(name="addcmd", description="Ajouter une commande (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def addcmd(interaction: discord.Interaction, user: discord.Member, produit: str):
    database.add_command(user.id, produit)
    await interaction.response.send_message("Commande ajoutée manuellement.")

# --- Commandes produits ---

@TREE.command(name="prix", description="Voir le prix d’un produit")
async def prix(interaction: discord.Interaction, produit: str):
    p = database.get_product(produit)
    if p:
        await interaction.response.send_message(f"Le prix de **{produit}** est **{p['price']} €**.\nStock : {p['stock']}", ephemeral=True)
    else:
        await interaction.response.send_message("Produit introuvable.", ephemeral=True)

@TREE.command(name="pack", description="Afficher les packs disponibles")
async def pack(interaction: discord.Interaction):
    packs = database.get_all_packs()
    if not packs:
        await interaction.response.send_message("Aucun pack disponible.", ephemeral=True)
        return
    embed = discord.Embed(title="🎁 Packs disponibles", color=0x33cc33)
    for p in packs:
        embed.add_field(name=p["name"], value=f"{p['price']}€ - {p['description']}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@TREE.command(name="addpacks", description="Ajouter un pack (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def addpacks(interaction: discord.Interaction, name: str, price: float, description: str):
    db = database.load_db()
    db["packs"].append({ "name": name, "price": price, "description": description })
    database.save_db(db)
    await interaction.response.send_message("Pack ajouté.")

@TREE.command(name="suprpack", description="Supprimer un pack (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def suprpack(interaction: discord.Interaction, name: str):
    ok = database.remove_pack(name)
    if ok:
        await interaction.response.send_message("Pack supprimé.")
    else:
        await interaction.response.send_message("Pack introuvable.")

# --- Commandes VIP / Abonnements ---

@TREE.command(name="abonnement", description="Voir ton abonnement")
async def abonnement(interaction: discord.Interaction):
    db = database.load_db()
    abo = db["subscriptions"].get(str(interaction.user.id))
    if not abo:
        await interaction.response.send_message("Aucun abonnement actif.", ephemeral=True)
        return
    await interaction.response.send_message(f"Type : {abo['type']}\nExpire le : {abo['end']}", ephemeral=True)

@TREE.command(name="ajouterabo", description="Ajouter un abonnement à un utilisateur")
@app_commands.checks.has_permissions(administrator=True)
async def ajouterabo(interaction: discord.Interaction, user: discord.Member, type: str, duree_jours: int):
    from datetime import datetime, timedelta
    fin = (datetime.utcnow() + timedelta(days=duree_jours)).strftime("%Y-%m-%d")
    db = database.load_db()
    db["subscriptions"][str(user.id)] = {"type": type, "end": fin}
    database.save_db(db)
    await interaction.response.send_message("Abonnement ajouté.")

@TREE.command(name="monprofil", description="Afficher ton profil Luxoria")
async def monprofil(interaction: discord.Interaction):
    db = database.load_db()
    abo = db["subscriptions"].get(str(interaction.user.id), {"type": "Aucun", "end": "-"})
    cmds = database.get_commands_by_user(interaction.user.id)
    embed = discord.Embed(title=f"Profil de {interaction.user.name}", color=0x7289da)
    embed.add_field(name="Abonnement", value=abo["type"])
    embed.add_field(name="Expire le", value=abo["end"])
    embed.add_field(name="Commandes passées", value=str(len(cmds)))
    embed.set_footer(text=f"Membre depuis {interaction.user.joined_at.date()}.")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@TREE.command(name="vip", description="Voir les avantages VIP")
async def vip(interaction: discord.Interaction):
    embed = discord.Embed(title="⭐ Avantages VIP", description="Accès prioritaire, promos exclusives, support rapide...", color=0xffd700)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@TREE.command(name="vip-promos", description="Promos réservées aux VIP")
async def vip_promos(interaction: discord.Interaction):
    await interaction.response.send_message("Actuellement aucune promo VIP disponible.", ephemeral=True)

@TREE.command(name="vip-support", description="Ouvrir un ticket prioritaire pour VIP")
async def vip_support(interaction: discord.Interaction):
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    channel = await interaction.guild.create_text_channel(name=f"vip-{interaction.user.name}", overwrites=overwrites)
    await channel.send(f"Support prioritaire pour <@{interaction.user.id}>.")
    await interaction.response.send_message("Ticket prioritaire créé.", ephemeral=True)

# --- Logs, Clear, Ban, Kick ---

@TREE.command(name="logs", description="Afficher les dernières commandes")
async def logs(interaction: discord.Interaction):
    logs = database.get_all_commands()[-5:]
    if not logs:
        await interaction.response.send_message("Aucune commande enregistrée.", ephemeral=True)
        return
    embed = discord.Embed(title="Logs des dernières commandes", color=0x666666)
    for l in logs:
        embed.add_field(name=l["product"], value=f"<@{l['user']}> - {l['status']}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@TREE.command(name="clear", description="Supprimer des messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"{amount} messages supprimés.", ephemeral=True)

@TREE.command(name="ban", description="Bannir un membre")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "Pas de raison"):
    await user.ban(reason=reason)
    await interaction.response.send_message(f"{user.mention} banni.")

@TREE.command(name="kick", description="Expulser un membre")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "Pas de raison"):
    await user.kick(reason=reason)
    await interaction.response.send_message(f"{user.mention} expulsé.")

# --- Boutique paginée avec boutons ---

class BoutiqueView(discord.ui.View):
    def __init__(self, produits):
        super().__init__(timeout=120)
        self.produits = produits
        self.index = 0
        self.message = None

    async def update_message(self):
        produit = self.produits[self.index]
        embed = discord.Embed(title=f"🛍️ Boutique - {produit['name']}", color=0x3498db)
        embed.add_field(name="Description", value=produit["description"], inline=False)
        embed.add_field(name="Prix", value=f"{produit['price']} €", inline=True)
        embed.add_field(name="Stock", value=str(produit["stock"]), inline=True)
        embed.set_footer(text=f"Produit {self.index + 1} / {len(self.produits)}")
        await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Précédent", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
            await self.update_message()
        await interaction.response.defer()

    @discord.ui.button(label="Acheter", style=discord.ButtonStyle.success)
    async def acheter(self, interaction: discord.Interaction, button: discord.ui.Button):
        produit = self.produits[self.index]
        if produit["stock"] <= 0:
            await interaction.response.send_message("Désolé, ce produit est en rupture de stock.", ephemeral=True)
            return
        # Crée la commande
        database.add_command(interaction.user.id, produit["name"])

        # Met à jour le stock
        produit["stock"] -= 1
        db = database.load_db()
        for p in db["products"]:
            if p["name"].lower() == produit["name"].lower():
                p["stock"] = produit["stock"]
                break
        database.save_db(db)

        # Envoie un message dans le salon commandes
        global commandes_channel
        if commandes_channel:
            await commandes_channel.send(f"Nouvelle commande de {interaction.user.mention} pour **{produit['name']}**.")

        await interaction.response.send_message("Commande enregistrée ! Merci pour votre achat.", ephemeral=True)
        await self.update_message()

    @discord.ui.button(label="Suivant", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.produits) - 1:
            self.index += 1
            await self.update_message()
        await interaction.response.defer()

@TREE.command(name="boutique", description="Afficher la boutique")
async def boutique(interaction: discord.Interaction):
    produits = database.get_all_products()
    if not produits:
        await interaction.response.send_message("La boutique est vide.", ephemeral=True)
        return
    view = BoutiqueView(produits)
    embed = discord.Embed(title=f"🛍️ Boutique - {produits[0]['name']}", color=0x3498db)
    embed.add_field(name="Description", value=produits[0]["description"], inline=False)
    embed.add_field(name="Prix", value=f"{produits[0]['price']} €", inline=True)
    embed.add_field(name="Stock", value=str(produits[0]["stock"]), inline=True)
    embed.set_footer(text=f"Produit 1 / {len(produits)}")
    msg = await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
    view.message = await interaction.original_response()

# --- Ajouter un produit (admin) ---

class AddProduitModal(discord.ui.Modal, title="Ajouter un produit"):
    def __init__(self):
        super().__init__()
        self.nom = discord.ui.TextInput(label="Nom du produit", max_length=50)
        self.description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)
        self.stock = discord.ui.TextInput(label="Stock", max_length=5)
        self.prix = discord.ui.TextInput(label="Prix (€)", max_length=10)

        self.add_item(self.nom)
        self.add_item(self.description)
        self.add_item(self.stock)
        self.add_item(self.prix)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            stock = int(self.stock.value)
            prix = float(self.prix.value)
        except:
            await interaction.response.send_message("Stock doit être un entier et prix un nombre.", ephemeral=True)
            return
        database.add_product(self.nom.value, self.description.value, stock, prix)
        await interaction.response.send_message(f"Produit **{self.nom.value}** ajouté à la boutique.", ephemeral=True)

@TREE.command(name="addproduits", description="Ajouter un produit à la boutique (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def addproduits(interaction: discord.Interaction):
    modal = AddProduitModal()
    await interaction.response.send_modal(modal)

# --- Supprimer un produit (admin) ---

@TREE.command(name="suprproduits", description="Supprimer un produit (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def suprproduits(interaction: discord.Interaction, nom: str):
    ok = database.remove_product(nom)
    if ok:
        await interaction.response.send_message(f"Produit **{nom}** supprimé.")
    else:
        await interaction.response.send_message("Produit introuvable.")

# --- Supprimer un pack (admin) ---

@TREE.command(name="suprpack", description="Supprimer un pack (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def suprpack_cmd(interaction: discord.Interaction, nom: str):
    ok = database.remove_pack(nom)
    if ok:
        await interaction.response.send_message(f"Pack **{nom}** supprimé.")
    else:
        await interaction.response.send_message("Pack introuvable.")

# --- Erreurs ---

@addproduits.error
@suprproduits.error
@suprpack_cmd.error
@cmdencours.error
@cmdlivrer.error
@suprcmd.error
@addcmd.error
@clear.error
@ban.error
@kick.error
async def on_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("Vous n'avez pas la permission d'utiliser cette commande.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Erreur: {error}", ephemeral=True)

bot.run(TOKEN)
