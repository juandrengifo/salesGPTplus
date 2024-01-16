import os
from typing import List

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Correct the import path as per your project structure
from salesgpt.salesgptapi import SalesGPTAPI

app = FastAPI()


@app.get("/")
async def say_hello():
    return {"message": "Hello World"}


class MessageList(BaseModel):
    conversation_history: List[str]
    human_say: str


@app.post("/chat")
async def chat_with_sales_agent(req: MessageList):
    sales_api = SalesGPTAPI(config_path="")
    response = sales_api.do(req.conversation_history, req.human_say)

    # Use the response directly
    return response


def _set_env():
    # Load environment variables from .env file
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

if __name__ == "__main__":
    _set_env()
    uvicorn.run(app, host="127.0.0.1", port=8000)
