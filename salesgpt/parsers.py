import re
from typing import Union

from langchain.agents.agent import AgentOutputParser
from langchain.schema import AgentAction, AgentFinish

class SalesConvoOutputParser(AgentOutputParser):
    ai_prefix: str = "AI"  # change for salesperson_name
    verbose: bool = True

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        if self.verbose:
            print("Parsing text:", text)

        # Check for the action format
        action_regex = r"Action: (.*?)\n*Action Input: (.*)"
        action_match = re.search(action_regex, text)

        if action_match:
            action = action_match.group(1).strip()
            action_input = action_match.group(2).strip().strip('"')
            print("Detected action format: Action={}, Action Input={}".format(action, action_input))
            return AgentAction(action, action_input, text)

        # If the action format is not found, return a default response
        print("No action format detected. Returning default response.")
        return AgentFinish({"output": text}, text)

    @property
    def _type(self) -> str:
        return "sales-agent"
