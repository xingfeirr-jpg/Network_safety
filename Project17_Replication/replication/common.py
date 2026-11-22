"""Load the shared configuration and build the full command line for each tool.

pipeline.py (runs inside the container) and compare.py (runs on the host) both call
argv(), so the command that is executed and the command that is checked against the
original record come from the same code.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "libraries.json"
TOOLS = (("FF", "flawfinder"), ("CP", "cppcheck"), ("CC", "codechecker"))


def load_config(path=CONFIG):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def expand(text, config, **values):
    text = text.replace("{BASE}", config["base"])
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def run_dir(config, lib, tool_key):
    return f'{config["base"]}/{lib["results_dir"]}/{lib["runs"][tool_key]}'


def build_db(config, lib):
    return f'{config["base"]}/{lib["build_dir"]}/compile_commands.json'


def analysis_db(config, lib, tool_key):
    """Compilation database actually read by Cppcheck or CodeChecker."""
    if tool_key == "CP" and "database" in lib["cppcheck"]:
        return lib["cppcheck"]["database"]["path"]
    if "analysis_db" in lib:
        return lib["analysis_db"]["path"]
    return build_db(config, lib)


def argv(config, lib, tool_key):
    """Return the full command (as a list) for one library and one tool."""
    run = run_dir(config, lib, tool_key)
    if tool_key == "FF":
        tool = config["tools"]["flawfinder"]
        return ([expand(tool["binary"], config), *tool["args"]]
                + [f'{config["base"]}/{item}' for item in lib["flawfinder"]["inputs"]])
    if tool_key == "CP":
        tool = config["tools"]["cppcheck"]
        values = dict(DB=analysis_db(config, lib, "CP"), STD=lib["cppcheck"]["std"], RUN=run)
        return ([expand(tool["binary"], config), *lib["cppcheck"].get("extra_args", [])]
                + [expand(arg, config, **values) for arg in tool["args"]])
    if tool_key == "CC":
        tool = config["tools"]["codechecker"]
        values = dict(DB=analysis_db(config, lib, "CC"), RUN=run)
        return [expand(tool["binary"], config)] + [expand(arg, config, **values) for arg in tool["args"]]
    raise ValueError(tool_key)
