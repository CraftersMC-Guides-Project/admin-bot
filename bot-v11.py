import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import datetime
import copy
import json
import base64
import requests
import io
import math
import asyncio
from collections import defaultdict
from difflib import get_close_matches
from typing import Optional
import os
from dotenv import load_dotenv
load_dotenv()

USER_GITHUB_TOKENS = {
    947868777528307742: os.environ.get('GITHUB_TOKEN_DEFAULT'),
    845690488752832522: os.environ.get('GITHUB_TOKEN_DEFAULT'),
    783972385882767400: os.environ.get('GITHUB_TOKEN_DEFAULT'),
    992284684425904168: os.environ.get('GITHUB_TOKEN_DEFAULT'),
    1099047739209293944: os.environ.get('GITHUB_TOKEN_DEFAULT'),
    909654814651195423: os.environ.get('GITHUB_TOKEN_DEFAULT'),
    878545726014107698: os.environ.get('GITHUB_TOKEN_DEFAULT'),
    1275833464981032970: os.environ.get('GITHUB_TOKEN_DEFAULT'),
    1224733916213284864: os.environ.get('GITHUB_TOKEN_DEFAULT'),
    1178800421926608949: os.environ.get('GITHUB_TOKEN_DEFAULT'),
    994249322667450460: os.environ.get('GITHUB_TOKEN_DEFAULT'),
    # ...add more as needed
}

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN_DEFAULT')

TOKEN = os.environ.get('BOT_TOKEN')
webhook_url = os.environ.get('WEBHOOK_URL')
REPO = 'CraftersMC-Guides-Project/guides-code'
FILE_PATH = 'market/mprices.txt'
MARKET_FILE_PATH = 'market/market.txt'
PET_FILE_PATH = 'market/pet-prices.txt'
PET_MARKET_FILE_PATH = 'market/pets.txt'
MINION_FILE_PATH = 'market/minion-prices.txt'
MINION_MARKET_FILE_PATH = 'market/minions.txt'

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='.', intents=intents)

original_data = []
temp_data = []
change_history = []

# These functions are defined later in the file
# market_temp will be initialized in initialize_data()

def load_file():
    global original_data, temp_data
    original_data = []
    updated_lines = []
    file_changed = False

    def safe(val):
        if val is None:
            return "null"
        return json.dumps(val)

    try:
        with open("mprices.txt", "r") as f:
            for line in f:
                try:
                    parts = line.strip().split(": ", 1)
                    if len(parts) != 2:
                        continue

                    clean_line = parts[1].replace("N/A", "null")
                    item = json.loads(clean_line)

                    name = item[0]
                    user_price = item[1]
                    npc_price = item[2] if len(item) > 2 else None

                    if npc_price is None:
                        npc_price = 0
                        file_changed = True

                    original_data.append([name, user_price, npc_price])

                    updated_lines.append(
                        f'{parts[0]}: [{safe(name)}, {safe(user_price)}, {safe(npc_price)}]\n'
                    )

                except Exception as item_error:
                    print(f"Skipping line due to error: {item_error}\nLine: {line.strip()}")

        temp_data = copy.deepcopy(original_data)

        if file_changed:
            with open("mprices.txt", "w") as f:
                f.writelines(updated_lines)

            try:
                with open("mprices.txt", "r") as f:
                    content = f.read()

                sha = get_file_sha_blank()
                upload_to_github_blank(content, sha)
                print("✅ NaN update committed to GitHub.")
            except Exception as e:
                print(f"❌ Error committing changes: {e}")

    except Exception as e:
        print(f"❌ Error loading mprices.txt: {e}")

ABBREVIATIONS = {
    "enc": "enchanted",
    "ench": "enchanted",
    "green": "grean",
    "cobble": "cobblestone",
    "op": "OVERPRICE",
    "st": "STABLE",
    "up": "UNDERPRICE",
    "overprice": "OVERPRICE",
    "stable": "STABLE",
    "underprice": "UNDERPRICE",
}

def expand_abbreviations(text: str) -> str:
    words = text.lower().split()
    expanded = [ABBREVIATIONS.get(w, w) for w in words]
    return " ".join(expanded)

user_lock = defaultdict(lambda: None)

def check_lock(command_category, user_id):
    if user_lock[command_category] is None or user_lock[command_category] == user_id:
        return True
    return False

@bot.command(aliases=['up'])
async def updateprice(ctx, *, args=None):
    if args is None:
        await ctx.send("Usage: `.up <index or item name> <user_price> <npc_price>`\n"
                      "Example: `.up 10 1000 1000` or `.up stick 1000 500`")
        return

    category = "updateprice"
    if not check_lock(category, ctx.author.id):
        await ctx.send("Another user is currently using this command category. Please try again later.")
        return

    user_lock[category] = ctx.author.id
    global temp_data, change_history

    try:
        parts = args.rsplit(" ", 2)
        npc_price = None
        if len(parts) == 3:
            identifier, user_price_str, npc_price_str = parts
            npc_price = round(float(npc_price_str))
        elif len(parts) == 2:
            identifier, user_price_str = parts
        else:
            raise ValueError
        user_price = round(float(user_price_str))
        identifier = identifier.strip()
    except ValueError:
        await ctx.send("Usage: `.up <index or item name> <user_price> <npc_price>`\n"
                      "Example: `.up 10 1000 1000` or `.up stick 1000 500`")
        user_lock[category] = None
        return

    def update_item(index):
        # Check if values are actually changing
        user_changed = temp_data[index][1] != user_price
        npc_changed = (npc_price is not None and 
                      (len(temp_data[index]) <= 2 or temp_data[index][2] != npc_price))
        
        if not user_changed and not npc_changed:
            return f"**{temp_data[index][0]}** already has these values (no changes made)."

        # Only add to history if something actually changes
        if user_changed or npc_changed:
            change_history.append(copy.deepcopy(temp_data))
            
            if user_changed:
                temp_data[index][1] = user_price
                
            if npc_changed:
                if len(temp_data[index]) > 2:
                    temp_data[index][2] = npc_price
                else:
                    temp_data[index].append(npc_price)
        
        npc_display = f"{npc_price}" if npc_price is not None else "(unchanged)"
        return f"Updated **{temp_data[index][0]}** to **User: {user_price}**, **NPC: {npc_display}**."

    # Check if identifier is numeric (index)
    if identifier.isdigit():
        index = int(identifier)
        if 1 <= index <= len(temp_data):
            msg = update_item(index - 1)
            await ctx.send(msg)
        else:
            await ctx.send(f"Invalid index. Please provide a valid index between 1 and {len(temp_data)}.")
        user_lock[category] = None
        return

    # Expand abbreviation for identifier
    expanded_name = expand_abbreviations(identifier.lower())
    item_names = [item[0].lower() for item in temp_data]

    # Try to match expanded name to item names
    matches = [(i, name) for i, name in enumerate(item_names) if expanded_name in name]

    # No direct matches, try close matches
    if not matches:
        close_matches = get_close_matches(expanded_name, item_names, n=3, cutoff=0.6)
        if not close_matches:
            await ctx.send(f"No item found matching '{identifier}'.")
            user_lock[category] = None
            return
        elif len(close_matches) > 1:
            await ctx.send(f"Multiple items match '{identifier}': {close_matches}. Please be more specific.")
            user_lock[category] = None
            return

        match_name = close_matches[0]
        for i, item in enumerate(temp_data):
            if item[0].lower() == match_name:
                msg = update_item(i)
                await ctx.send(f"{msg} (best match).")
                user_lock[category] = None
                return

    # Handle multiple matches with buttons
    if len(matches) > 1:
        class ItemChoiceView(View):
            def __init__(self, matches, user_id):
                super().__init__(timeout=30)
                self.user_id = user_id
                for idx, _ in matches:
                    self.add_item(Button(label=temp_data[idx][0], custom_id=str(idx)))

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                return interaction.user.id == self.user_id

        view = ItemChoiceView(matches, ctx.author.id)
        await ctx.send("Multiple items match your input. Please select one:", view=view)

        async def wait_for_choice():
            try:
                interaction: discord.Interaction = await bot.wait_for(
                    "interaction",
                    check=lambda i: i.user == ctx.author and hasattr(i, 'data') and i.data and "custom_id" in i.data and i.data["custom_id"].isdigit(),
                    timeout=30
                )
                index = int(interaction.data.get("custom_id", "0"))
                await interaction.response.send_message(
                    "Enter the new **user price** and optionally the **NPC price**, separated by space (e.g., `1000 1200`):",
                    ephemeral=True
                )

                def price_check(m):
                    return m.author == ctx.author and m.channel == ctx.channel

                msg = await bot.wait_for("message", check=price_check, timeout=30)
                try:
                    parts = msg.content.strip().split()
                    user_price_local = round(float(parts[0]))
                    npc_price_local = round(float(parts[1])) if len(parts) > 1 else None

                    # Check if values are actually changing
                    user_changed = temp_data[index][1] != user_price_local
                    npc_changed = (npc_price_local is not None and 
                                  (len(temp_data[index]) <= 2 or temp_data[index][2] != npc_price_local))
                    
                    if not user_changed and not npc_changed:
                        await ctx.send(f"**{temp_data[index][0]}** already has these values (no changes made).")
                        return

                    # Only add to history if something actually changes
                    if user_changed or npc_changed:
                        change_history.append(copy.deepcopy(temp_data))
                        
                        if user_changed:
                            temp_data[index][1] = user_price_local
                            
                        if npc_changed:
                            if len(temp_data[index]) > 2:
                                temp_data[index][2] = npc_price_local
                            else:
                                temp_data[index].append(npc_price_local)

                    npc_display = f"{npc_price_local}" if npc_changed else "(unchanged)"
                    await ctx.send(f"Updated **{temp_data[index][0]}** to **User: {user_price_local}**, **NPC: {npc_display}**.")
                except:
                    await ctx.send("Invalid input. Please try the command again.")
            except asyncio.TimeoutError:
                await ctx.send("Timed out. Please try again.")

        await wait_for_choice()
        user_lock[category] = None
        return

    # Single match, apply update
    i, _ = matches[0]
    msg = update_item(i)
    await ctx.send(msg)
    user_lock[category] = None

@bot.command(aliases=['un'])
async def updatenpc(ctx, *, args=None):
    if args is None:
        await ctx.send("Usage: `.un <index or item name> <npc_price>`\n"
                      "Example: `.un 10 500` or `.un stick 500`")
        return

    category = "updateprice"
    if not check_lock(category, ctx.author.id):
        await ctx.send("Another user is currently using this command category. Please try again later.")
        return

    user_lock[category] = ctx.author.id
    global temp_data, change_history

    try:
        identifier, npc_price_str = args.rsplit(" ", 1)
        npc_price = round(float(npc_price_str))
        identifier = identifier.strip()
    except ValueError:
        await ctx.send("Usage: `.un <index or item name> <npc_price>`\n"
                      "Example: `.un 10 500` or `.un stick 500`")
        user_lock[category] = None
        return

    if identifier.isdigit():
        index = int(identifier)
        if 1 <= index <= len(temp_data):
            change_history.append(copy.deepcopy(temp_data))
            if len(temp_data[index - 1]) > 2:
                temp_data[index - 1][2] = npc_price
            else:
                temp_data[index - 1].append(npc_price)
            await ctx.send(f"Updated item {index} to **NPC: {npc_price}**.")
        else:
            await ctx.send(f"Invalid index. Please provide a valid index between 1 and {len(temp_data)}.")
        user_lock[category] = None
        return

    expanded_name = expand_abbreviations(identifier.lower())
    item_names = [item[0].lower() for item in temp_data]
    matches = [(i, name) for i, name in enumerate(item_names) if expanded_name in name]

    if not matches:
        close_matches = get_close_matches(expanded_name, item_names, n=3, cutoff=0.6)
        if not close_matches:
            await ctx.send(f"No item found matching '{identifier}'.")
            user_lock[category] = None
            return
        elif len(close_matches) > 1:
            await ctx.send(f"Multiple items match '{identifier}': {close_matches}. Please be more specific.")
            user_lock[category] = None
            return

        match_name = close_matches[0]
        for i, item in enumerate(temp_data):
            if item[0].lower() == match_name:
                change_history.append(copy.deepcopy(temp_data))
                if len(temp_data[i]) > 2:
                    temp_data[i][2] = npc_price
                else:
                    temp_data[i].append(npc_price)
                await ctx.send(f"Updated **{item[0]}** to **NPC: {npc_price}** (best match).")
                user_lock[category] = None
                return

    if len(matches) > 1:
        class ItemChoiceView(View):
            def __init__(self, matches, user_id):
                super().__init__(timeout=30)
                self.user_id = user_id
                for idx, _ in matches:
                    self.add_item(Button(label=temp_data[idx][0], custom_id=str(idx)))

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                return interaction.user.id == self.user_id

        view = ItemChoiceView(matches, ctx.author.id)
        await ctx.send("Multiple items match your input. Please select one:", view=view)

        async def wait_for_choice():
            try:
                interaction: discord.Interaction = await bot.wait_for(
                    "interaction",
                    check=lambda i: i.user == ctx.author and hasattr(i, 'data') and i.data and "custom_id" in i.data and i.data["custom_id"].isdigit(),
                    timeout=30
                )
                index = int(interaction.data.get("custom_id", "0"))
                change_history.append(copy.deepcopy(temp_data))
                if len(temp_data[index]) > 2:
                    temp_data[index][2] = npc_price
                else:
                    temp_data[index].append(npc_price)
                await interaction.response.send_message(
                    f"Updated **{temp_data[index][0]}** to **NPC: {npc_price}**.",
                    ephemeral=False
                )
            except asyncio.TimeoutError:
                await ctx.send("Timed out. Please try again.")

        await wait_for_choice()
        user_lock[category] = None
        return

    # Single match
    i, _ = matches[0]
    change_history.append(copy.deepcopy(temp_data))
    if len(temp_data[i]) > 2:
        temp_data[i][2] = npc_price
    else:
        temp_data[i].append(npc_price)
    await ctx.send(f"Updated **{temp_data[i][0]}** to **NPC: {npc_price}**.")

    user_lock[category] = None


class PriceChangeView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id 

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="Commit Changes", style=discord.ButtonStyle.success, custom_id="price_commit_btn")
    async def commit_changes(self, interaction: discord.Interaction, button: Button):
        user_id = self.user_id
        global temp_data, original_data, change_history
        await interaction.response.defer(ephemeral=True)
        try:
            # Store original data before making changes
            old_data = original_data.copy()
            webhook_url = "https://discord.com/api/webhooks/1370789767155023882/HzjZZHZSrQWBY0GM9UKpVFRqM7XjypWu4H_m73jwx2xbdq2eLRuwo4PcTgp9V94UK3fe"
            
            # Generate new content
            content = ""
            for i, item in enumerate(temp_data, start=1):
                name = item[0]
                user_price = item[1] if item[1] is not None else "0"
                npc_price = item[2] if len(item) > 2 and item[2] is not None else "0"
                content += f'{i}: ["{name}", {user_price}, {npc_price}]\n'
    
            # Save to file and GitHub
            with open("mprices.txt", "w") as f:
                f.write(content)
            sha = get_file_sha(user_id)
            upload_to_github(content, sha, user_id)
            load_file()
    
            # Find changes between old and new data
            changes = []
            for i, (new_item, old_item) in enumerate(zip(temp_data, old_data), start=1):
                old_user_price = old_item[1] if old_item[1] is not None else 0
                new_user_price = new_item[1] if new_item[1] is not None else 0
                old_npc_price = old_item[2] if len(old_item) > 2 and old_item[2] is not None else 0
                new_npc_price = new_item[2] if len(new_item) > 2 and new_item[2] is not None else 0
    
                if old_user_price != new_user_price or old_npc_price != new_npc_price:
                    changes.append(f"`{i}:` {old_item} → {new_item}")
    
            # Check for added/removed items
            if len(temp_data) > len(old_data):
                for i in range(len(old_data), len(temp_data)):
                    changes.append(f"`{i + 1}:` + {temp_data[i]}")
            elif len(temp_data) < len(old_data):
                for i in range(len(temp_data), len(old_data)):
                    changes.append(f"`{i + 1}:` - {old_data[i]}")
    
            # Prepare embed
            embed = discord.Embed(
                title="📝 Price Changes Committed",
                description=f"Changes made by {interaction.user.mention}",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            if changes:
                # Split changes into chunks to avoid embed field limits
                change_chunks = [changes[i:i + 10] for i in range(0, len(changes), 10)]
                for i, chunk in enumerate(change_chunks, 1):
                    embed.add_field(
                        name=f"Changes (Part {i})" if len(change_chunks) > 1 else "Changes",
                        value="\n".join(chunk),
                        inline=False
                    )
                embed.set_footer(text=f"Total changes: {len(changes)}")
            else:
                embed.description = "No changes detected"
                embed.color = discord.Color.blue()
    
            try:
                avatar_url = interaction.client.user.display_avatar.url if interaction.client.user and interaction.client.user.display_avatar else None
                webhook_data = {
                    "embeds": [embed.to_dict()],
                    "username": "Market Bot"
                }
                if avatar_url:
                    webhook_data["avatar_url"] = avatar_url
                requests.post(webhook_url, json=webhook_data)
            except Exception as webhook_error:
                print(f"Failed to send webhook: {webhook_error}")
    
            await interaction.followup.send(
                embed=discord.Embed(
                    description="✅ Changes committed to GitHub and saved to `mprices.txt`",
                    color=discord.Color.green()
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=f"❌ Error committing changes: `{e}`",
                    color=discord.Color.red()
                ),
                ephemeral=False
            )
    
    @discord.ui.button(label="Undo Last", style=discord.ButtonStyle.danger, custom_id="price_undo_last_btn")
    async def undo_last(self, interaction: discord.Interaction, button: Button):
        global temp_data, change_history

        await interaction.response.defer()
        if change_history:
            temp_data = change_history.pop()
            await interaction.followup.send("🔁 Last change has been undone.")
        else:
            await interaction.followup.send("⚠️ No previous change to undo.")

    @discord.ui.button(label="Undo All", style=discord.ButtonStyle.danger, custom_id="price_undo_all_btn")
    async def undo_all(self, interaction: discord.Interaction, button: Button):
        global temp_data, original_data, change_history

        await interaction.response.defer()
        if change_history:
            temp_data = copy.deepcopy(original_data)
            change_history.clear()
            await interaction.followup.send("🔄 All changes have been undone.")
        else:
            await interaction.followup.send("⚠️ No changes to undo.")

@bot.command(aliases=['sc'])
async def showchanges(ctx):
    category = "showchanges"
    if not check_lock(category, ctx.author.id):
        await ctx.send("Another user is currently using this command category. Please try again later.")
        return

    user_lock[category] = ctx.author.id

    def format_entry(item):
        name = item[0]
        user_price = item[1] if item[1] is not None else "0"
        npc_price = item[2] if len(item) > 2 and item[2] is not None else "0"
        return f'["{name}", {user_price}, {npc_price}]'

    diff = ""
    for i, (new_item, old_item) in enumerate(zip(temp_data, original_data), start=1):
        old_user_price = old_item[1] if old_item[1] is not None else 0
        new_user_price = new_item[1] if new_item[1] is not None else 0
        old_npc_price = old_item[2] if len(old_item) > 2 and old_item[2] is not None else 0
        new_npc_price = new_item[2] if len(new_item) > 2 and new_item[2] is not None else 0

        if old_user_price != new_user_price or old_npc_price != new_npc_price:
            diff += f"{i}: {format_entry(old_item)} → {format_entry(new_item)}\n"

    if len(temp_data) > len(original_data):
        for i in range(len(original_data), len(temp_data)):
            diff += f"{i + 1}: + {format_entry(temp_data[i])}\n"

    elif len(temp_data) < len(original_data):
        for i in range(len(temp_data), len(original_data)):
            diff += f"{i + 1}: - {format_entry(original_data[i])}\n"

    if not diff:
        diff = "No changes."

    user_token = get_user_github_token(ctx.author.id)
    if not user_token:
        await ctx.send("No GitHub token found for this user. Please ensure you have linked your GitHub account.")
        user_lock[category] = None
        return

    try:
        user_id = ctx.author.id
        get_file_sha(user_id)
    except ValueError as e:
        await ctx.send(f"Error fetching file: {str(e)}")
        user_lock[category] = None
        return
    except requests.exceptions.RequestException as e:
        await ctx.send(f"GitHub request failed: {str(e)}")
        user_lock[category] = None
        return

    view = PriceChangeView(ctx.author.id)

    if len(diff) > 3900:
        file = discord.File(io.BytesIO(diff.encode('utf-8')), filename="diff.txt")
        await ctx.send("Here are the pending changes:", file=file, view=view)
    else:
        await ctx.send(f"```diff\n{diff}```", view=view)

    user_lock[category] = None

market_original, market_temp = [], []
pet_market_original, pet_market_temp = [], []
market_history, pet_market_history = [], []

def load_market_data():
    with open("market.txt", "r") as f:
        return json.load(f)

def save_market_data(data):
    with open("market.txt", "w") as f:
        json.dump(data, f, indent=4)

def load_pet_market_data():
    with open("pets.txt", "r") as f:
        return json.load(f)

def save_pet_market_data(data):
    with open("pets.txt", "w") as f:
        json.dump(data, f, indent=4)

def initialize_data():
    global market_original, market_temp, pet_market_original, pet_market_temp
    market_original = load_market_data()
    market_temp = copy.deepcopy(market_original)
    pet_market_original = load_pet_market_data()
    pet_market_temp = copy.deepcopy(pet_market_original)

async def update_entry(ctx, args, data_temp, data_history, filetype: str):
    if args is None:
        await ctx.send(f"Usage: `.{filetype} <item> [nature] [demand]`\n"
                      f"Example: `.{filetype} stick stable 9`")
        return

    parts = args.split()
    nature = demand = None

    if parts:
        last = parts[-1]
        if last.isdigit() or "/10" in last:
            demand = parts.pop()
            if "/" not in demand:
                demand = f"{demand}/10"

    if parts:
        potential_nature = parts[-1]
        if not potential_nature.isdigit() and "/10" not in potential_nature:
            nature = parts.pop().upper()

    if not parts:
        await ctx.send("❌ Could not parse item name. Please try again.")
        return

    identifier = expand_abbreviations(" ".join(parts).lower().strip())
    if nature:
        nature = expand_abbreviations(nature.lower())
    if demand:
        demand = expand_abbreviations(demand.lower())

    matches = [
        (i, item) for i, item in enumerate(data_temp)
        if identifier in expand_abbreviations(item['name'].lower()) or str(item['id']) == identifier
    ]

    if not matches:
        expanded_names = [expand_abbreviations(item['name'].lower()) for item in data_temp]
        close = get_close_matches(identifier, expanded_names, n=3, cutoff=0.5)
        if not close:
            await ctx.send("❌ No matches found.")
            return
        elif len(close) > 1:
            await ctx.send(f"Multiple items match '{identifier}': {close}. Please be more specific.")
            return

        matches = [
            (i, item) for i, item in enumerate(data_temp)
            if expand_abbreviations(item['name'].lower()) in close
        ]

    async def apply_update(index: int):
        data_history.append(copy.deepcopy(data_temp))
        updates = []
        if nature is not None:
            data_temp[index]['nature'] = f"[{nature}]"
            updates.append(f"nature **[{nature}]**")
        else:
            # Preserve existing nature formatting (strip brackets if needed)
            current_nature = data_temp[index].get('nature', '')
            data_temp[index]['nature'] = current_nature
    
        if demand is not None:
            data_temp[index]['demand'] = f"[{demand}]"
            updates.append(f"demand **[{demand}]**")
        else:
            # Preserve existing demand formatting
            current_demand = data_temp[index].get('demand', '')
            data_temp[index]['demand'] = current_demand
    
        updated_item = data_temp[index]
        changes_msg = " and ".join(updates) if updates else "no changes"
        await ctx.send(f"✅ Updated **{updated_item['name']}** with {changes_msg}.")
    

    if len(matches) > 1:
        class ChoiceView(View):
            def __init__(self):
                super().__init__(timeout=30)
                for idx, item in matches:
                    label = f"{item['name']} ({item['id']})"
                    self.add_item(Button(label=label, custom_id=str(idx)))

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                return interaction.user == ctx.author

        view = ChoiceView()
        await ctx.send("🔍 Multiple items found. Select one:", view=view)

        def check(interaction: discord.Interaction):
            return interaction.user == ctx.author and hasattr(interaction, 'data') and interaction.data and 'custom_id' in interaction.data and interaction.data['custom_id'].isdigit()

        try:
            interaction = await bot.wait_for("interaction", check=check, timeout=30)
            await interaction.response.defer()
            await apply_update(int(interaction.data.get('custom_id', '0')))
        except asyncio.TimeoutError:
            await ctx.send("⏱️ Selection timed out.")
    else:
        index, _ = matches[0]
        await apply_update(index)

@bot.command(aliases=['um'])
async def updatemarket(ctx, *, args=None):
    await update_entry(ctx, args, market_temp, market_history, "um")

@bot.command(aliases=['upm'])
async def updatepet_marketmarket(ctx, *, args=None):
    await update_entry(ctx, args, pet_market_temp, pet_market_history, "upm")

class MarketChangeView(View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Commit Changes", style=discord.ButtonStyle.success, custom_id="commit_market")
    async def commit_changes(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Defer the response immediately to prevent interaction timeout
            await interaction.response.defer()
            
            user_id = interaction.user.id
            committed = []
            changes = []
    
            # Check for changes in market
            if market_temp != market_original:
                market_content = json.dumps(market_temp, indent=4)
                with open("market.txt", "w") as f:
                    f.write(market_content)
    
                market_sha = get_market_sha(user_id)
                upload_market_to_github(market_content, market_sha, user_id)
                committed.append("Market")
                
                # Collect market changes for webhook
                for temp_item, orig_item in zip(market_temp, market_original):
                    item_changes = []
                    for key in ['name', 'price', 'nature', 'demand']:
                        if temp_item.get(key) != orig_item.get(key):
                            item_changes.append(f"{key}: {orig_item.get(key, 'N/A')} → {temp_item.get(key, 'N/A')}")
                    if item_changes:
                        changes.append(f"[Market] {orig_item['name']} ({orig_item['id']}):\n  " + "\n  ".join(item_changes))
    
            # Check for changes in pets
            if pet_market_temp != pet_market_original:
                pet_content = json.dumps(pet_market_temp, indent=4)
                with open("pets.txt", "w") as f:
                    f.write(pet_content)
    
                pet_sha = get_pet_market_sha(user_id)
                upload_pet_market_to_github(pet_content, pet_sha, user_id)
                committed.append("Pets")
                
                # Collect pet changes for webhook
                for temp_item, orig_item in zip(pet_market_temp, pet_market_original):
                    item_changes = []
                    for key in ['name', 'price', 'nature', 'demand']:
                        if temp_item.get(key) != orig_item.get(key):
                            item_changes.append(f"{key}: {orig_item.get(key, 'N/A')} → {temp_item.get(key, 'N/A')}")
                    if item_changes:
                        changes.append(f"[Pets] {orig_item['name']} ({orig_item['id']}):\n  " + "\n  ".join(item_changes))
    
            # Reload and clear only if something was committed
            if committed:
                # Update both temp and original data to reflect the committed state
                market_temp[:] = load_market_data()
                market_original[:] = copy.deepcopy(market_temp)
                pet_market_temp[:] = load_pet_market_data()
                pet_market_original[:] = copy.deepcopy(pet_market_temp)
                market_history.clear()
                pet_market_history.clear()
                
                # Send webhook with changes
                if changes:
                    embed = discord.Embed(
                        title="📝 Market Changes Committed",
                        description=f"Changes made by {interaction.user.mention}",
                        color=discord.Color.green(),
                        timestamp=discord.utils.utcnow()
                    )
                    
                    # Split changes into chunks to avoid embed field limits
                    change_chunks = [changes[i:i + 10] for i in range(0, len(changes), 10)]
                    for i, chunk in enumerate(change_chunks, 1):
                        embed.add_field(
                            name=f"Changes (Part {i})" if len(change_chunks) > 1 else "Changes",
                            value="\n".join(chunk),
                            inline=False
                        )
                    embed.set_footer(text=f"Total changes: {len(changes)}")
                    
                    try:
                        avatar_url = interaction.client.user.display_avatar.url if interaction.client.user and interaction.client.user.display_avatar else None
                        webhook_data = {
                            "embeds": [embed.to_dict()],
                            "username": "Market Bot"
                        }
                        if avatar_url:
                            webhook_data["avatar_url"] = avatar_url
                        requests.post(webhook_url, json=webhook_data)
                    except Exception as webhook_error:
                        print(f"Failed to send webhook: {webhook_error}")
                
                await interaction.followup.send(f"✅ Committed changes to: {', '.join(committed)}. Temporary edits cleared.")
            else:
                await interaction.followup.send("ℹ️ No changes to commit.")
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Error committing changes: `{e}`")
            except:
                # If followup also fails, try to send a new message
                if hasattr(interaction.channel, 'send'):
                    await interaction.channel.send(f"❌ Error committing changes: `{e}`")
    
    @discord.ui.button(label="Undo Last", style=discord.ButtonStyle.danger, custom_id="undo_last")
    async def undo_last(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if market_history:
            market_temp[:] = market_history.pop()
        if pet_market_history:
            pet_market_temp[:] = pet_market_history.pop()
        await interaction.followup.send("↩️ Last change undone.")

    @discord.ui.button(label="Undo All", style=discord.ButtonStyle.danger, custom_id="undo_all")
    async def undo_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        market_temp[:] = load_market_data()
        market_original[:] = copy.deepcopy(market_temp)
        pet_market_temp[:] = load_pet_market_data()
        pet_market_original[:] = copy.deepcopy(pet_market_temp)
        market_history.clear()
        pet_market_history.clear()
        await interaction.followup.send("🔄 All changes undone.")

@bot.command(aliases=['smc'])
async def showmarketchanges(ctx):
    diff = ""
    for temp_item, orig_item in zip(market_temp, market_original):
        changes = [f"{key}: {orig_item.get(key)} → {temp_item.get(key)}" for key in ['name', 'price', 'nature', 'demand'] if temp_item.get(key) != orig_item.get(key)]
        if changes:
            diff += f"[Market] {orig_item['name']} ({orig_item['id']}):\n  " + "\n  ".join(changes) + "\n"

    for temp_item, orig_item in zip(pet_market_temp, pet_market_original):
        changes = [f"{key}: {orig_item.get(key)} → {temp_item.get(key)}" for key in ['name', 'price', 'nature', 'demand'] if temp_item.get(key) != orig_item.get(key)]
        if changes:
            diff += f"[pets] {orig_item['name']} ({orig_item['id']}):\n  " + "\n  ".join(changes) + "\n"

    view = MarketChangeView()
    if not diff:
        diff = "No changes."

    if len(diff) > 3900:
        file = discord.File(io.BytesIO(diff.encode('utf-8')), filename="market_diff.txt")
        await ctx.send("Here are the pending changes:", file=file, view=view)
    else:
        await ctx.send(f"```diff\n{diff}```", view=view)
        
pet_temp_data = []
pet_change_history = []
pet_original_data = []

def load_pet_prices():
    global pet_original_data, pet_temp_data
    pet_original_data.clear()
    pet_temp_data.clear()
    file_changed = False

    try:
        with open("pet-prices.txt", "r") as f:
            data = json.load(f)

        # Fix missing rarity fields in-place (both market and NPC prices)
        for item in data:
            for rarity in ["common", "uncommon", "rare", "epic", "legendary"]:
                # Ensure market prices exist
                if item.get(rarity) is None:
                    item[rarity] = 0
                    file_changed = True
                # Ensure NPC prices exist
                npc_key = f"n{rarity}"
                if item.get(npc_key) is None:
                    item[npc_key] = 0
                    file_changed = True

        # Save updated data
        pet_original_data.extend(copy.deepcopy(data))
        pet_temp_data.extend(copy.deepcopy(pet_original_data))

        if file_changed:
            with open("pet-prices.txt", "w") as f:
                json.dump(data, f, indent=2)
            try:
                with open("pet-prices.txt", "r") as f:
                    content = f.read()
                sha = get_file_sha_blank()
                upload_to_github_blank(content, sha)
                print("✅ Missing values filled and committed to GitHub.")
            except Exception as e:
                print(f"❌ Error committing changes: {e}")

    except Exception as e:
        print(f"❌ Error loading pet-prices.txt: {e}")

def load_pet_data():
    with open("pet-prices.txt", "r") as f:
        return json.load(f)

load_pet_prices()

def save_pet_data(data):
    with open("pet-prices.txt", "w") as file:
        json.dump(data, file, indent=4)


async def process_pet_update(ctx, index: int, price_type: str, rarity: str, price: float):
    """Helper function to process pet price updates"""
    try:
        # Determine the price field (market or NPC)
        price_field = rarity if price_type == "market" else f"n{rarity}"
        current_value = pet_temp_data[index].get(price_field)

        # Check if the new price is different
        if round(price) == current_value:
            await ctx.send("⚠️ No changes made. The value is the same as the current one.")
            return

        # Record changes in history
        pet_change_history.append(copy.deepcopy(pet_temp_data))
        
        # Update the price
        pet_temp_data[index][price_field] = round(price)

        pet = pet_temp_data[index]
        pet_name = pet.get("name") or f"Pet ID {pet.get('petId')}"
        await ctx.send(
            f"✅ Updated `{pet_name}` **{price_type.upper()}** price "
            f"(Rarity: `{rarity.title()}`) to `{round(price)}`."
        )
    except Exception as e:
        await ctx.send(f"❌ An error occurred: {e}")

@bot.command(aliases=['pu'])
async def updatepet(ctx, pet_identifier: Optional[str] = None, price_type: Optional[str] = None, rarity: Optional[str] = None, price: Optional[float] = None):
    """
    Updates pet prices (market or NPC).
    Usage: 
      !updatepet <pet_id/name> <market/npc> <rarity> <price>
    Example:
      !updatepet 1 market common 100    (Updates market price)
      !updatepet "Silverfish" npc rare 50  (Updates NPC price)
    """
    if None in (pet_identifier, price_type, rarity, price):
        await ctx.send("Usage: `.pu <pet_id/name> <market/npc> <rarity> <price>`\n"
                      "Example: `.pu 1 market common 100` or `.pu \"Silverfish\" npc rare 50`")
        return

    category = "updatepet"
    
    if not check_lock(category, ctx.author.id):
        await ctx.send("⚠️ Another user is currently using this command category. Please try again later.")
        return
    user_lock[category] = ctx.author.id

    try:
        # Validate price type
        if price_type is None:
            await ctx.send("❌ Price type is required.")
            return
        price_type = price_type.lower()
        if price_type not in {"market", "npc"}:
            await ctx.send("❌ Invalid price type. Use `market` or `npc`.")
            return

        # Validate rarity
        if rarity is None:
            await ctx.send("❌ Rarity is required.")
            return
        rarity = rarity.lower()
        valid_rarities = {"common", "uncommon", "rare", "epic", "legendary"}
        if rarity not in valid_rarities:
            await ctx.send("❌ Invalid rarity. Choose from: common, uncommon, rare, epic, legendary")
            return

        # Validate price
        if price is None:
            await ctx.send("❌ Price is required.")
            return

        # Find the pet
        index = None
        if pet_identifier is None:
            await ctx.send("❌ Pet identifier is required.")
            return
        if pet_identifier.isdigit():
            index = next((i for i, item in enumerate(pet_temp_data)
                        if str(item.get("petId")) == pet_identifier), None)
        else:
            # Use fuzzy matching for pet names
            lower_name = pet_identifier.lower()
            pet_names = [item.get("name", "").lower() for item in pet_temp_data]
            
            # Try exact match first
            exact_matches = [(i, name) for i, name in enumerate(pet_names) if name == lower_name]
            if exact_matches:
                index = exact_matches[0][0]
            else:
                # Try partial matches
                partial_matches = [(i, name) for i, name in enumerate(pet_names) if lower_name in name]
                if partial_matches:
                    if len(partial_matches) == 1:
                        index = partial_matches[0][0]
                    else:
                        # Multiple matches - show buttons for selection
                        class PetChoiceView(View):
                            def __init__(self, matches, user_id):
                                super().__init__(timeout=30)
                                self.user_id = user_id
                                for idx, _ in matches:
                                    pet_name = pet_temp_data[idx]['name']
                                    pet_id = pet_temp_data[idx].get('petId', 'N/A')
                                    self.add_item(Button(label=f"{pet_name} (ID: {pet_id})", custom_id=str(idx)))

                            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                                return interaction.user.id == self.user_id

                        view = PetChoiceView(partial_matches, ctx.author.id)
                        await ctx.send(f"Multiple pets match '{pet_identifier}'. Please select one:", view=view)

                        async def wait_for_choice():
                            try:
                                interaction: discord.Interaction = await bot.wait_for(
                                    "interaction",
                                    check=lambda i: i.user == ctx.author and hasattr(i, 'data') and i.data and "custom_id" in i.data and i.data["custom_id"].isdigit(),
                                    timeout=30
                                )
                                selected_index = int(interaction.data.get("custom_id", "0"))
                                await interaction.response.defer()
                                
                                # Now process the update with the selected pet
                                await process_pet_update(ctx, selected_index, price_type, rarity, price)
                            except asyncio.TimeoutError:
                                await ctx.send("Timed out. Please try again.")
                            finally:
                                user_lock[category] = None

                        await wait_for_choice()
                        return
                else:
                    # Try fuzzy matching
                    close_matches = get_close_matches(lower_name, pet_names, n=3, cutoff=0.6)
                    if close_matches:
                        if len(close_matches) == 1:
                            # Single close match
                            match_name = close_matches[0]
                            for i, name in enumerate(pet_names):
                                if name == match_name:
                                    index = i
                                    break
                        else:
                            # Multiple close matches - show buttons for selection
                            close_match_indices = []
                            for match_name in close_matches:
                                for i, name in enumerate(pet_names):
                                    if name == match_name:
                                        close_match_indices.append(i)
                                        break
                            
                            class PetChoiceView(View):
                                def __init__(self, matches, user_id):
                                    super().__init__(timeout=30)
                                    self.user_id = user_id
                                    for idx in matches:
                                        pet_name = pet_temp_data[idx]['name']
                                        pet_id = pet_temp_data[idx].get('petId', 'N/A')
                                        self.add_item(Button(label=f"{pet_name} (ID: {pet_id})", custom_id=str(idx)))

                                async def interaction_check(self, interaction: discord.Interaction) -> bool:
                                    return interaction.user.id == self.user_id

                            view = PetChoiceView(close_match_indices, ctx.author.id)
                            await ctx.send(f"Multiple pets match '{pet_identifier}'. Please select one:", view=view)

                            async def wait_for_choice():
                                try:
                                    interaction: discord.Interaction = await bot.wait_for(
                                        "interaction",
                                        check=lambda i: i.user == ctx.author and hasattr(i, 'data') and i.data and "custom_id" in i.data and i.data["custom_id"].isdigit(),
                                        timeout=30
                                    )
                                    selected_index = int(interaction.data.get("custom_id", "0"))
                                    await interaction.response.defer()
                                    
                                    # Now process the update with the selected pet
                                    await process_pet_update(ctx, selected_index, price_type, rarity, price)
                                except asyncio.TimeoutError:
                                    await ctx.send("Timed out. Please try again.")
                                finally:
                                    user_lock[category] = None

                            await wait_for_choice()
                            return

        if index is None:
            await ctx.send(f"❌ No pet found with ID or name `{pet_identifier}`.")
            return

        # Process the update using the helper function
        await process_pet_update(ctx, index, price_type, rarity, price)

    except Exception as e:
        await ctx.send(f"❌ An error occurred: {e}")

    finally:
        user_lock[category] = None

class PetPriceChangeView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="Commit Pet Changes", style=discord.ButtonStyle.success)
    async def commit_changes(self, interaction: discord.Interaction, button: Button):
        global pet_temp_data, pet_original_data, pet_change_history
        await interaction.response.defer(ephemeral=True)
        try:
            content = json.dumps(pet_temp_data, indent=2)
            with open("pet-prices.txt", "w") as f:
                f.write(content)

            sha = get_pet_sha(self.user_id)
            upload_pet_to_github(content, sha, self.user_id)

            # Collect changes for webhook
            changes = []
            id_map = {str(p["petId"]): p for p in pet_original_data}
            
            for pet in pet_temp_data:
                pet_id = str(pet["petId"])
                name = pet.get("name", "")
                original = id_map.get(pet_id)

                if not original:
                    continue  # skip new pets for now

                # Check market prices
                for rarity in ["common", "uncommon", "rare", "epic", "legendary"]:
                    # Market prices
                    old_market = original.get(rarity, 0)
                    new_market = pet.get(rarity, 0)
                    if old_market != new_market:
                        changes.append(f"{pet_id} - {name}: Market {rarity.title()} {old_market} → {new_market}")
                    
                    # NPC prices
                    npc_key = f"n{rarity}"
                    old_npc = original.get(npc_key, 0)
                    new_npc = pet.get(npc_key, 0)
                    if old_npc != new_npc:
                        changes.append(f"{pet_id} - {name}: NPC {rarity.title()} {old_npc} → {new_npc}")

            # Commit the changes
            pet_original_data = copy.deepcopy(pet_temp_data)
            pet_change_history.clear()

            # Send webhook with changes
            if changes:
                embed = discord.Embed(
                    title="🐾 Pet Price Changes Committed",
                    description=f"Changes made by {interaction.user.mention}",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                # Split changes into chunks to avoid embed field limits
                change_chunks = [changes[i:i + 10] for i in range(0, len(changes), 10)]
                for i, chunk in enumerate(change_chunks, 1):
                    embed.add_field(
                        name=f"Changes (Part {i})" if len(change_chunks) > 1 else "Changes",
                        value="\n".join(chunk),
                        inline=False
                    )
                embed.set_footer(text=f"Total changes: {len(changes)}")
                
                try:
                    avatar_url = interaction.client.user.display_avatar.url if interaction.client.user and interaction.client.user.display_avatar else None
                    webhook_data = {
                        "embeds": [embed.to_dict()],
                        "username": "Market Bot"
                    }
                    if avatar_url:
                        webhook_data["avatar_url"] = avatar_url
                    requests.post(webhook_url, json=webhook_data)
                except Exception as webhook_error:
                    print(f"Failed to send webhook: {webhook_error}")

            await interaction.followup.send("✅ Pet market changes committed to GitHub and saved to `pet-prices.txt`.")
        except Exception as e:
            await interaction.followup.send(f"❌ Error committing pet changes: `{e}`")

    @discord.ui.button(label="Undo Last", style=discord.ButtonStyle.danger)
    async def undo_last(self, interaction: discord.Interaction, button: Button):
        global pet_temp_data, pet_change_history
        await interaction.response.defer()
        if pet_change_history:
            pet_temp_data = pet_change_history.pop()
            await interaction.followup.send("🔁 Last pet market change has been undone.")
        else:
            await interaction.followup.send("⚠️ No previous change to undo.")

    @discord.ui.button(label="Undo All", style=discord.ButtonStyle.danger)
    async def undo_all(self, interaction: discord.Interaction, button: Button):
        global pet_temp_data, pet_original_data, pet_change_history
        await interaction.response.defer()
        if pet_change_history:
            pet_temp_data = copy.deepcopy(pet_original_data)
            pet_change_history.clear()
            await interaction.followup.send("🔄 All pet market changes have been undone.")
        else:
            await interaction.followup.send("⚠️ No changes to undo.")

@bot.command(aliases=['spc'])
async def showpetchanges(ctx):
    category = "updatepet"
    if not check_lock(category, ctx.author.id):
        await ctx.send("⚠️ Another user is currently using this command category. Please try again later.")
        return
    user_lock[category] = ctx.author.id

    def format_change(pet_id, name, price_type, rarity, old_val, new_val):
        label = f"{pet_id} - {name}" if name else f"{pet_id}"
        return f"{label}: {price_type.upper()} {rarity.title()} {old_val} → {new_val}"

    diff = ""
    id_map = {str(p["petId"]): p for p in pet_original_data}
    temp_ids = {str(p["petId"]) for p in pet_temp_data}

    for pet in pet_temp_data:
        pet_id = str(pet["petId"])
        name = pet.get("name", "")
        original = id_map.get(pet_id)

        if not original:
            continue  # skip new pets for now

        # Check market prices
        for rarity in ["common", "uncommon", "rare", "epic", "legendary"]:
            # Market prices
            old_market = original.get(rarity, 0)
            new_market = pet.get(rarity, 0)
            if old_market != new_market:
                diff += format_change(pet_id, name, "market", rarity, old_market, new_market) + "\n"
            
            # NPC prices
            npc_key = f"n{rarity}"
            old_npc = original.get(npc_key, 0)
            new_npc = pet.get(npc_key, 0)
            if old_npc != new_npc:
                diff += format_change(pet_id, name, "npc", rarity, old_npc, new_npc) + "\n"

    if not diff:
        diff = "No changes detected in either market or NPC prices."

    user_token = get_user_github_token(ctx.author.id)
    if not user_token:
        await ctx.send("❌ No GitHub token found for this user.")
        user_lock[category] = None
        return

    try:
        get_file_sha(ctx.author.id)
    except Exception as e:
        await ctx.send(f"❌ Error fetching GitHub SHA: {str(e)}")
        user_lock[category] = None
        return

    view = PetPriceChangeView(ctx.author.id)

    if len(diff) > 1900:  # Lower threshold since we're showing more data
        file = discord.File(io.BytesIO(diff.encode('utf-8')), filename="pet_price_changes.txt")
        await ctx.send("Pending pet price changes (market + NPC):", file=file, view=view)
    else:
        await ctx.send(f"**Pending Price Changes**\n```diff\n{diff}```", view=view)

    user_lock[category] = None
    
minion_temp_data = []
minion_change_history = []
minion_original_data = []

def load_minion_prices():
    global minion_original_data, minion_temp_data
    minion_original_data.clear()
    minion_temp_data.clear()
    
    try:
        with open("minion-prices.txt", "r") as f:
            data = json.load(f)
        
        # Ensure all tiers exist for each minion
        file_changed = False
        for minion in data:
            for tier in range(1, 12):
                tier_key = f"tier{tier}"
                if tier_key not in minion["tiers"]:
                    minion["tiers"][tier_key] = [0, 0]
                    file_changed = True
        
        minion_original_data.extend(copy.deepcopy(data))
        minion_temp_data.extend(copy.deepcopy(minion_original_data))
        
        if file_changed:
            with open("minion-prices.txt", "w") as f:
                json.dump(data, f, indent=2)
            try:
                with open("minion-prices.txt", "r") as f:
                    content = f.read()
                sha = get_file_sha_blank()
                upload_to_github_blank(content, sha)
                print("✅ Missing tiers filled and committed to GitHub.")
            except Exception as e:
                print(f"❌ Error committing changes: {e}")
                
    except Exception as e:
        print(f"❌ Error loading minion-prices.txt: {e}")

def load_minion_data():
    with open("minion-prices.txt", "r") as f:
        return json.load(f)

load_minion_prices()

def save_minion_data(data):
    with open("minion-prices.txt", "w") as file:
        json.dump(data, file, indent=4)

@bot.command(aliases=['mu'])
async def updateminion(ctx, minion_id: Optional[int] = None, tier: Optional[str] = None, price_type: Optional[str] = None, price: Optional[int] = None):
    if None in (minion_id, tier, price_type, price):
        await ctx.send("Usage: `.mu <id> <tier> <cost/sell> <price>`\n"
                      "Example: `.mu 1 tier5 cost 13999`")
        return

    category = "updateminion"
    
    if not check_lock(category, ctx.author.id):
        await ctx.send("⚠️ Another user is currently using this command category. Please try again later.")
        return
    user_lock[category] = ctx.author.id

    try:
        # ... (keep your existing validation code)

        # Find the minion
        index = next((i for i, item in enumerate(minion_temp_data)
                    if item.get("minionId") == minion_id), None)

        if index is None:
            await ctx.send(f"❌ No minion found with ID `{minion_id}`.")
            return

        # Get current values
        current_values = minion_temp_data[index]["tiers"][tier]
        current_cost, current_sell = current_values

        # Store the original values before making changes
        original_values = copy.deepcopy(current_values)

        # Determine which value to update
        if price_type == "cost":
            new_values = [price, current_sell]
        else:
            new_values = [current_cost, price]

        # Check if the new price is different
        if new_values == current_values:
            await ctx.send("⚠️ No changes made. The value is the same as the current one.")
            return

        # Record the change in history (store the change, not the entire state)
        change_record = {
            "minion_id": minion_id,
            "tier": tier,
            "price_type": price_type,
            "old_value": original_values[0] if price_type == "cost" else original_values[1],
            "new_value": price,
            "timestamp": datetime.datetime.now().isoformat()
        }
        minion_change_history.append(change_record)
        
        # Update the price in temp data
        minion_temp_data[index]["tiers"][tier] = new_values

        # Validate parameters
        if minion_id is None or tier is None or price_type is None or price is None:
            await ctx.send("❌ All parameters are required.")
            return
            
        await ctx.send(
            f"✅ Updated Minion ID `{minion_id}` **{tier.upper()}** "
            f"**{price_type.upper()}** price to `{price}`."
        )

    except Exception as e:
        await ctx.send(f"❌ An error occurred: {e}")

    finally:
        user_lock[category] = None

@bot.command(aliases=['muc'])
async def showminionchanges(ctx):
    category = "updateminion"
    if not check_lock(category, ctx.author.id):
        await ctx.send("⚠️ Another user is currently using this command category. Please try again later.")
        return
    user_lock[category] = ctx.author.id

    if not minion_change_history:
        await ctx.send("No pending minion price changes.")
        user_lock[category] = None
        return

    # Group changes by minion ID for better display
    changes_by_minion = {}
    for change in minion_change_history:
        if change["minion_id"] not in changes_by_minion:
            changes_by_minion[change["minion_id"]] = []
        changes_by_minion[change["minion_id"]].append(change)

    # Format the changes
    diff = ""
    for minion_id, changes in changes_by_minion.items():
        diff += f"\nMinion ID {minion_id}:\n"
        for change in changes:
            diff += (f"  {change['tier'].upper()} {change['price_type'].upper()}: "
                    f"{change['old_value']} → {change['new_value']}\n")

    # Create and send the view
    view = MinionPriceChangeView(ctx.author.id)
    
    if len(diff) > 1900:
        file = discord.File(io.BytesIO(diff.encode('utf-8')), filename="minion_changes.txt")
        await ctx.send("Pending minion price changes:", file=file, view=view)
    else:
        await ctx.send(f"**Pending Minion Price Changes**```diff{diff}```", view=view)

    user_lock[category] = None

class MinionPriceChangeView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="Commit Changes", style=discord.ButtonStyle.success)
    async def commit_changes(self, interaction: discord.Interaction, button: Button):
        global minion_temp_data, minion_original_data, minion_change_history
        await interaction.response.defer(ephemeral=True)
        try:
            # Save to file
            save_minion_data(minion_temp_data)
            
            # Commit to GitHub
            content = json.dumps(minion_temp_data, indent=2)
            sha = get_minion_sha(self.user_id)
            upload_minion_to_github(content, sha, self.user_id)
            
            # Collect changes for webhook
            changes = []
            for change in minion_change_history:
                changes.append(f"Minion ID {change['minion_id']}: {change['tier'].upper()} {change['price_type'].upper()} {change['old_value']} → {change['new_value']}")
            
            # Update original data and clear history
            minion_original_data = copy.deepcopy(minion_temp_data)
            minion_change_history.clear()
            
            # Send webhook with changes
            if changes:
                embed = discord.Embed(
                    title="⚒️ Minion Price Changes Committed",
                    description=f"Changes made by {interaction.user.mention}",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                # Split changes into chunks to avoid embed field limits
                change_chunks = [changes[i:i + 10] for i in range(0, len(changes), 10)]
                for i, chunk in enumerate(change_chunks, 1):
                    embed.add_field(
                        name=f"Changes (Part {i})" if len(change_chunks) > 1 else "Changes",
                        value="\n".join(chunk),
                        inline=False
                    )
                embed.set_footer(text=f"Total changes: {len(changes)}")
                
                try:
                    avatar_url = interaction.client.user.display_avatar.url if interaction.client.user and interaction.client.user.display_avatar else None
                    webhook_data = {
                        "embeds": [embed.to_dict()],
                        "username": "Market Bot"
                    }
                    if avatar_url:
                        webhook_data["avatar_url"] = avatar_url
                    requests.post(webhook_url, json=webhook_data)
                except Exception as webhook_error:
                    print(f"Failed to send webhook: {webhook_error}")
            
            await interaction.followup.send("✅ All minion price changes committed!")
        except Exception as e:
            await interaction.followup.send(f"❌ Error committing changes: {e}")

    @discord.ui.button(label="Undo Last", style=discord.ButtonStyle.danger)
    async def undo_last(self, interaction: discord.Interaction, button: Button):
        global minion_temp_data, minion_change_history
        await interaction.response.defer()
        if not minion_change_history:
            await interaction.followup.send("⚠️ No changes to undo.")
            return
            
        # Get the last change
        last_change = minion_change_history.pop()
        
        # Find the minion and revert the change
        index = next((i for i, item in enumerate(minion_temp_data)
                    if item.get("minionId") == last_change["minion_id"]), None)
        
        if index is not None:
            tier = last_change["tier"]
            if last_change["price_type"] == "cost":
                minion_temp_data[index]["tiers"][tier][0] = last_change["old_value"]
            else:
                minion_temp_data[index]["tiers"][tier][1] = last_change["old_value"]
        
        await interaction.followup.send(f"✅ Undid last change for Minion ID {last_change['minion_id']}")

    @discord.ui.button(label="Undo All", style=discord.ButtonStyle.danger)
    async def undo_all(self, interaction: discord.Interaction, button: Button):
        global minion_temp_data, minion_original_data, minion_change_history
        await interaction.response.defer()
        
        # Revert all changes
        minion_temp_data = copy.deepcopy(minion_original_data)
        minion_change_history.clear()
        
        await interaction.followup.send("✅ All minion price changes have been reverted!")
        
minion_market_original = []
minion_market_temp = []
minion_market_history = []

def load_minion_market_data():
    with open("minions.txt", "r") as f:
        return json.load(f)

def save_minion_market_data(data):
    with open("minions.txt", "w") as f:
        json.dump(data, f, indent=4)

def initialize_minion_market_data():
    global minion_market_original, minion_market_temp
    minion_market_original = load_minion_market_data()
    minion_market_temp = copy.deepcopy(minion_market_original)

async def update_minion_market_entry(ctx, args=None):
    if args is None:
        await ctx.send("Usage: `.umm <minion> [nature] [demand]`\n"
                      "Example: `.umm cobblestone stable 9`")
        return

    parts = args.split()
    nature = demand = None

    if parts:
        last = parts[-1]
        if last.isdigit() or "/10" in last:
            demand = parts.pop()
            if "/" not in demand:
                demand = f"{demand}/10"

    if parts:
        potential_nature = parts[-1]
        if not potential_nature.isdigit() and "/10" not in potential_nature:
            nature = parts.pop().upper()

    if not parts:
        await ctx.send("❌ Could not parse item name. Please try again.")
        return

    identifier = expand_abbreviations(" ".join(parts).lower().strip())
    if nature:
        nature = expand_abbreviations(nature.lower())
    if demand:
        demand = expand_abbreviations(demand.lower())

    matches = [
        (i, item) for i, item in enumerate(minion_market_temp)
        if identifier in expand_abbreviations(item['name'].lower()) or str(item['id']) == identifier
    ]

    if not matches:
        expanded_names = [expand_abbreviations(item['name'].lower()) for item in minion_market_temp]
        close = get_close_matches(identifier, expanded_names, n=3, cutoff=0.5)
        if not close:
            await ctx.send("❌ No matches found.")
            return
        elif len(close) > 1:
            await ctx.send(f"Multiple items match '{identifier}': {', '.join(close)}. Please be more specific.")
            return

        matches = [
            (i, item) for i, item in enumerate(minion_market_temp)
            if expand_abbreviations(item['name'].lower()) in close
        ]

    async def apply_update(index: int):
        minion_market_history.append(copy.deepcopy(minion_market_temp))
        updates = []
        if nature is not None:
            minion_market_temp[index]['nature'] = f"[{nature}]"
            updates.append(f"nature **[{nature}]**")
        if demand is not None:
            minion_market_temp[index]['demand'] = f"[{demand}]"
            updates.append(f"demand **[{demand}]**")
        
        updated_item = minion_market_temp[index]
        changes_msg = " and ".join(updates) if updates else "no changes"
        await ctx.send(f"✅ Updated **{updated_item['name']}** with {changes_msg}.")

    if len(matches) > 1:
        class ChoiceView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                for idx, item in matches:
                    self.add_item(ChoiceButton(item, idx))

        class ChoiceButton(discord.ui.Button):
            def __init__(self, item, index):
                super().__init__(
                    label=f"{item['name']} ({item['id']})",
                    style=discord.ButtonStyle.primary
                )
                self.index = index
            
            async def callback(self, interaction: discord.Interaction):
                await interaction.response.defer()
                await apply_update(self.index)
                if self.view:
                    self.view.stop()

        view = ChoiceView()
        await ctx.send("🔍 Multiple items found. Select one:", view=view)
    else:
        index, _ = matches[0]
        await apply_update(index)

@bot.command(aliases=['umm'])
async def updateminionmarket(ctx, *, args=None):
    """Update an item in the minions"""
    await update_minion_market_entry(ctx, args)

class MinionMarketChangeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Commit Changes", style=discord.ButtonStyle.success)
    async def commit_changes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if minion_market_temp != minion_market_original:
            user_id = interaction.user.id
            save_minion_market_data(minion_market_temp)
            minion_market_original[:] = load_minion_market_data()
            minion_market_temp[:] = copy.deepcopy(minion_market_original)
            content = json.dumps(minion_market_temp, indent=4)
            sha = get_minion_market_sha(user_id)
            upload_minion_market_to_github(content, sha, user_id)
            
            # Collect changes for webhook
            changes = []
            for temp_item, orig_item in zip(minion_market_temp, minion_market_original):
                item_changes = []
                for key in ['name', 'price', 'nature', 'demand']:
                    if temp_item.get(key) != orig_item.get(key):
                        item_changes.append(f"{key}: {orig_item.get(key, 'N/A')} → {temp_item.get(key, 'N/A')}")
                if item_changes:
                    changes.append(f"{orig_item['name']} ({orig_item['id']}):\n  " + "\n  ".join(item_changes))
            
            minion_market_history.clear()
            
            # Send webhook with changes
            if changes:
                embed = discord.Embed(
                    title="⚒️ Minion Market Changes Committed",
                    description=f"Changes made by {interaction.user.mention}",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                # Split changes into chunks to avoid embed field limits
                change_chunks = [changes[i:i + 10] for i in range(0, len(changes), 10)]
                for i, chunk in enumerate(change_chunks, 1):
                    embed.add_field(
                        name=f"Changes (Part {i})" if len(change_chunks) > 1 else "Changes",
                        value="\n".join(chunk),
                        inline=False
                    )
                embed.set_footer(text=f"Total changes: {len(changes)}")
                
                try:
                    avatar_url = interaction.client.user.display_avatar.url if interaction.client.user and interaction.client.user.display_avatar else None
                    webhook_data = {
                        "embeds": [embed.to_dict()],
                        "username": "Market Bot"
                    }
                    if avatar_url:
                        webhook_data["avatar_url"] = avatar_url
                    requests.post(webhook_url, json=webhook_data)
                except Exception as webhook_error:
                    print(f"Failed to send webhook: {webhook_error}")
            
            await interaction.followup.send("✅ Minion changes committed and temporary edits cleared.")
        else:
            await interaction.followup.send("ℹ️ No Minion changes to commit.")

    @discord.ui.button(label="Undo Last", style=discord.ButtonStyle.danger)
    async def undo_last(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if minion_market_history:
            minion_market_temp[:] = minion_market_history.pop()
            await interaction.followup.send("↩️ Last minion change undone.")
        else:
            await interaction.followup.send("ℹ️ No minion changes to undo.")

    @discord.ui.button(label="Undo All", style=discord.ButtonStyle.danger)
    async def undo_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        minion_market_temp[:] = load_minion_market_data()
        minion_market_original[:] = copy.deepcopy(minion_market_temp)
        minion_market_history.clear()
        await interaction.followup.send("🔄 All minion changes undone.")

@bot.command(aliases=['smmc'])
async def showminionmarketchanges(ctx):
    """Show pending minion changes"""
    diff = ""
    for temp_item, orig_item in zip(minion_market_temp, minion_market_original):
        changes = [
            f"{key}: {orig_item.get(key, '')} → {temp_item.get(key, '')}"
            for key in ['name', 'price', 'nature', 'demand']
            if temp_item.get(key) != orig_item.get(key)
        ]
        if changes:
            diff += f"{orig_item['name']} ({orig_item['id']}):\n  " + "\n  ".join(changes) + "\n\n"

    view = MinionMarketChangeView()
    if not diff:
        diff = "No market changes."

    if len(diff) > 1900:
        file = discord.File(io.BytesIO(diff.encode('utf-8')), filename="minions_diff.txt")
        await ctx.send("Here are the pending minion changes:", file=file, view=view)
    else:
        await ctx.send(f"```diff\n{diff}```", view=view)


    
def get_user_github_token(user_id):
    """Fetches the GitHub token for the user based on their ID."""
    return USER_GITHUB_TOKENS.get(user_id)

def get_file_sha(user_id):
    """Get the SHA of the file using the user's GitHub token."""
    token = get_user_github_token(user_id)
    if not token:
        raise ValueError("No GitHub token found for this user.")

    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()["sha"]

def get_market_sha(user_id):
    """Get the SHA of the market file using the user's GitHub token."""
    token = get_user_github_token(user_id)
    if not token:
        raise ValueError("No GitHub token found for this user.")

    url = f"https://api.github.com/repos/{REPO}/contents/{MARKET_FILE_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()["sha"]

def get_minion_market_sha(user_id):
    """Get the SHA of the minions file using the user's GitHub token."""
    token = get_user_github_token(user_id)
    if not token:
        raise ValueError("No GitHub token found for this user.")

    url = f"https://api.github.com/repos/{REPO}/contents/{MINION_MARKET_FILE_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()["sha"]

def get_pet_sha(user_id):
    """Get the SHA of the pet-prices file using the user's GitHub token."""
    token = get_user_github_token(user_id)
    if not token:
        raise ValueError("No GitHub token found for this user.")

    url = f"https://api.github.com/repos/{REPO}/contents/{PET_FILE_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()["sha"]

def get_pet_market_sha(user_id):
    """Get the SHA of the pet file using the user's GitHub token."""
    token = get_user_github_token(user_id)
    if not token:
        raise ValueError("No GitHub token found for this user.")

    url = f"https://api.github.com/repos/{REPO}/contents/{PET_MARKET_FILE_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()["sha"]

def get_minion_sha(user_id):
    """Get the SHA of the minion file using the user's GitHub token."""
    token = get_user_github_token(user_id)
    if not token:
        raise ValueError("No GitHub token found for this user.")

    url = f"https://api.github.com/repos/{REPO}/contents/{MINION_FILE_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()["sha"]

def get_file_sha_blank():
    """Get the SHA of the file using the user's GitHub token."""
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()["sha"]

def upload_to_github_blank(content, sha):
    """Upload content to GitHub using the user's GitHub token."""
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "message": "Updated mprices.txt via Discord bot",
        "content": base64.b64encode(content.encode()).decode(),
        "sha": sha
    }
    r = requests.put(url, headers=headers, json=payload)
    r.raise_for_status()
    
def upload_to_github(content, sha, user_id):
    """Upload content to GitHub using the user's GitHub token."""
    token = get_user_github_token(user_id)
    if not token:
        raise ValueError("No GitHub token found for this user.")

    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "message": "Updated mprices.txt via Discord bot",
        "content": base64.b64encode(content.encode()).decode(),
        "sha": sha
    }
    r = requests.put(url, headers=headers, json=payload)
    r.raise_for_status()


def upload_market_to_github(market_content, market_sha, user_id):
    """Upload content to the market file on GitHub using the user's GitHub token."""
    token = get_user_github_token(user_id)
    if not token:
        raise ValueError("No GitHub token found for this user.")

    url = f"https://api.github.com/repos/{REPO}/contents/{MARKET_FILE_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "message": "Updated market.txt via Discord bot",
        "content": base64.b64encode(market_content.encode()).decode(),
        "sha": market_sha
    }
    r = requests.put(url, headers=headers, json=payload)
    r.raise_for_status()
    
def upload_minion_market_to_github(content, sha, user_id):
    """Upload content to the minions file on GitHub using the user's GitHub token."""
    token = get_user_github_token(user_id)
    if not token:
        raise ValueError("No GitHub token found for this user.")

    url = f"https://api.github.com/repos/{REPO}/contents/{MINION_MARKET_FILE_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "message": "Updated minions.txt via Discord bot",
        "content": base64.b64encode(content.encode()).decode(),
        "sha": sha
    }
    r = requests.put(url, headers=headers, json=payload)
    r.raise_for_status()

def upload_pet_to_github(content, sha, user_id):
    """Upload content to the market file on GitHub using the user's GitHub token."""
    token = get_user_github_token(user_id)
    if not token:
        raise ValueError("No GitHub token found for this user.")

    url = f"https://api.github.com/repos/{REPO}/contents/{PET_FILE_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "message": "Updated pet-prices.txt via Discord bot",
        "content": base64.b64encode(content.encode()).decode(),
        "sha": sha
    }
    r = requests.put(url, headers=headers, json=payload)
    r.raise_for_status()
    
def upload_pet_market_to_github(pet_content, pet_sha, user_id):
    """Upload content to the market file on GitHub using the user's GitHub token."""
    token = get_user_github_token(user_id)
    if not token:
        raise ValueError("No GitHub token found for this user.")

    url = f"https://api.github.com/repos/{REPO}/contents/{PET_MARKET_FILE_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "message": "Updated pets.txt via Discord bot",
        "content": base64.b64encode(pet_content.encode()).decode(),
        "sha": pet_sha
    }
    r = requests.put(url, headers=headers, json=payload)
    r.raise_for_status()
    
def upload_minion_to_github(content, sha, user_id):
    """Upload content to the minion file on GitHub using the user's GitHub token."""
    token = get_user_github_token(user_id)
    if not token:
        raise ValueError("No GitHub token found for this user.")

    url = f"https://api.github.com/repos/{REPO}/contents/{MINION_FILE_PATH}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "message": "Updated minion-prices.txt via Discord bot",
        "content": base64.b64encode(content.encode()).decode(),
        "sha": sha
    }
    r = requests.put(url, headers=headers, json=payload)
    r.raise_for_status()

def download_from_github():
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    content = base64.b64decode(response.json()['content']).decode()

    with open("mprices.txt", "w") as f:
        f.write(content)

def download_market_from_github():
    url = f"https://api.github.com/repos/{REPO}/contents/{MARKET_FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    market_content = base64.b64decode(response.json()['content']).decode()

    with open("market.txt", "w") as f:
        f.write(market_content)
        
def download_minion_market_from_github():
    url = f"https://api.github.com/repos/{REPO}/contents/{MINION_MARKET_FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    content = base64.b64decode(response.json()['content']).decode()

    with open("minions.txt", "w") as f:
        f.write(content)
        
def download_pet_from_github():
    url = f"https://api.github.com/repos/{REPO}/contents/{PET_FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    content = base64.b64decode(response.json()['content']).decode()

    with open("pet-prices.txt", "w") as f:
        f.write(content)
        
def download_pet_market_from_github():
    url = f"https://api.github.com/repos/{REPO}/contents/{PET_MARKET_FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    pet_content = base64.b64decode(response.json()['content']).decode()

    with open("pets.txt", "w") as f:
        f.write(pet_content)
        
def download_minion_from_github():
    url = f"https://api.github.com/repos/{REPO}/contents/{MINION_FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    content = base64.b64decode(response.json()['content']).decode()

    with open("minion-prices.txt", "w") as f:
        f.write(content)

@tasks.loop(minutes=5)
async def sync_prices_from_github():
    print("Syncing prices from GitHub...")
    try:
        download_from_github()
        load_file()
        print("Successfully synced mprices.txt from GitHub.")
    except Exception as e:
        print(f"Failed to sync: {e}")

@tasks.loop(minutes=5)
async def sync_market_from_github():
    print("Syncing market.txt from GitHub...")
    try:
        download_market_from_github()
        global market_temp
        market_temp = load_market_data()
        print("Successfully synced market.txt from GitHub.")
    except Exception as e:
        print(f"Failed to sync market.txt: {e}")
        
@tasks.loop(minutes=5)
async def sync_minion_market_from_github():
    print("Syncing minions.txt from GitHub...")
    try:
        download_minion_market_from_github()
        global minion_market_temp
        minion_market_temp = load_minion_market_data()
        print("Successfully synced minions.txt from GitHub.")
    except Exception as e:
        print(f"Failed to sync minions.txt: {e}")
        
@tasks.loop(minutes=5)
async def sync_pet_from_github():
    print("Syncing pet-prices.txt from GitHub...")
    try:
        download_pet_from_github()
        global pet_temp
        pet_temp = load_pet_data()
        print("Successfully synced pet-prices.txt from GitHub.")
    except Exception as e:
        print(f"Failed to sync pet-prices.txt: {e}")
        
@tasks.loop(minutes=5)
async def sync_pet_market_from_github():
    print("Syncing pets.txt from GitHub...")
    try:
        download_pet_market_from_github()
        global pet_market_temp
        pet_market_temp = load_pet_market_data()
        print("✅ Successfully synced pets.txt from GitHub.")
    except Exception as e:
        print(f"❌ Failed to sync pets.txt: {e}")
        
@tasks.loop(minutes=5)
async def sync_minion_from_github():
    print("Syncing minion-prices.txt from GitHub...")
    try:
        download_minion_from_github()
        global minion_temp_data
        minion_temp_data = load_minion_data()
        print("✅ Successfully synced minion-prices.txt from GitHub.")
    except Exception as e:
        print(f"❌ Failed to sync minion-prices.txt: {e}")

        
bot.remove_command('help')

@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="🛒 Market Commands Help",
        description="Below are the available market-related commands and their usage:",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="🔧 `.up <item> <bz-price> <npc-price>`",
        value="Update the bz and npc price of a market item.\nExample: `.up stick 5 2`\nIt is used for updating both Bazaar and NPC price or only Bazaar price.",
        inline=False
    )
    
    embed.add_field(
        name="🧾 `.un <item> <npc-price>`",
        value="Update the npc price of a market item.\nExample: `.un stick 2`\nIt is only used for updating NPC price.",
        inline=False
    )

    embed.add_field(
        name="📄 `.sc`",
        value="Show pending changes made via `.up` and `.un` before committing.",
        inline=False
    )

    embed.add_field(
        name="🔁 `.um <item> [nature] [demand]`",
        value="Update the nature 'overpaid/stable/underpaid' and/or demand '1-10' of a market item.\nExample: `.um stick stable 9`",
        inline=False
    )
    
    embed.add_field(
        name="🔁 `.upm <petid/name> [nature] [demand]`",
        value="Update the nature 'overpaid/stable/underpaid' and/or demand '1-10' of a pets.\nExample: `.upm elephant stable 9`",
        inline=False
    )

    embed.add_field(
        name="📋 `.smc`",
        value="Show all pending changes made via `.um` and `.upm`. You can then **commit** or **undo** changes via buttons.",
        inline=False
    )
    
    embed.add_field(
        name="🔁 `.pu <id/name> <market/npc> <rarity> <price>`",
        value="Update the pet's different rarity prices.\nExample: `.pu 1 market rare 13999`",
        inline=False
    )

    embed.add_field(
        name="📋 `.spc`",
        value="Show all pending changes made via `.pu`. You can then **commit** or **undo** changes via buttons.",
        inline=False
    )
    
    embed.add_field(
        name="🔁 `.mu <id> <tier> <cost/sell> <price>`",
        value="Update the minions's different tier prices.\nExample: `.mu 1 tier5 cost 13999`",
        inline=False
    )

    embed.add_field(
        name="📋 `.muc`",
        value="Show all pending changes made via `.mu`. You can then **commit** or **undo** changes via buttons.",
        inline=False
    )
    
    embed.add_field(
        name="🔁 `.umm <minion> [nature] [demand]`",
        value="Update the nature 'overpaid/stable/underpaid' and/or demand '1-10' of a minion.\nExample: `.um cobblestone stable 9`",
        inline=False
    )

    embed.add_field(
        name="📋 `.smmc`",
        value="Show all pending changes made via `.umm`. You can then **commit** or **undo** changes via buttons.",
        inline=False
    )
    
    embed.add_field(
        name="🔁 `.sync`",
        value="Downloads `mprices.txt` `market.txt` `pets.txt`, `pet-prices.txt`, `minions.txt` and `minion-prices.txt` from github to sync the bot with latest data.",
        inline=False
    )

    embed.add_field(
        name="🔐 GitHub Access Required",
        value=(
            "If you're using any of these commands, you **must provide your personal GitHub access token** "
            "with `repo` (full repository control) privileges.\n"
            "This is necessary so the bot can commit changes under your account securely."
        ),
        inline=False
    )

    embed.add_field(
        name="👨‍💻 Bot Developers",
        value=(
            "If the bot breaks or behaves unexpectedly, please contact or ping:\n"
            "<@947868777528307742> or <@783972385882767400>"
        ),
        inline=False
    )

    embed.set_footer(text="Use these commands responsibly. All actions are logged.")

    await ctx.send(embed=embed)

    
AUTHORIZED_UNLOCK_ROLES = [1320729567652085780, 1356267415134011502, 1361716492479107132]

@bot.check
async def global_command_check(ctx):
    # Only allow users whose IDs are in USER_GITHUB_TOKENS
    return ctx.author.id in USER_GITHUB_TOKENS

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("🚫 You are not authorized to use this bot.")
    else:
        raise error
    
@bot.command()
async def sync(ctx):
    await ctx.send("🔄 Syncing files from GitHub...")

    try:
        print("Syncing prices from GitHub...")
        download_from_github()
        load_file()
        print("Successfully synced mprices.txt from GitHub.")

        print("Syncing market.txt from GitHub...")
        download_market_from_github()
        global market_temp
        market_temp = load_market_data()
        print("Successfully synced market.txt from GitHub.")
        
        print("Syncing minions.txt from GitHub...")
        download_minion_market_from_github()
        global minion_market_temp
        minion_market_temp = load_minion_market_data()
        print("Successfully synced minions.txt from GitHub.")
        
        print("Syncing pet-prices.txt from GitHub...")
        download_pet_from_github()
        global pet_temp
        pet_temp = load_pet_data()
        print("Successfully synced pet-prices.txt from GitHub.")
        
        print("Syncing pets.txt from GitHub...")
        download_pet_market_from_github()
        global pet_market_temp
        pet_market_temp = load_pet_market_data()
        print("Successfully synced pets.txt from GitHub.")
        
        print("Syncing minion-prices.txt from GitHub...")
        download_minion_from_github()
        global minion_temp_data
        minion_temp_data = load_minion_data()
        print("Successfully synced minion-prices.txt from GitHub.")

        await ctx.send("✅ Synced `mprices.txt`, `market.txt`, `pets.txt`, `pet-prices.txt`, `minions.txt` and `minion-prices.txt` from GitHub.")
    except Exception as e:
        print(f"Sync failed: {e}")
        await ctx.send(f"❌ Sync failed: `{type(e).__name__}: {e}`")

@bot.event
async def on_ready():
    load_file()
    initialize_data()
    initialize_minion_market_data()
    load_pet_prices()
    sync_prices_from_github.start()
    sync_market_from_github.start()
    sync_minion_market_from_github.start()
    sync_pet_from_github.start()
    sync_pet_market_from_github.start()
    sync_minion_from_github.start()
    print(f"Bot is ready as {bot.user}")
    print(f"Version: v11")

bot.run(TOKEN)
