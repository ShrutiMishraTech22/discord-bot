#
# ===================================================================================
#  The Brain of Your Project: bot.py
# ===================================================================================
#
import re
import discord
from discord.ext import commands
import os
import requests
import sqlite3
from flask import Flask, request, abort
from threading import Thread
import hashlib
import hmac
from dotenv import load_dotenv

# This line loads the secrets from your .env file
load_dotenv()

# --- CONFIGURATION (Reads from your .env file) ---
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GITHUB_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET')
LEADERBOARD_CHANNEL_ID = int(os.getenv('LEADERBOARD_CHANNEL_ID'))
GITHUB_REPO = "LavanyaSharma232/EduEase" # IMPORTANT: Change this!

# --- DATABASE SETUP ---
# This sets up a simple database file named 'scores.db' in your project folder.
con = sqlite3.connect("scores.db", check_same_thread=False)
cur = con.cursor()
cur.execute('''
    CREATE TABLE IF NOT EXISTS scores (
        github_username TEXT PRIMARY KEY,
        points INTEGER
    )
''')
con.commit()

# --- DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    """This function runs when the bot successfully connects to Discord."""
    print(f'Bot is online and logged in as {bot.user}')

def update_score(username, points_to_add):
    """This function handles updating the score in the database."""
    cur.execute("SELECT points FROM scores WHERE github_username = ?", (username,))
    result = cur.fetchone()
    if result:
        new_points = result[0] + points_to_add
        cur.execute("UPDATE scores SET points = ? WHERE github_username = ?", (new_points, username))
    else:
        cur.execute("INSERT INTO scores (github_username, points) VALUES (?, ?)", (username, points_to_add))
    con.commit()
    print(f"Updated score for {username}. Added {points_to_add} points.")

# --- GITHUB API HELPER ---
# --- GITHUB API HELPER (IMPROVED VERSION) ---
def get_points_from_pr_labels(issue_number):
    """Fetches issue labels from GitHub API and returns points."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"--- DEBUG INFO ---")
        print(f"Error fetching details for ISSUE #{issue_number} from GitHub. Status Code: {response.status_code}")
        print(f"The URL I tried to access was: {url}")
        print(f"Please double-check that the GITHUB_REPO variable is set correctly in your code and that issue #{issue_number} actually exists.")
        print(f"--- END DEBUG INFO ---")
        return 0

    data = response.json()
    labels = {label['name'].lower() for label in data.get('labels', [])}
    
    if 'hard' in labels:
        return 20
    elif 'medium' in labels:
        return 10
    elif 'easy' in labels:
        return 5
    return 0

# --- LEADERBOARD COMMAND ---
@bot.command(name='leaderboard')
async def show_leaderboard(ctx):
    """This function runs when someone types !leaderboard in Discord."""
    cur.execute("SELECT github_username, points FROM scores ORDER BY points DESC LIMIT 10")
    results = cur.fetchall()

    if not results:
        await ctx.send("The leaderboard is currently empty!")
        return

    embed = discord.Embed(title="🏆 Open Source Event Leaderboard 🏆", color=discord.Color.gold())
    description = ""
    for rank, (username, points) in enumerate(results, 1):
        description += f"**{rank}.** {username} - `{points} points`\n"
    
    embed.description = description
    await ctx.send(embed=embed)


# --- FLASK WEB SERVER FOR WEBHOOK ---
# This part listens for the messages from GitHub.
app = Flask(__name__)

# --- FLASK WEB SERVER FOR WEBHOOK (IMPROVED VERSION) ---
@app.route('/github-webhook', methods=['POST'])
def github_webhook():
    # --- Signature verification (no changes here) ---
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature or not signature.startswith('sha256='):
        abort(400, 'Invalid signature')
    hash_object = hmac.new(GITHUB_SECRET.encode('utf-8'), msg=request.data, digestmod=hashlib.sha256)
    expected_signature = 'sha256=' + hash_object.hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        abort(403, 'Signatures do not match. Is the secret correct?')

    # --- Process the payload (this part is new and improved) ---
    data = request.json
    if data.get('action') == 'closed' and data['pull_request']['merged']:
        pr = data['pull_request']
        username = pr['user']['login']
        pr_number = pr['number']
        pr_title = pr['title']
        pr_url = pr['html_url']
        pr_body = pr.get('body') or ""# Get the PR description

        # NEW: Search the PR body for keywords like "Fixes #123"
        issue_number_match = re.search(r"(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s#(\d+)", pr_body, re.IGNORECASE)

        if not issue_number_match:
            print(f"Could not find a linked issue number (e.g., 'Fixes #123') in the body of PR #{pr_number}. Cannot assign points.")
            return ('', 204) # Exit gracefully, nothing to score.

        # Extract the actual issue number from the description
        issue_number = int(issue_number_match.group(1))
        
        # Pass the CORRECT issue number to our helper function
        points = get_points_from_pr_labels(issue_number)

        if points > 0:
            update_score(username, points)
            
            channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title="🎉 New Contribution Merged! 🎉",
                    description=f"**[{pr_title}]({pr_url})**",
                    color=discord.Color.green()
                )
                embed.add_field(name="Contributor", value=f"**{username}**", inline=True)
                embed.add_field(name="Points Awarded", value=f"**{points}**", inline=True)
                bot.loop.create_task(channel.send(embed=embed))

    return ('', 204)


# --- RUN EVERYTHING ---
# This part runs the Flask web server and the Discord Bot at the same time.
def run_flask():
    # The web server will run on host 0.0.0.0, which is needed for hosting platforms.
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    # Start the web server in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Run the Discord bot
    bot.run(DISCORD_TOKEN)