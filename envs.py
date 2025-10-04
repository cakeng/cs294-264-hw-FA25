from utils import get_sb_environment
import subprocess

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
    
    def generate_patch(self, result: str) -> str:
        """
        Generate a patch from the result (for SWE-Bench)
        """
        try:
            patch_output = self.env.execute("git add -A && git diff --cached")
            if patch_output["output"].strip():
                return patch_output
            else:
                return f"{result}\n\nNo changes detected to generate a patch."
        except Exception as e:
            return f"{result}\n\nError running git commands: {e}"
    
    # -------------------- TODO(student): add more functions here if you want --------------------
    def replace_in_file(self, file_path: str, from_line: int, to_line: int, content: str) -> str:
        """
        [Optional] Replace the content of the file from the given line to the given line with the given content
        """
        # Validate input
        if from_line < 1 or to_line < 1:
            raise ValueError("Line numbers must be >= 1")
        if to_line < from_line:
            raise ValueError("to_line must be >= from_line")

        # Read file from the SWEBench environment
        try:
            original = self.env.execute(f"cat {file_path}")
        except Exception as e:
            raise ValueError(f"Failed to read file '{file_path}': {e}")

        lines = original.splitlines()
        start_idx = from_line - 1
        end_idx_inclusive = to_line - 1
        if start_idx > len(lines):
            raise ValueError("from_line exceeds total number of lines in file")

        # Build new content
        before = lines[:start_idx]
        after = lines[end_idx_inclusive + 1 :] if end_idx_inclusive + 1 <= len(lines) else []
        new_lines = content.splitlines()
        merged = before + new_lines + after
        # Join with newlines; preserve trailing newline if present originally
        new_text = "\n".join(merged)
        if original.endswith("\n") or new_text and not new_text.endswith("\n"):
            new_text += "\n"

        # Write back using a here-doc to avoid shell quoting issues
        write_cmd = (
            f"cat > {file_path} << 'MINISWE_EOF'\n"
            + new_text
            + "MINISWE_EOF"
        )
        try:
            self.env.execute(write_cmd)
        except Exception as e:
            raise ValueError(f"Failed to write file '{file_path}': {e}")

        return f"Replaced lines {from_line}-{to_line} in {file_path}."
    
    def show_file(self, file_path: str) -> str:
        """
        [Optional]Show the content of the file
        """
        try:
            # Show file with line numbers for easier referencing
            output = self.env.execute(f"nl -ba {file_path}")
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