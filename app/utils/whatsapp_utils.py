import logging
import json
import requests
import re

from flask import current_app, jsonify
from salesgpt.salesgptapi import SalesGPTAPI

# Global dictionary to store conversation histories
conversation_histories = {}

sales_api = SalesGPTAPI(config_path="")

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")

def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

def parse(reply):
    reply = reply[11:-13]
    if '```' in reply:
        reply = reply[3:-3]
        
    if "Action:" in reply:
        return ""
    
    if "tool? No" in reply and "hought" not in reply:
        reply = reply[38:]
    if "hought" in reply:
        reply = reply[45:]
    return reply



def generate_response(sender, incoming_msg, conversation_history):
    # Use the singleton instance of SalesGPTAPI
    global sales_api 

    response = sales_api.do(conversation_history, incoming_msg)
    name, reply = response["name"], response["reply"]
    reply = parse(reply)
    # Split the response into segments based on punctuation marks
    segments = re.split(r'(?<=[.!?]) +', reply)

    _segments = []

    # Update the conversation history with segments
    for segment in segments:
        if not (segment == "<INFO_REQUESTED>" or segment == " <INFO_REQUESTED>" or segment=="<INFO_REQUESTED> "):
            _segments.append(segment) 
        conversation_history.append(f"{name}: {segment}")
    conversation_histories[sender] = conversation_history

    return _segments

def send_message(recipient, segments):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    for segment in segments:
        data = get_text_message_input(recipient, segment)
        try:
            response = requests.post(url, data=data, headers=headers, timeout=10)
            response.raise_for_status()
            log_http_response(response)
        except requests.Timeout:
            logging.error("Timeout occurred while sending message segment")
        except requests.RequestException as e:
            logging.error(f"Request failed due to: {e}")
            break  # Stop sending further segments if an error occurs

def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_body = message["text"]["body"]

    # Retrieve the conversation history for the user
    conversation_history = conversation_histories.get(wa_id, [])

    # Generate a response which now returns a list of segments
    segments = generate_response(wa_id, message_body, conversation_history)

    # Send each message segment separately
    send_message(current_app.config["RECIPIENT_WAID"], segments)

def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )