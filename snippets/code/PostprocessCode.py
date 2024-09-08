"""Specialisation for response skill."""
import logging
from typing import List

from snippets.snippet import BaseSnippet

logger = logging.getLogger(__name__)


class PostprocessCode(BaseSnippet):
    def calculate_indent(self, code: str) -> int:
        """
        Calculate the indentation level of the first non-empty line in the given code.

        This function processes the input code to determine the number of leading spaces in the first
        non-empty line. Tabs are replaced with four spaces for consistency.

        :param code: A string representing the code to analyze.
        :return: The number of leading spaces in the first non-empty line.
        """
        if not code:
            return 0

        lines = code.splitlines()
        # Find the first non-empty line
        for line in lines:
            if line.strip():  # Non-empty line
                line = line.replace("\t", " " * 4)
                indent_level = len(line) - len(line.lstrip())
                return indent_level
        return 0

    def indent_code(self, lines: List[str], indent_level: int) -> str:
        """
        Indent the given code to the specified indent level.
        Each line will have the specified number of spaces prefixed.

        :param lines: List of code lines
        :param indent_level: Number of spaces to indent each line.
        :return: Indented code as a multi-line string.
        """
        if not lines:
            return ""
        # Join the lines back into a single string
        indented_code = "\n".join([(" " * indent_level) + line for line in lines])
        return indented_code

    def run(self, query: str, /, **kwargs) -> str:
        """
        Process a query and return corrected code with appropriate indentation.

        This function takes a query, processes it to correct the code within,
        and returns the corrected code with the original indentation level.

        :param query: The input query containing a programmer task.
        :param kwargs: Additional keyword arguments for the processing.
        :return: Corrected code with the original indentation.
        """
        indent_level = self.calculate_indent(query)
        ret = super().run(query, **kwargs)
        query = f"""
        Here is the code with explanation:
        ```
        {ret}
        ```
        Review the code above, make corrections and return only the code without any examples or test.
        Return as Markdown code.
        """
        ret = super().run(query, **kwargs)
        s_ret = ret.splitlines()
        id_start = 1 if "```" in s_ret[0] else 0
        id_stop = -1 if "```" in s_ret[-1] else None
        return self.indent_code(s_ret[id_start:id_stop], indent_level)
