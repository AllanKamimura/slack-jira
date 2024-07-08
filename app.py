import os
from slack_bolt import App
from slack_sdk.web import WebClient
from slack_bolt.adapter.socket_mode import SocketModeHandler

import json
import logging
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin

BOT_TAG  = "<@U07AANEMT6E>"

JIRA_URL   = os.environ.get('JIRA_URL')
JIRA_KEY   = os.environ.get('JIRA_KEY')
JIRA_EMAIL = os.environ.get('JIRA_EMAIL')
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")

issue_types = {
    "BUG": {
        'id': '10103',
        },
    "STORY":{
        "id": "10100"
        }
}

#### jira functions (todo: create a proper class)
#### todo: make the project id configurable
def create_jira_issue(message, summary, issuetype):
    api = f"rest/api/3/issue"
    url = urljoin(JIRA_URL, api)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    payload = json.dumps({
        "fields": {
            "description": {
                "content": [
                    {
                        "content": [
                            {
                                "text": message,
                                "type": "text"
                            }
                        ],
                        "type": "paragraph"
                    }
                ],
                "type": "doc",
                "version": 1
            },
            "project": {
                "id": "10038" # todo: make this configurable
            },
            "summary": summary,
            "labels": ["TMTriage", "bot"],
            "issuetype": issuetype
        }
    })

    auth = HTTPBasicAuth(f"{JIRA_EMAIL}", f"{JIRA_KEY}")

    response = requests.request(
                        "POST",
                        url,
                        data    = payload,
                        headers = headers,
                        auth    = auth
                        )

    print(response.content)

    response.raise_for_status()
    
    return response.json()['key']

def add_attachments(issue_id, file_paths):
    api = f"rest/api/3/issue/{issue_id}/attachments"
    url = urljoin(JIRA_URL, api)

    attachment_headers = {
        'X-Atlassian-Token': 'no-check'
        }
    
    auth = HTTPBasicAuth(f"{JIRA_EMAIL}", f"{JIRA_KEY}")

    for file_path in file_paths:
        with open(file_path, "rb") as f:
            files = {
                'file': (os.path.basename(file_path), open(file_path, 'rb'))
            }

            response = requests.post(
                url,
                headers = attachment_headers, 
                files = files,
                auth  = auth,
                )

        logging.info(f"jira: add attach: {file_path}")
        
#### bot functions (todo: create a proper class)
def is_message_in_thread(event):
    # Check if the message event has the 'thread_ts' attribute
    return 'thread_ts' in event

def download_image(file_url, file_name, thread_ts):
    headers = {
        'Authorization': f'Bearer {SLACK_BOT_TOKEN}',
    }
    response = requests.get(file_url, headers=headers)

    logging.info(f"{file_url}")

    if response.status_code == 200:
        
        format_name = f"{thread_ts.replace('.', '_')}-{file_name}"
        print(format_name)
        file_path = os.path.join("media", format_name)

        with open(file_path, 'wb') as file:
            file.write(response.content)

        print(f"File downloaded successfully and saved at {file_path}")

        return file_path
    
    else:  
        print("Failed to download file")

def get_user(event, main_message):
    reply_user = main_message.get("user", event["user"])

    return reply_user

def check_category(text):
    if text.strip().upper().startswith("BUG"):
        issuetype = issue_types["BUG"]
    else:
        issuetype = issue_types["STORY"]

    return issuetype

def check_attachments(main_message, thread_ts):
    files = main_message.get("files", {})
    downloaded_files = []

    logging.info(f"{files}")

    for file in files:
        url   = file.get("url_private_download", "")
        name  = file.get("name", "")

        if url:
            print(url)
            file_path = download_image(url, name, thread_ts)
            downloaded_files.append(file_path)
    
    return downloaded_files

# Initialize your app with your bot token and signing secret
app    = App(token = SLACK_BOT_TOKEN)
client = WebClient(token = SLACK_BOT_TOKEN)

# Configure logging to file
logging.basicConfig(filename='logs/app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@app.event("app_mention")
def handle_app_mention_events(event, say, logger):
    print(event)
    
    user      = event["user"]      # The user who mentioned the bot
    text      = event["text"]      # The text of the message (to be used as a title)
    channel   = event["channel"]   # The channel where the mention occurred
    timestamp = event["ts"]        # The message event timestamp

    # Log the mention
    logger.info(f"Bot was mentioned by user {user} in channel {channel} with message: {text}")

    # Confirm that the bot received the message
    url = "https://slack.com/api/reactions.add"

    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "channel": channel,
        "timestamp": timestamp,
        "name": "thumbsup"
    }

    response = requests.post(url, headers=headers, json=data)
    print(response.text)

    if is_message_in_thread(event):

        thread_ts = event['thread_ts']            # Thread "id"
        text = event["text"].replace(BOT_TAG, "") # Remove the mention to the bot

        issuetype = check_category(text)

        response = client.conversations_replies(channel = channel, ts = thread_ts)

        print(response)

        main_message = response["messages"][0]
        main_text    = main_message["text"] # The text in the first message in the thread

        downloaded_files = check_attachments(main_message, thread_ts)
        reply_user = get_user(event, main_message)

        issue_key = create_jira_issue(main_text.replace("\n","\n\n"), text, issuetype)
        #issue_key = "DWC-5266"
        link = f"{JIRA_URL}/browse/{issue_key}"

        say(f"Hi there, <@{reply_user}>!\nThis issue is being tracked at {link}", thread_ts = thread_ts)

        add_attachments(issue_key, downloaded_files)

# Start your app
if __name__ == "__main__":
    logging.info("app start")
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
