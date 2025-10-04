from utils import get_sb_environment
import subprocess

def y_str(s): # yellow
    return "\033[33m" + s + "\033[0m"

class LimitsExceeded(Exception):
    """Raised when the agent has reached its step limit."""


class SWEEnvironment:
    """
    Minimal interface to the SWEBench execution environment.

    Students may use their own wrapper. The environment must expose:
    - execute(command: str) -> str: Run a shell command and return stdout, or raise ValueError on failure
    """

    def __init__(self, instance: dict):
        self.env = get_sb_environment(instance)
     
    # -------------------- REQUIRED TOOLS --------------------
    def run_bash_cmd(self, command: str) -> str:
        """
        Run the command in a bash shell and return the output or throw a ValueError
        if the process returns non-zero exit code.

        Args;
            command (str): the shell command to run

        Returns:
            The output of running the shell command
        """
        try:
            output = self.env.execute(command)
        except subprocess.TimeoutExpired as e:
            output = e.output.decode("utf-8", errors="replace") if e.output else ""
            raise ValueError(output)
        except TimeoutError:
            raise ValueError("TimeoutError")
        return output
    def _extract_unified_diff(self, text: str) -> str:
        if not text:
            return ""
        # Prefer unified diffs that start with `diff --git`
        i = text.rfind("\ndiff --git ")
        if i == -1:
            i = text.find("diff --git ")
        if i != -1:
            return text[i:].rstrip("\n") + "\n"
        # Fallback: look for classic headers
        j = text.rfind("\n--- a/")
        if j == -1:
            j = text.find("--- a/")
        if j != -1:
            return text[j:].rstrip("\n") + "\n"
        return ""

    def generate_patch(self, result: str) -> str:
        """
        Generate a patch from the result (for SWE-Bench)
        """
        try:
            patch_output = self.env.execute("git add -A && git diff --cached")
            print(y_str(f"Patch output: ") + f"{patch_output}")
            if patch_output["output"].strip():
                return patch_output["output"].strip()
            else:
                fallback = self._extract_unified_diff(result or "")
                if fallback:
                    print(y_str(f"Fallback patch: ") + f"{fallback}")
                    return fallback
                return f"{result}\n\nNo changes detected to generate a patch."
        except Exception as e:
            return f"{result}\n\nError running git commands: {e}"
    
    # -------------------- TODO(student): add more functions here if you want --------------------
    def replace_in_file(self, file_path: str, from_line: int, to_line: int, content: str) -> str:
        """
        [Optional] Replace the content of the file from the given line to the given line with the given content
        """
        from_line = int(str(from_line).strip())
        to_line = int(str(to_line).strip()) 
        if from_line < 1 or to_line < 1 or to_line < from_line:
            raise ValueError("Invalid line range")

        # Read file
        res = self.env.execute(f"cat {file_path}")
        original = res.get("output", "") if isinstance(res, dict) else str(res)

        lines = original.splitlines()
        start = from_line - 1
        end = to_line - 1
        if start > len(lines):
            raise ValueError("from_line exceeds total number of lines")

        before = lines[:start]
        after = lines[end + 1:] if end + 1 <= len(lines) else []
        new_text = "\n".join(before + content.splitlines() + after)
        if original.endswith("\n") and not new_text.endswith("\n"):
            new_text += "\n"

        # Write back (quoted heredoc prevents expansion)
        write_cmd = f"cat > {file_path} << 'MINISWE_EOF'\n{new_text}MINISWE_EOF"
        wres = self.env.execute(write_cmd)
        if isinstance(wres, dict) and wres.get("returncode", 0):
            raise ValueError(wres.get("output", ""))

        return f"Replaced lines {from_line}-{to_line} in {file_path}."
    
    def show_file(self, file_path: str) -> str:
        """
        [Optional]Show the content of the file
        """
        try:
            # Show file with line numbers for easier referencing
            output = self.env.execute(f"nl -ba {file_path}")["output"].strip()
            return output
        except Exception as e:
            raise ValueError(f"Failed to read file '{file_path}': {e}")


class DumbEnvironment:
    """
    Dumb environment that just executes the command
    """

    def run_bash_cmd(self, command: str) -> str:
        """
        Run the command in bash and return the output

        Args;
            command (str): the shell command to run

        Returns:
            The output of running the shell command
        """
        result = subprocess.run(command, capture_output=True, shell=True, check=False)
        output = f"--STDOUT--\n{result.stdout.decode()}\n--STDERR--\n{result.stderr.decode()}"
        if result.returncode:
            raise ValueError(output)
        return output