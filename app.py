import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from salesgpt.salesgptapi import SalesGPTAPI

app = Flask(__name__)

conversation_histories = {}

@app.route('/bot', methods=['POST'])
def bot():
    sender = request.values.get('From', '')  # Get sender's phone number
    incoming_msg = request.values.get('Body', '').lower()

    # Retrieve or initialize conversation history
    conversation_history = conversation_histories.get(sender, [])

    # Initialize the SalesGPT API
    sales_api = SalesGPTAPI(config_path="")

    # Process the incoming message and get the response from SalesGPT
    response = sales_api.do(conversation_history, incoming_msg)
    name, reply = response["name"], response["reply"]

    # Append both user's and agent's responses to the conversation history
    conversation_history.append(f"User: {incoming_msg}")
    conversation_history.append(f"{name}: {reply}")
    conversation_histories[sender] = conversation_history

    # Create a Twilio MessagingResponse
    resp = MessagingResponse()
    msg = resp.message()
    msg.body(reply)  # Send only the reply
    return str(resp)








def _set_env():
    with open(".env", "r") as f:
        env_file = f.readlines()
    envs_dict = {key.strip("'"): value.strip("\n") for key, value in [(i.split("=")) for i in env_file]}
    os.environ["OPENAI_API_KEY"] = envs_dict["OPENAI_API_KEY"]

if __name__ == "__main__":
    _set_env()
    app.run(host="127.0.0.1", port=5000)
