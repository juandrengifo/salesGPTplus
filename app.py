import os
import time
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from salesgpt.salesgptapi import SalesGPTAPI

app = Flask(__name__)

conversation_histories = {}

def split_message(message, max_length=50):
    """Splits a message into chunks of max_length, splitting by punctuation or space."""
    chunks = []
    while message:
        if len(message) <= max_length:
            chunks.append(message)
            break
        split_index = max([message.rfind(punc, 0, max_length + 1) 
                           for punc in '.?!'])  # Find punctuation
        if split_index == -1:  # No punctuation found
            split_index = message.rfind(' ', 0, max_length + 1)  # Find last space
        if split_index == -1:  # No space found, force split
            split_index = max_length
        chunks.append(message[:split_index + 1])
        message = message[split_index + 1:].strip()
    return chunks

@app.route('/bot', methods=['POST'])
def bot():
    sender = request.values.get('From', '')
    incoming_msg = request.values.get('Body', '').lower()

    conversation_history = conversation_histories.get(sender, [])
    sales_api = SalesGPTAPI(config_path="")

    response = sales_api.do(conversation_history, incoming_msg)
    name, reply = response["name"], response["reply"]

    conversation_history.append(f"User: {incoming_msg}")
    conversation_history.append(f"{name}: {reply}")
    conversation_histories[sender] = conversation_history

    resp = MessagingResponse()
    message_chunks = split_message(reply)
    for chunk in message_chunks:
        msg = resp.message()
        msg.body(chunk)
        time.sleep(1)  # Delay to prevent Twilio limitations
    return str(resp)

def _set_env():
    with open(".env", "r") as f:
        env_file = f.readlines()
    envs_dict = {key.strip("'"): value.strip("\n") for key, value in [(i.split("=")) for i in env_file]}
    os.environ["OPENAI_API_KEY"] = envs_dict["OPENAI_API_KEY"]

if __name__ == "__main__":
    _set_env()
    app.run(host="127.0.0.1", port=5000)
