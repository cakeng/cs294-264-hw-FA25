def g_str(s): # green
    return "\033[32m" + s + "\033[0m"
def r_str(s): # red
    return "\033[31m" + s + "\033[0m"
def b_str(s): # blue
    return "\033[34m" + s + "\033[0m"
def y_str(s): # yellow
    return "\033[33m" + s + "\033[0m"


class ResponseParser:
    """
    Parses LLM responses to extract a single function call using a rigid textual format.

    The LLM must output exactly one function call at the end of its response.
    Do NOT use JSON or XML. Use rfind to locate the final markers.
    """

    BEGIN_CALL = "----BEGIN_FUNCTION_CALL----"
    END_CALL = "----END_FUNCTION_CALL----"
    ARG_SEP = "----ARG----"

    # Students should include this exact template in the system prompt so the LLM follows it.
    response_format = f"""
your_thoughts_here
...
{BEGIN_CALL}
function_name
{ARG_SEP}
arg1_name
arg1_value (can be multiline)
{ARG_SEP}
arg2_name
arg2_value (can be multiline)
...
{END_CALL}
"""

    def parse(self, text: str) -> dict:
        """
        Parse the function call from `text` using string.rfind to avoid confusion with
        earlier delimiter-like content in the reasoning.

        Returns a dictionary: {"thought": str, "name": str, "arguments": dict}
        """
        end_idx = text.rfind(self.END_CALL)
        if end_idx == -1:
            raise ValueError("Missing END_CALL token")
        begin_idx = text.rfind(self.BEGIN_CALL, 0, end_idx)
        if begin_idx == -1:
            raise ValueError("Missing BEGIN_CALL before END_CALL")

        thought = text[:begin_idx].rstrip()
        inner = text[begin_idx + len(self.BEGIN_CALL):end_idx]
        inner = inner.strip()

        # Split by ARG_SEP blocks. The first block contains only the function name.
        parts = inner.split(self.ARG_SEP)
        if not parts or not parts[0].strip():
            raise ValueError("Missing function name block")

        name = parts[0].strip().splitlines()[0].strip()
        if not name:
            raise ValueError("Empty function name")

        arguments = {}
        # Each subsequent block corresponds to a single argument block:
        # first line is the arg name; remaining lines form the value (can be multiline).
        for block in parts[1:]:
            cleaned = block.strip("\n")
            if not cleaned.strip():
                continue
            lines = cleaned.splitlines()
            if not lines:
                continue
            arg_name = lines[0].strip()
            if not arg_name:
                raise ValueError("Empty argument name")
            arg_value = "\n".join(lines[1:]).strip()
            arguments[arg_name] = arg_value

        return {"thought": thought, "name": name, "arguments": arguments}
