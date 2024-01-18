import re
from typing import Union

from langchain.agents.agent import AgentOutputParser
from langchain.agents.conversational.prompt import FORMAT_INSTRUCTIONS
from langchain.schema import AgentAction, AgentFinish  # OutputParserException


class SalesConvoOutputParser(AgentOutputParser):
    ai_prefix: str = "AI"  # change for salesperson_name
    verbose: bool = True

    def get_format_instructions(self) -> str:
        return FORMAT_INSTRUCTIONS

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        # Logging for debugging
        if self.verbose:
            print(f"Parsing text: {text}")

        # Regex to extract the desired response part
        response_pattern = rf"{self.ai_prefix}: (.+?)(<END_OF_TURN>|$)"
        response_match = re.search(response_pattern, text, re.DOTALL)

        if response_match:
            # Extract the actual response text
            actual_response = response_match.group(1).strip()
            if self.verbose:
                print(f"Extracted response: {actual_response}")
            return AgentFinish({"output": actual_response}, text)

        # Existing regex pattern matching for action format
        action_regex = r"Action: (.*?)[\n]*Action Input: (.*)"
        action_match = re.search(action_regex, text)
        if action_match:
            # Found action format
            action = action_match.group(1).strip()
            action_input = action_match.group(2).strip().strip('"')
            if self.verbose:
                print(f"Detected action format: Action={action}, Action Input={action_input}")
            return AgentAction(action, action_input, text)

        # Fallback if none of the expected formats are found
        if self.verbose:
            print("Fallback to default apology message.")
        return AgentFinish(
            {
                "output": "I apologize, I was unable to find the answer to your question. Is there anything else I can help with?"
            },
            text,
        )

    @property
    def _type(self) -> str:
        return "sales-agent"
