import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import copy
import json
import base64
import requests
import io
import math
import asyncio
from collections import defaultdict
from difflib import get_close_matches

USER_GITHUB_TOKENS = {
    947868777528307742: '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',  # PG
    1334835742047731733: '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', #Sagnik with Main acc token
    #1032668335135019029: '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', #Ghosty with Main acc token
    845690488752832522: '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',  # Aakash
    783972385882767400: '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', # dev
    992284684425904168: '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',  # SAMA
    1099047739209293944: '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', # techon
    909654814651195423: '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', # dipanshu with main acc token
    878545726014107698: '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', # edu with main acc token
    1090560686083559545: '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', # Promanhlo with main acc token
    931065234762907668: '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', # CRAFTER32ON with main acc token
}

GITHUB_TOKEN = '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'

TOKEN = 'MTM1OTQ4Njc3MjM2NjY3MjAyMg.GNnFP5.MzwGW0qOss4baLDS-ePP0GFmNxk-4vgDvT8ipM'
REPO = 'CraftersMC-Guides-Project/guides-code'
FILE_PATH = 'market/mprices.txt'
MARKET_FILE_PATH = 'market/market.txt'
PET_FILE_PATH = 'market/pet-prices.txt'
PET_MARKET_FILE_PATH = 'market/pets.txt'

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='.', intents=intents)

original_data = []
temp_data = []
change_history = []

def load_market_data():
    with open("market.txt", "r") as file:
        return json.load(file)

def save_market_data(data):
    with open("market.txt", "w") as file:
        json.dump(data, file, indent=4)

market_temp = load_market_data()

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
    "op": "OVERPRICED",
    "up": "UNDERPRICED",
    "st": "STABLE",
}

def expand_abbreviations(text):
    words = text.lower().split()
    expanded = [ABBREVIATIONS.get(w, w) for w in words]
    return " ".join(expanded)

user_lock = defaultdict(lambda: None)

def check_lock(command_category, user_id):
    if user_lock[command_category] is None or user_lock[command_category] == user_id:
        return True
    return False

# Command to update price
@bot.command(aliases=['up'])
async def updateprice(ctx, *, args):
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
        await ctx.send("Usage: `.updateprice <index or item name> <user_price> <npc_price>`")
        user_lock[category] = None
        return

    def update_item(index):
        change_history.append(copy.deepcopy(temp_data))
        temp_data[index][1] = user_price
        if npc_price is not None:
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
                    check=lambda i: i.user == ctx.author and i.data["custom_id"].isdigit(),
                    timeout=30
                )
                index = int(interaction.data["custom_id"])
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

                    change_history.append(copy.deepcopy(temp_data))
                    temp_data[index][1] = user_price_local
                    if npc_price_local is not None:
                        if len(temp_data[index]) > 2:
                            temp_data[index][2] = npc_price_local
                        else:
                            temp_data[index].append(npc_price_local)

                    npc_display = f"{npc_price_local}" if npc_price_local is not None else "(unchanged)"
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
async def updatenpc(ctx, *, args):
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
        await ctx.send("Usage: `.updatenpc <index or item name> <npc_price>`")
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
                    check=lambda i: i.user == ctx.author and i.data["custom_id"].isdigit(),
                    timeout=30
                )
                index = int(interaction.data["custom_id"])
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
            content = ""
            for i, item in enumerate(temp_data, start=1):
                name = item[0]
                user_price = item[1] if item[1] is not None else "0"
                npc_price = item[2] if len(item) > 2 and item[2] is not None else "0"
                content += f'{i}: ["{name}", {user_price}, {npc_price}]\n'

            with open("mprices.txt", "w") as f:
                f.write(content)

            sha = get_file_sha(user_id)
            upload_to_github(content, sha, user_id)
            load_file()

            await interaction.followup.send("✅ Changes committed to GitHub and saved to `mprices.txt`.")
        except Exception as e:
            await interaction.followup.send(f"❌ Error committing changes: `{e}`")

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
        file = discord.File(io.StringIO(diff), filename="diff.txt")
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

def expand_abbreviations(text: str) -> str:
    ABBREVIATIONS = {
        "op": "OVERPRICE",
        "st": "STABLE",
        "up": "UNDERPRICE",
    }
    text = text.lower()
    return ABBREVIATIONS.get(text, text)

async def update_entry(ctx, args, data_temp, data_history, filetype: str):
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
            return interaction.user == ctx.author and interaction.data['custom_id'].isdigit()

        try:
            interaction = await bot.wait_for("interaction", check=check, timeout=30)
            await interaction.response.defer()
            await apply_update(int(interaction.data['custom_id']))
        except asyncio.TimeoutError:
            await ctx.send("⏱️ Selection timed out.")
    else:
        index, _ = matches[0]
        await apply_update(index)

@bot.command(aliases=['um'])
async def updatemarket(ctx, *, args):
    await update_entry(ctx, args, market_temp, market_history, "market")

@bot.command(aliases=['upm'])
async def updatepet_marketmarket(ctx, *, args):
    await update_entry(ctx, args, pet_market_temp, pet_market_history, "pets")

class MarketChangeView(View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Commit Changes", style=discord.ButtonStyle.success, custom_id="commit_market")
    async def commit_changes(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user_id = interaction.user.id
            committed = []
    
            # Check for changes in market
            if market_temp != market_original:
                market_content = json.dumps(market_temp, indent=4)
                with open("market.txt", "w") as f:
                    f.write(market_content)
    
                market_sha = get_market_sha(user_id)
                upload_market_to_github(market_content, market_sha, user_id)
                committed.append("Market")
    
            # Check for changes in pets
            if pet_market_temp != pet_market_original:
                pet_content = json.dumps(pet_market_temp, indent=4)
                with open("pets.txt", "w") as f:
                    f.write(pet_content)
    
                pet_sha = get_pet_market_sha(user_id)
                upload_pet_market_to_github(pet_content, pet_sha, user_id)
                committed.append("Pets")
    
            # Reload and clear only if something was committed
            if committed:
                market_temp[:] = load_market_data()
                pet_market_temp[:] = load_pet_market_data()
                market_history.clear()
                pet_market_history.clear()
                await interaction.response.send_message(f"✅ Committed changes to: {', '.join(committed)}. Temporary edits cleared.")
            else:
                await interaction.response.send_message("ℹ️ No changes to commit.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error committing changes: `{e}`")
    
    @discord.ui.button(label="Undo Last", style=discord.ButtonStyle.danger, custom_id="undo_last")
    async def undo_last(self, interaction: discord.Interaction, button: discord.ui.Button):
        if market_history:
            market_temp[:] = market_history.pop()
        if pet_market_history:
            pet_market_temp[:] = pet_market_history.pop()
        await interaction.response.send_message("↩️ Last change undone.")

    @discord.ui.button(label="Undo All", style=discord.ButtonStyle.danger, custom_id="undo_all")
    async def undo_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        market_temp[:] = load_market_data()
        pet_market_temp[:] = load_pet_market_data()
        market_history.clear()
        pet_market_history.clear()
        await interaction.response.send_message("🔄 All changes undone.")

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
        file = discord.File(io.StringIO(diff), filename="market_diff.txt")
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


@bot.command(aliases=['pu'])
async def updatepet(ctx, pet_identifier: str, price_type: str, rarity: str, price: float):
    """
    Updates pet prices (market or NPC).
    Usage: 
      !updatepet <pet_id/name> <market/npc> <rarity> <price>
    Example:
      !updatepet 1 market common 100    (Updates market price)
      !updatepet "Silverfish" npc rare 50  (Updates NPC price)
    """
    category = "updatepet"
    
    if not check_lock(category, ctx.author.id):
        await ctx.send("⚠️ Another user is currently using this command category. Please try again later.")
        return
    user_lock[category] = ctx.author.id

    try:
        # Validate price type
        price_type = price_type.lower()
        if price_type not in {"market", "npc"}:
            await ctx.send("❌ Invalid price type. Use `market` or `npc`.")
            return

        # Validate rarity
        rarity = rarity.lower()
        valid_rarities = {"common", "uncommon", "rare", "epic", "legendary"}
        if rarity not in valid_rarities:
            await ctx.send("❌ Invalid rarity. Choose from: common, uncommon, rare, epic, legendary")
            return

        # Find the pet
        index = None
        if pet_identifier.isdigit():
            index = next((i for i, item in enumerate(pet_temp_data)
                        if str(item.get("petId")) == pet_identifier), None)
        else:
            lower_name = pet_identifier.lower()
            index = next((i for i, item in enumerate(pet_temp_data)
                        if item.get("name", "").lower() == lower_name), None)

        if index is None:
            await ctx.send(f"❌ No pet found with ID or name `{pet_identifier}`.")
            return

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

            # Commit the changes
            pet_original_data = copy.deepcopy(pet_temp_data)
            pet_change_history.clear()

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

    def format_change(pet_id, name, rarity, old_val, new_val):
        label = f"{pet_id} - {name}" if name else f"{pet_id}"
        return f"{label}: {rarity.title()} {old_val} → {new_val}"

    diff = ""
    id_map = {str(p["petId"]): p for p in pet_original_data}
    temp_ids = {str(p["petId"]) for p in pet_temp_data}

    for pet in pet_temp_data:
        pet_id = str(pet["petId"])
        name = pet.get("name", "")
        original = id_map.get(pet_id)

        if not original:
            continue  # skip new pets for now

        for rarity in ["common", "uncommon", "rare", "epic", "legendary"]:
            old_val = original.get(rarity, 0)
            new_val = pet.get(rarity, 0)
            if old_val != new_val:
                diff += format_change(pet_id, name, rarity, old_val, new_val) + "\n"

    if not diff:
        diff = "No changes."

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

    if len(diff) > 3900:
        file = discord.File(io.StringIO(diff), filename="pet_diff.txt")
        await ctx.send("Here are the pending pet market changes:", file=file, view=view)
    else:
        await ctx.send(f"```diff\n{diff}```", view=view)

    user_lock[category] = None

    
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
        name="🔁 `.pu <id> <rarity> <price>`",
        value="Update the pet's different rarity prices.\nExample: `.pu 1 rare 13999`",
        inline=False
    )

    embed.add_field(
        name="📋 `.spc`",
        value="Show all pending changes made via `.pu`. You can then **commit** or **undo** changes via buttons.",
        inline=False
    )
    
    embed.add_field(
        name="🔁 `.sync`",
        value="Downloads `mprices.txt` `market.txt` `pets.txt` and `pet-prices.txt` from github to sync the bot with latest data.",
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

    
AUTHORIZED_UNLOCK_USERS = [78397238588276740, 947868777528307742, 845690488752832522, 992284684425904168, 1090560686083559545, 931065234762907668]  # Add allowed user IDs here

@bot.command()
async def unlock(ctx, category: str):
    if ctx.author.id not in AUTHORIZED_UNLOCK_USERS:
        await ctx.send("❌ You are not authorized to use this command.")
        return

    if category not in user_lock:
        await ctx.send("⚠️ Invalid category.")
        return

    user_lock[category] = None
    await ctx.send(f"🔓 The `{category}` command lock has been cleared.")
    
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

        await ctx.send("✅ Synced `mprices.txt`, `market.txt`, `pets.txt` and `pet-prices.txt` from GitHub.")
    except Exception as e:
        print(f"Sync failed: {e}")
        await ctx.send(f"❌ Sync failed: `{type(e).__name__}: {e}`")


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


@bot.event
async def on_ready():
    load_file()
    initialize_data()
    load_pet_prices()
    sync_prices_from_github.start()
    sync_market_from_github.start()
    sync_pet_from_github.start()
    sync_pet_market_from_github.start()
    print(f"Bot is ready as {bot.user}")

bot.run(TOKEN)