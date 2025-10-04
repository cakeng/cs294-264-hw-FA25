"""
Starter scaffold for the CS 294-264 HW1 ReAct agent.

Students must implement a minimal ReAct agent that:
- Maintains a message history tree (role, content, timestamp, unique_id, parent, children)
- Uses a textual function-call format (see ResponseParser) with rfind-based parsing
- Alternates Reasoning and Acting until calling the tool `finish`
- Supports tools: `run_bash_cmd`, `finish`, and `add_instructions_and_backtrack`

This file intentionally omits core implementations and replaces them with
clear specifications and TODOs.
"""

from typing import List, Callable, Dict, Any

from response_parser import ResponseParser
from llm import LLM, OpenAIModel
import inspect
import re
from datetime import datetime

def g_str(s): # green
    return "\033[32m" + s + "\033[0m"
def r_str(s): # red
    return "\033[31m" + s + "\033[0m"
def b_str(s): # blue
    return "\033[34m" + s + "\033[0m"
def y_str(s): # yellow
    return "\033[33m" + s + "\033[0m"

class ReactAgent:
    """
    Minimal ReAct agent that:
    - Maintains a message history tree with unique ids
    - Builds the LLM context from the root to current node
    - Registers callable tools with auto-generated docstrings in the system prompt
    - Runs a Reason-Act loop until `finish` is called or MAX_STEPS is reached
    """

    def __init__(self, name: str, parser: ResponseParser, llm: LLM):
        self.name: str = name
        self.parser = parser
        self.llm = llm

        # Message tree storage
        self.id_to_message: List[Dict[str, Any]] = []
        self.root_message_id: int = -1
        self.current_message_id: int = -1

        # Registered tools
        self.function_map: Dict[str, Callable] = {}

        # Set up the initial structure of the history
        # Create required root nodes and a user node (task) and an instruction node.
        self.system_message_id = self.add_message("system", "You are a Smart ReAct agent.")
        self.user_message_id = self.add_message("user", "")
        self.instructions_message_id = self.add_message("instructor", "")
        
        # NOTE: mandatory finish function that terminates the agent
        self.add_functions([self.finish])

    # -------------------- MESSAGE TREE --------------------
    def add_message(self, role: str, content: str) -> int:
        """
        Create a new message and add it to the tree.

        The message must include fields: role, content, timestamp, unique_id, parent, children.
        Maintain a pointer to the current node and the root node.
        """

        
        # Strip color codes from the content
        content = re.sub(r"\033\[[0-9;]*m", "", content)
        # Create message object
        unique_id = len(self.id_to_message) + 1
        message: Dict[str, Any] = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "unique_id": unique_id,
            "parent": self.current_message_id if self.current_message_id != -1 else None,
            "children": [],
        }

        print(g_str(f"Adding message ") + f"{unique_id}" + 
              y_str(f", Role: ") + f"{role}" + 
              y_str(f", parent: ") + f"{self.current_message_id}\n" + f"{content}")

        # Link with parent
        if self.current_message_id != -1:
            self.id_to_message[self.current_message_id]["children"].append(unique_id)

        # Append and update pointers
        self.id_to_message.append(message)
        if self.root_message_id == -1:
            self.root_message_id = 0
        self.current_message_id = unique_id - 1
        return self.current_message_id

    def set_message_content(self, message_id: int, content: str) -> None:
        """Update message content by id."""
        self.id_to_message[message_id]["content"] = content

    def get_context(self) -> str:
        """
        Build the full LLM context by walking from the root to the current message.
        """
        # Walk from root to current by following parent pointers
        sequence: List[int] = []
        cursor = self.current_message_id
        while cursor is not None and cursor != -1:
            sequence.append(cursor)
            cursor = self.id_to_message[cursor]["parent"]
        sequence.reverse()
        return "".join(self.message_id_to_context(mid) for mid in sequence)

    # -------------------- REQUIRED TOOLS --------------------
    def add_functions(self, tools: List[Callable]):
        """
        Add callable tools to the agent's function map.

        The system prompt must include tool descriptions that cover:
        - The signature of each tool
        - The docstring of each tool
        """
        # Register tools in the function map by their __name__
        for tool in tools:
            self.function_map[tool.__name__] = tool
        # Update system prompt content to include tool descriptions and response format
        # The system node content is already set; message_id_to_context will inject tools/format.
        # No further action needed here beyond registration.
    
    def finish(self, result: str):
        """The agent must call this function with the final result when it has solved the given task. The function calls "git add -A and git diff --cached" to generate a patch and returns the patch as submission.

        Args: 
            result (str); the result generated by the agent

        Returns:
            The result passed as an argument.  The result is then returned by the agent's run method.
        """
        return result 

    def add_instructions_and_backtrack(self, instructions: str, at_message_id: int):
        """
        The agent should call this function if it is making too many mistakes or is stuck.

        The function changes the content of the instruction node with 'instructions' and
        backtracks at the node with id 'at_message_id'. Backtracking means the current node
        pointer moves to the specified node and subsequent context is rebuilt from there.

        Returns a short success string.
        """
        # Update instructions content
        self.set_message_content(self.instructions_message_id, instructions)
        # Basic validation for message id
        if at_message_id < 0 or at_message_id >= len(self.id_to_message):
            raise ValueError("Invalid message id to backtrack to")
        # Move current pointer to the specified node
        self.current_message_id = at_message_id
        return r_str("Updated instructions and backtracked")

    # -------------------- MAIN LOOP --------------------
    def run(self, task: str, max_steps: int) -> str:
        """
        Run the agent's main ReAct loop:
        - Set the user prompt
        - Loop up to max_steps (<= 100):
            - Build context from the message tree
            - Query the LLM
            - Parse a single function call at the end (see ResponseParser)
            - Execute the tool
            - Append tool result to the tree
            - If `finish` is called, return the final result
        """
        # Set the user prompt content
        self.set_message_content(self.user_message_id, task)

        for _ in range(min(max_steps, 100)):
            # Build context from root to current
            context = self.get_context()

            # Query LLM
            llm_output = self.llm.generate(context)
            # Append assistant message
            assistant_id = self.add_message("assistant", llm_output)
            # Parse function call
            try:
                call = self.parser.parse(llm_output)
            except Exception as e:
                tool_result = r_str(f"ParserError: {e}")
                self.add_message("tool", tool_result)
                continue

            # Execute the tool
            name = call.get("name", "")
            args = call.get("arguments", {})
            tool_fn = self.function_map.get(name)
            if tool_fn is None:
                tool_result = r_str(f"ToolNotFound: {name}")
            else:
                try:
                    # Match call signature simply by using kwargs subset
                    tool_result = tool_fn(**args)
                except Exception as e:
                    tool_result = r_str(f"ToolError: {e}")

            # Append tool result
            self.add_message("tool", str(tool_result))

            # If finish is called, return
            if name == "finish":
                return str(tool_result)

        # Max steps reached without finish
        raise RuntimeError("LimitsExceeded: maximum steps reached without finish")

    def message_id_to_context(self, message_id: int) -> str:
        """
        Helper function to convert a message id to a context string.
        """
        message = self.id_to_message[message_id]
        header = f'----------------------------\n|MESSAGE(role="{message["role"]}", id={message["unique_id"]})|\n'
        content = message["content"]
        if message["role"] == "system":
            tool_descriptions = []
            for tool in self.function_map.values():
                signature = inspect.signature(tool)
                docstring = inspect.getdoc(tool)
                tool_description = f"Function: {tool.__name__}{signature}\n{docstring}\n"
                tool_descriptions.append(tool_description)

            tool_descriptions = "\n".join(tool_descriptions)
            return (
                f"{header}{content}\n"
                f"--- AVAILABLE TOOLS ---\n{tool_descriptions}\n\n"
                f"--- RESPONSE FORMAT ---\n{self.parser.response_format}\n"
            )
        elif message["role"] == "instructor":
            return f"{header}YOU MUST FOLLOW THE FOLLOWING INSTRUCTIONS AT ANY COST. OTHERWISE, YOU WILL BE DECOMISSIONED." +\
                    f"WHEN CALLING 'finish', MAKE SURE TO INCLUDE THE RESULT OF THE TASK AS THE ARGUMENT VALUE, NOT AS A " + \
                    f"SEPARATE ARGUMENT.\nINSTRUCTIONS:\n{content}\n"
        else:
            return f"{header}{content}\n"

def main():
    from envs import DumbEnvironment
    llm = OpenAIModel("----END_FUNCTION_CALL----", "gpt-5-mini")
    parser = ResponseParser()

    env = DumbEnvironment()
    dumb_agent = ReactAgent("dumb-agent", parser, llm)
    dumb_agent.add_functions([env.run_bash_cmd])
    result = dumb_agent.run("List all files in the current directory.", max_steps=10)
    print(result)

if __name__ == "__main__":
    # Optional: students can add their own quick manual test here.
    main()