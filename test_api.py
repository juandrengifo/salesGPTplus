import requests

url = 'http://127.0.0.1:8000/chat'

# Starting the conversation
data = {
    "conversation_history": ["Agent: Hi, how can I help you today?"],
    "human_say": "I'm looking for a car battery."
}

response = requests.post(url, json=data)
if response.status_code == 200:
    response_data = response.json()
    agent_name = response_data.get("name")
    agent_reply = response_data.get("reply")
    print(f"{agent_name}: {agent_reply}")

    # Accumulate the conversation history
    conversation_history = data["conversation_history"] + [f"User: I'm looking for a car battery.", f"Agent: {agent_reply}"]

    # Now, continue the conversation by replying to the agent
    next_data = {
        "conversation_history": conversation_history,
        "human_say": "Hola, con Juan"  # Your response to the agent
    }

    next_response = requests.post(url, json=next_data)
    if next_response.status_code == 200:
        next_response_data = next_response.json()
        next_agent_name = next_response_data.get("name")
        next_agent_reply = next_response_data.get("reply")
        print(f"{next_agent_name}: {next_agent_reply}")
    else:
        print(f"Error: Received response with status code {next_response.status_code}")
else:
    print(f"Error: Received response with status code {response.status_code}")
