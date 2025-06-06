import discord
from discord.ext import commands
from discord import app_commands
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

# Chargement de la base de données
if not os.path.exists("database.json"):
    with open("database.json", "w") as f:
        json.dump({"commands": [], "products": [], "packs": [], "subscriptions": {}}, f)

with open("database.json", "r") as f:
    db = json.load(f)

def save_db():
    with open("database.json", "w") as f:
        json.dump(db, f, indent=4)

# ========== COMMANDES SLASH ==========

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
    for cmd in db["commands"]:
        if cmd["user"] == user.id and cmd["product"].lower() == produit.lower():
            cmd["status"] = "livrée"
            save_db()
            await interaction.response.send_message("Commande livrée.")
            return
    await interaction.response.send_message("Commande introuvable.")

@TREE.command(name="suprcmd", description="Supprimer une commande")
@app_commands.checks.has_permissions(administrator=True)
async def suprcmd(interaction: discord.Interaction, user: discord.Member, produit: str):
    db["commands"] = [c for c in db["commands"] if not (c["user"] == user.id and c["product"].lower() == produit.lower())]
    save_db()
    await interaction.response.send_message("Commande supprimée.")

@TREE.command(name="annulercmd", description="Annuler votre commande")
async def annulercmd(interaction: discord.Interaction, produit: str):
    db["commands"] = [c for c in db["commands"] if not (c["user"] == interaction.user.id and c["product"].lower() == produit.lower())]
    save_db()
    await interaction.response.send_message("Commande annulée.", ephemeral=True)

@TREE.command(name="addcmd", description="Ajouter une commande (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def addcmd(interaction: discord.Interaction, user: discord.Member, produit: str):
    db["commands"].append({"user": user.id, "product": produit, "status": "en attente"})
    save_db()
    await interaction.response.send_message("Commande ajoutée manuellement.")

@TREE.command(name="prix", description="Voir le prix d’un produit")
async def prix(interaction: discord.Interaction, produit: str):
    for p in db["products"]:
        if p["name"].lower() == produit.lower():
            await interaction.response.send_message(f"Le prix de **{produit}** est **{p['price']} €**.", ephemeral=True)
            return
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

@TREE.command(name="addpacks", description="Ajouter un pack (admin)")
@app_commands.checks.has_permissions(administrator=True)
async def addpacks(interaction: discord.Interaction, name: str, price: float, description: str):
    db["packs"].append({ "name": name, "price": price, "description": description })
    save_db()
    await interaction.response.send_message("Pack ajouté.")

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
        await interaction.response.send_message("Aucune commande en cours.", ephemeral=True)
        return
    embed = discord.Embed(title="Suivi de vos commandes", color=0x00ffcc)
    for c in cmds:
        embed.add_field(name=c["product"], value=c["status"], inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@TREE.command(name="abonnement", description="Voir ton abonnement")
async def abonnement(interaction: discord.Interaction):
    abo = db["subscriptions"].get(str(interaction.user.id))
    if not abo:
        await interaction.response.send_message("Aucun abonnement actif.", ephemeral=True)
        return
    await interaction.response.send_message(f"Type : {abo['type']}\nExpire le : {abo['end']}", ephemeral=True)

@TREE.command(name="ajouterabo", description="Ajouter un abonnement à un utilisateur")
@app_commands.checks.has_permissions(administrator=True)
async def ajouterabo(interaction: discord.Interaction, user: discord.Member, type: str, duree_jours: int):
    fin = (datetime.utcnow() + timedelta(days=duree_jours)).strftime("%Y-%m-%d")
    db["subscriptions"][str(user.id)] = {"type": type, "end": fin}
    save_db()
    await interaction.response.send_message("Abonnement ajouté.")

@TREE.command(name="monprofil", description="Afficher ton profil Luxoria")
async def monprofil(interaction: discord.Interaction):
    abo = db["subscriptions"].get(str(interaction.user.id), {"type": "Aucun", "end": "-"})
    cmds = [c for c in db["commands"] if c["user"] == interaction.user.id]
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

@TREE.command(name="logs", description="Afficher les dernières commandes")
async def logs(interaction: discord.Interaction):
    logs = db["commands"][-5:]
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

# ========== LANCEMENT ==========
@bot.event
async def on_ready():
    await TREE.sync()
    print(f"{bot.user} est connecté !")

bot.run(TOKEN)
