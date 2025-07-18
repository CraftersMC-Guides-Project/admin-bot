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

TOKEN = 'MTM1OTQ4Njc3MjM2NjY3MjAyMg.GNnFP5.MzwGW0qOss4baLDS-ePP0GFmNxk-4vgDvT8ipM'
BUG_REPORT_CHANNEL_ID = 1361692561198153971
BUG_REPORT_ADMIN_CHANNEL_ID = 1368205816573853796
BUG_REPORT_QUEUE_CHANNEL_ID = 1368206019922100257
BUG_REPORT_ARCHIVE_CHANNEL_ID = 1368207149758418994

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='-', intents=intents)

report_cooldown = {}
SPAM_LIMIT = 3
SPAM_WINDOW = 60

class BugReportReviewView(View):
    def __init__(self, reporter_id, report_data):
        super().__init__(timeout=None)
        self.reporter_id = reporter_id
        self.report_data = report_data

    async def disable_all_buttons(self, interaction, status):
        for item in self.children:
            item.disabled = True
        embed = interaction.message.embeds[0]
        embed.title = f"Bug Report ({status})"
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="bug_report_accept")
    async def accept_report(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await self.disable_all_buttons(interaction, "Accepted")
        
        queue_channel = bot.get_channel(BUG_REPORT_QUEUE_CHANNEL_ID)
        embed = discord.Embed(
            title=f"Bug Report (Accepted)",
            description=self.report_data['description'],
            color=discord.Color.green()
        )
        embed.set_author(name=f"Reported by {self.report_data['reporter']['discord_username']} ({self.report_data['reporter']['in_game_name']})")
        await queue_channel.send(embed=embed)

        try:
            user = await bot.fetch_user(int(self.report_data['reporter']['discord_id']))
            embed = discord.Embed(
                title="Bug Report Accepted",
                description="Your report has been accepted and added to our queue.",
                color=discord.Color.green()
            )
            embed.add_field(name="Details", value=self.report_data['description'])
            await user.send(embed=embed)
        except:
            pass

        archive_channel = bot.get_channel(BUG_REPORT_ARCHIVE_CHANNEL_ID)
        await archive_channel.send(embed=interaction.message.embeds[0])

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="bug_report_reject")
    async def reject_report(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await self.disable_all_buttons(interaction, "Rejected")

        try:
            user = await bot.fetch_user(int(self.report_data['reporter']['discord_id']))
            embed = discord.Embed(
                title="Bug Report Reviewed",
                description="Your report was reviewed but not accepted.",
                color=discord.Color.red()
            )
            embed.add_field(name="Details", value=self.report_data['description'])
            await user.send(embed=embed)
        except:
            pass

        archive_channel = bot.get_channel(BUG_REPORT_ARCHIVE_CHANNEL_ID)
        await archive_channel.send(embed=interaction.message.embeds[0])

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    
    if message.channel.id == BUG_REPORT_CHANNEL_ID and message.webhook_id:
        try:
            report_data = json.loads(message.content)
            
            if report_data.get('type') == 'bug_report':
                reporter_id = int(report_data['reporter']['discord_id'])
                
                current_time = asyncio.get_event_loop().time()
                if reporter_id not in report_cooldown:
                    report_cooldown[reporter_id] = []
                
                report_cooldown[reporter_id] = [
                    t for t in report_cooldown[reporter_id] 
                    if current_time - t < SPAM_WINDOW
                ]
                
                if len(report_cooldown[reporter_id]) >= SPAM_LIMIT:
                    try:
                        user = await bot.fetch_user(reporter_id)
                        embed = discord.Embed(
                            title="Too Many Reports",
                            description="Please try again later.",
                            color=discord.Color.red()
                        )
                        await user.send(embed=embed)
                    except:
                        pass
                    return
                
                report_cooldown[reporter_id].append(current_time)
                
                admin_channel = bot.get_channel(BUG_REPORT_ADMIN_CHANNEL_ID)
                embed = discord.Embed(
                    title="New Bug Report",
                    description=report_data['description'],
                    color=discord.Color.orange()
                )
                embed.add_field(name="Reporter", value=f"{report_data['reporter']['discord_username']} ({report_data['reporter']['in_game_name']})")
                embed.add_field(name="Timestamp", value=report_data['timestamp'])
                if report_data.get('attachment'):
                    embed.add_field(name="Attachment", value=report_data['attachment'])
                
                view = BugReportReviewView(reporter_id, report_data)
                await admin_channel.send(embed=embed, view=view)
                
                try:
                    user = await bot.fetch_user(reporter_id)
                    embed = discord.Embed(
                        title="Report Received",
                        description="Your bug report has been submitted for review.",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Details", value=report_data['description'])
                    await user.send(embed=embed)
                except:
                    pass
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Error processing bug report: {e}")

@bot.event
async def on_ready():
    bot.add_view(BugReportReviewView(reporter_id=None, report_data=None))
    print(f"Bot is ready as {bot.user}")

bot.run(TOKEN)