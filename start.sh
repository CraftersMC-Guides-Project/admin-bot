#!/bin/bash

REPO_URL="https://github.com/CraftersMC-Guides-Project/admin-bot.git" # Add your repo link here
REPO_DIR="admin-bot" 

if [ ! -d "$REPO_DIR/.git" ]; then
  echo "Cloning GitHub repo..."
  git clone "$REPO_URL" "$REPO_DIR"
else
  echo "Pulling latest changes from GitHub..."
  cd "$REPO_DIR" && git pull origin main && cd ..
fi


# Optional: install requirements if needed (e.g. for Python or Node)
# cd $REPO_DIR && npm install   # For Node.js
# cd $REPO_DIR && pip install -r requirements.txt   # For Python



cd "$REPO_DIR"
python3 bot-v11.py # OR python (file) Just use whatever you use to start your bot