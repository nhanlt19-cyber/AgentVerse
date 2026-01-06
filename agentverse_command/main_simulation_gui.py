import os
from agentverse.gui import GUI
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("--task", type=str, default="simulation/nlp_classroom_9players")
parser.add_argument(
    "--tasks_dir",
    type=str,
    default=os.path.join(os.path.dirname(__file__), "..", "agentverse", "tasks"),
)
parser.add_argument(
    "--share",
    action="store_true",
    default=False,
    help="Create a publicly shareable link",
)
parser.add_argument(
    "--server_name",
    type=str,
    default="0.0.0.0",
    help="Server name (use 0.0.0.0 to allow access from other machines in LAN)",
)
parser.add_argument("--debug", action="store_true", default=False, help="Debug mode")
parser.add_argument(
    "--model",
    type=str,
    default=os.environ.get(
        "OLLAMA_MODEL", os.environ.get("LLM_MODEL", "llama3.1:latest")
    ),
    help="Ollama model name to use (overrides task config model)",
)

args = parser.parse_args()


def cli_main():
    if args.model:
        os.environ["OLLAMA_MODEL"] = args.model
        os.environ["LLM_MODEL"] = args.model
    ui = GUI(
        args.task,
        args.tasks_dir,
        ui_kwargs={
            "share": args.share,
            "server_name": args.server_name,
            "debug": args.debug,
        },
    )
    ui.launch()


if __name__ == "__main__":
    cli_main()
