import os
import logging
from argparse import ArgumentParser

from agentverse.logging import logger
from agentverse.simulation import Simulation

parser = ArgumentParser()
parser.add_argument("--task", type=str, default="simulation/prisoner_dilemma")
parser.add_argument(
    "--tasks_dir",
    type=str,
    default=os.path.join(os.path.dirname(__file__), "..", "agentverse", "tasks"),
)
parser.add_argument(
    "--model",
    type=str,
    default=os.environ.get(
        "OLLAMA_MODEL", os.environ.get("LLM_MODEL", "llama3.1:latest")
    ),
    help="Ollama model name to use (overrides task config model)",
)
parser.add_argument("--debug", action="store_true")
args = parser.parse_args()

logger.set_level(logging.DEBUG if args.debug else logging.INFO)


def cli_main():
    # Allow overriding the model via CLI for quick testing of different Ollama models
    if args.model:
        os.environ["OLLAMA_MODEL"] = args.model
        os.environ["LLM_MODEL"] = args.model
    agentverse = Simulation.from_task(args.task, args.tasks_dir)
    agentverse.run()


if __name__ == "__main__":
    cli_main()
