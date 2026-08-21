import sys
from colorama import Fore, Style
from enum import Enum


class AgentColor(Enum):
    RESEARCHER = Fore.LIGHTBLUE_EX
    EDITOR = Fore.YELLOW
    WRITER = Fore.LIGHTGREEN_EX
    PUBLISHER = Fore.MAGENTA
    REVIEWER = Fore.CYAN
    REVISOR = Fore.LIGHTWHITE_EX
    MASTER = Fore.LIGHTYELLOW_EX
    FACT_CHECKER = Fore.LIGHTCYAN_EX
    VISUALIZER = Fore.LIGHTMAGENTA_EX


def print_agent_output(output:str, agent: str="RESEARCHER"):
    # Handle Unicode output on Windows with cp1252 encoding
    try:
        print(f"{AgentColor[agent].value}{agent}: {output}{Style.RESET_ALL}")
    except UnicodeEncodeError:
        # Fallback: encode to cp1252, replacing unsupported characters
        encoded_output = f"{AgentColor[agent].value}{agent}: {output}{Style.RESET_ALL}"
        print(encoded_output.encode('cp1252', errors='replace').decode('cp1252'))