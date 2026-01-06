import logging
import json
import ast
import os
import numpy as np
from aiohttp import ClientSession
from typing import Dict, List, Optional, Union
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from pydantic import Field

from agentverse.llms.base import LLMResult
from agentverse.logging import logger
from agentverse.message import Message

from . import llm_registry, LOCAL_LLMS, LOCAL_LLMS_MAPPING
from .base import BaseChatModel, BaseModelArgs
from .utils.jsonrepair import JsonRepair
from .utils.llm_server_utils import get_llm_server_modelname

try:
    from openai import OpenAI, AsyncOpenAI
    from openai import OpenAIError
    from openai import AzureOpenAI, AsyncAzureOpenAI
except ImportError:
    is_openai_available = False
    logger.warn(
        "openai package is not installed. Please install it via `pip install openai`"
    )
else:
    api_key = None
    base_url = None
    model_name = None

    # Standard OpenAI / Azure configuration
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL")
    AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
    AZURE_API_BASE = os.environ.get("AZURE_OPENAI_API_BASE")

    # Local LLM / vLLM configuration
    VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL")
    VLLM_API_KEY = os.environ.get("VLLM_API_KEY", "EMPTY")

    # Ollama configuration (OpenAI-compatible HTTP API)
    # Example: OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:latest")

    if OPENAI_API_KEY:
        # Cloud OpenAI
        DEFAULT_CLIENT = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        DEFAULT_CLIENT_ASYNC = AsyncOpenAI(
            api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL
        )
        api_key = OPENAI_API_KEY
        base_url = OPENAI_BASE_URL
    elif AZURE_API_KEY:
        # Azure OpenAI
        DEFAULT_CLIENT = AzureOpenAI(
            api_key=AZURE_API_KEY,
            azure_endpoint=AZURE_API_BASE,
            api_version="2024-02-15-preview",
        )
        DEFAULT_CLIENT_ASYNC = AsyncAzureOpenAI(
            api_key=AZURE_API_KEY,
            azure_endpoint=AZURE_API_BASE,
        )
        api_key = AZURE_API_KEY
        base_url = AZURE_API_BASE
    else:
        # Fallback to local Ollama (no real API key required).
        # This assumes Ollama is running with OpenAI-compatible endpoints.
        logger.info(
            f"No OPENAI_API_KEY or AZURE_OPENAI_API_KEY found. "
            f"Falling back to local Ollama at {OLLAMA_BASE_URL}."
        )
        DEFAULT_CLIENT = OpenAI(api_key="EMPTY", base_url=OLLAMA_BASE_URL)
        DEFAULT_CLIENT_ASYNC = AsyncOpenAI(api_key="EMPTY", base_url=OLLAMA_BASE_URL)
        api_key = "EMPTY"
        base_url = OLLAMA_BASE_URL

        # Register Ollama model as a local LLM so it can be referenced in configs
        if OLLAMA_MODEL not in LOCAL_LLMS:
            LOCAL_LLMS.append(OLLAMA_MODEL)
            LOCAL_LLMS_MAPPING[OLLAMA_MODEL] = {
                "hf_model_name": OLLAMA_MODEL,
                "base_url": OLLAMA_BASE_URL,
                "api_key": "EMPTY",
            }

    # vLLM-style backends (kept for backwards compatibility)
    if VLLM_BASE_URL:
        if model_name := get_llm_server_modelname(VLLM_BASE_URL, VLLM_API_KEY, logger):
            # model_name = /mnt/llama/hf_models/TheBloke_Llama-2-70B-Chat-GPTQ
            # transform to TheBloke/Llama-2-70B-Chat-GPTQ
            hf_model_name = model_name.split("/")[-1].replace("_", "/")
            LOCAL_LLMS.append(model_name)
            LOCAL_LLMS_MAPPING[model_name] = {
                "hf_model_name": hf_model_name,
                "base_url": VLLM_BASE_URL,
                "api_key": VLLM_API_KEY if VLLM_API_KEY else "EMPTY",
            }
            logger.info(f"Using vLLM model: {hf_model_name}")

    if hf_model_name := get_llm_server_modelname(
        "http://localhost:5000", logger=logger
    ):
        # meta-llama/Llama-2-7b-chat-hf
        # transform to llama-2-7b-chat-hf
        short_model_name = model_name.split("/")[-1].lower()
        LOCAL_LLMS.append(short_model_name)
        LOCAL_LLMS_MAPPING[short_model_name] = {
            "hf_model_name": hf_model_name,
            "base_url": "http://localhost:5000/v1",
            "api_key": "EMPTY",
        }

        logger.info(f"Using FSChat model: {model_name}")


class OpenAIChatArgs(BaseModelArgs):
    model: str = Field(default="gpt-3.5-turbo")
    max_tokens: int = Field(default=2048)
    temperature: float = Field(default=1.0)
    top_p: int = Field(default=1)
    n: int = Field(default=1)
    stop: Optional[Union[str, List]] = Field(default=None)
    presence_penalty: int = Field(default=0)
    frequency_penalty: int = Field(default=0)


# class OpenAICompletionArgs(OpenAIChatArgs):
#     model: str = Field(default="text-davinci-003")
#     suffix: str = Field(default="")
#     best_of: int = Field(default=1)


# @llm_registry.register("text-davinci-003")
# class OpenAICompletion(BaseCompletionModel):
#     args: OpenAICompletionArgs = Field(default_factory=OpenAICompletionArgs)

#     def __init__(self, max_retry: int = 3, **kwargs):
#         args = OpenAICompletionArgs()
#         args = args.dict()
#         for k, v in args.items():
#             args[k] = kwargs.pop(k, v)
#         if len(kwargs) > 0:
#             logging.warning(f"Unused arguments: {kwargs}")
#         super().__init__(args=args, max_retry=max_retry)

#     def generate_response(self, prompt: str) -> LLMResult:
#         response = openai.Completion.create(prompt=prompt, **self.args.dict())
#         return LLMResult(
#             content=response["choices"][0]["text"],
#             send_tokens=response["usage"]["prompt_tokens"],
#             recv_tokens=response["usage"]["completion_tokens"],
#             total_tokens=response["usage"]["total_tokens"],
#         )

#     async def agenerate_response(self, prompt: str) -> LLMResult:
#         response = await openai.Completion.acreate(prompt=prompt, **self.args.dict())
#         return LLMResult(
#             content=response["choices"][0]["text"],
#             send_tokens=response["usage"]["prompt_tokens"],
#             recv_tokens=response["usage"]["completion_tokens"],
#             total_tokens=response["usage"]["total_tokens"],
#         )


# To support your own local LLMs, register it here and add it into LOCAL_LLMS.
@llm_registry.register("gpt-35-turbo")
@llm_registry.register("gpt-3.5-turbo")
@llm_registry.register("gpt-4")
@llm_registry.register("vllm")
@llm_registry.register("local")
class OpenAIChat(BaseChatModel):
    args: OpenAIChatArgs = Field(default_factory=OpenAIChatArgs)
    client_args: Optional[Dict] = Field(
        default={"api_key": api_key, "base_url": base_url}
    )
    is_azure: bool = Field(default=False)

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    def __init__(self, max_retry: int = 3, **kwargs):
        args = OpenAIChatArgs()
        args = args.dict()
        client_args = {"api_key": api_key, "base_url": base_url}
        # check if api_key is an azure key
        is_azure = False
        if AZURE_API_KEY and not OPENAI_API_KEY:
            is_azure = True
        for k, v in args.items():
            args[k] = kwargs.pop(k, v)
        if len(kwargs) > 0:
            logger.warn(f"Unused arguments: {kwargs}")

        # If we are in "pure local Ollama" mode (no OpenAI/Azure keys, using OLLAMA_BASE_URL)
        # and the requested model does not correspond to a known local model,
        # transparently route all requests to the configured Ollama model instead.
        #
        # This avoids 404 errors like "model 'gpt-4' not found" when task configs
        # still reference OpenAI model names.
        if (
            not OPENAI_API_KEY
            and not AZURE_API_KEY
            and base_url == OLLAMA_BASE_URL
            and args.get("model") not in LOCAL_LLMS
        ):
            logger.info(
                f"Overriding model '{args.get('model')}' with local Ollama model '{OLLAMA_MODEL}'"
            )
            args["model"] = OLLAMA_MODEL

        if args["model"] in LOCAL_LLMS:
            if args["model"] in LOCAL_LLMS_MAPPING:
                client_args["api_key"] = LOCAL_LLMS_MAPPING[args["model"]]["api_key"]
                client_args["base_url"] = LOCAL_LLMS_MAPPING[args["model"]]["base_url"]
                is_azure = False
            else:
                raise ValueError(
                    f"Model {args['model']} not found in LOCAL_LLMS_MAPPING"
                )
        super().__init__(
            args=args, max_retry=max_retry, client_args=client_args, is_azure=is_azure
        )

    @classmethod
    def send_token_limit(self, model: str) -> int:
        send_token_limit_dict = {
            "gpt-3.5-turbo": 4096,
            "gpt-35-turbo": 4096,
            "gpt-3.5-turbo-16k": 16384,
            "gpt-3.5-turbo-0613": 16384,
            "gpt-3.5-turbo-1106": 16384,
            "gpt-3.5-turbo-0125": 16384,
            "gpt-4": 8192,
            "gpt-4-32k": 32768,
            "gpt-4-0613": 32768,
            "gpt-4-1106-preview": 131072,
            "gpt-4-0125-preview": 131072,
            "llama-2-7b-chat-hf": 4096,
        }
        # Default to 4096 tokens if model is not in the dictionary
        return send_token_limit_dict[model] if model in send_token_limit_dict else 4096

    # @retry(
    #     stop=stop_after_attempt(20),
    #     wait=wait_exponential(multiplier=1, min=4, max=10),
    #     reraise=True,
    #     retry=retry_if_exception_type(
    #         exception_types=(OpenAIError, json.decoder.JSONDecodeError, Exception)
    #     ),
    # )
    def generate_response(
        self,
        prepend_prompt: str = "",
        history: List[dict] = [],
        append_prompt: str = "",
        functions: List[dict] = [],
    ) -> LLMResult:
        messages = self.construct_messages(prepend_prompt, history, append_prompt)
        logger.log_prompt(messages)
        if self.is_azure:
            openai_client = AzureOpenAI(
                api_key=self.client_args["api_key"],
                azure_endpoint=self.client_args["base_url"],
                api_version="2024-02-15-preview",
            )
        else:
            openai_client = OpenAI(
                api_key=self.client_args["api_key"],
                base_url=self.client_args["base_url"],
            )
        try:
            # Execute function call
            if functions != []:
                response = openai_client.chat.completions.create(
                    messages=messages,
                    functions=functions,
                    **self.args.dict(),
                )

                logger.log_prompt(
                    [
                        {
                            "role": "assistant",
                            "content": response.choices[0].message.content,
                        }
                    ]
                )
                if response.choices[0].message.function_call is not None:
                    self.collect_metrics(response)

                    return LLMResult(
                        content=response.choices[0].message.get("content", ""),
                        function_name=response.choices[0].message.function_call.name,
                        function_arguments=ast.literal_eval(
                            response.choices[0].message.function_call.arguments
                        ),
                        send_tokens=response.usage.prompt_tokens,
                        recv_tokens=response.usage.completion_tokens,
                        total_tokens=response.usage.total_tokens,
                    )
                else:
                    self.collect_metrics(response)
                    logger.log_prompt(
                        {
                            "role": "assistant",
                            "content": response.choices[0].message.content,
                        }
                    )
                    return LLMResult(
                        content=response.choices[0].message.content,
                        send_tokens=response.usage.prompt_tokens,
                        recv_tokens=response.usage.completion_tokens,
                        total_tokens=response.usage.total_tokens,
                    )

            else:
                response = openai_client.chat.completions.create(
                    messages=messages,
                    **self.args.dict(),
                )
                logger.log_prompt(
                    [
                        {
                            "role": "assistant",
                            "content": response.choices[0].message.content,
                        }
                    ]
                )
                self.collect_metrics(response)
                return LLMResult(
                    content=response.choices[0].message.content,
                    send_tokens=response.usage.prompt_tokens,
                    recv_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                )
        except (OpenAIError, KeyboardInterrupt, json.decoder.JSONDecodeError) as error:
            raise

    # @retry(
    #     stop=stop_after_attempt(20),
    #     wait=wait_exponential(multiplier=1, min=4, max=10),
    #     reraise=True,
    #     retry=retry_if_exception_type(
    #         exception_types=(OpenAIError, json.decoder.JSONDecodeError, Exception)
    #     ),
    # )
    async def agenerate_response(
        self,
        prepend_prompt: str = "",
        history: List[dict] = [],
        append_prompt: str = "",
        functions: List[dict] = [],
    ) -> LLMResult:
        messages = self.construct_messages(prepend_prompt, history, append_prompt)
        logger.log_prompt(messages)

        if self.is_azure:
            async_openai_client = AsyncAzureOpenAI(
                api_key=self.client_args["api_key"],
                azure_endpoint=self.client_args["base_url"],
                api_version="2024-02-15-preview",
            )
        else:
            async_openai_client = AsyncOpenAI(
                api_key=self.client_args["api_key"],
                base_url=self.client_args["base_url"],
            )
        try:
            if functions != []:
                response = await async_openai_client.chat.completions.create(
                    messages=messages,
                    functions=functions,
                    **self.args.dict(),
                )
                logger.log_prompt(
                    [
                        {
                            "role": "assistant",
                            "content": response.choices[0].message.content,
                        }
                    ]
                )
                if response.choices[0].message.function_call is not None:
                    function_name = response.choices[0].message.function_call.name
                    valid_function = False
                    if function_name.startswith("function."):
                        function_name = function_name.replace("function.", "")
                    elif function_name.startswith("functions."):
                        function_name = function_name.replace("functions.", "")
                    for function in functions:
                        if function["name"] == function_name:
                            valid_function = True
                            break
                    if not valid_function:
                        logger.warn(
                            f"The returned function name {function_name} is not in the list of valid functions. Retrying..."
                        )
                        raise ValueError(
                            f"The returned function name {function_name} is not in the list of valid functions."
                        )
                    try:
                        arguments = ast.literal_eval(
                            response.choices[0].message.function_call.arguments
                        )
                    except:
                        try:
                            arguments = ast.literal_eval(
                                JsonRepair(
                                    response.choices[0].message.function_call.arguments
                                ).repair()
                            )
                        except:
                            logger.warn(
                                "The returned argument in function call is not valid json. Retrying..."
                            )
                            raise ValueError(
                                "The returned argument in function call is not valid json."
                            )
                    self.collect_metrics(response)
                    logger.log_prompt(
                        {
                            "role": "assistant",
                            "content": response.choices[0].message.content,
                        }
                    )
                    return LLMResult(
                        function_name=function_name,
                        function_arguments=arguments,
                        send_tokens=response.usage.prompt_tokens,
                        recv_tokens=response.usage.completion_tokens,
                        total_tokens=response.usage.total_tokens,
                    )

                else:
                    self.collect_metrics(response)
                    logger.log_prompt(
                        {
                            "role": "assistant",
                            "content": response.choices[0].message.content,
                        }
                    )
                    return LLMResult(
                        content=response.choices[0].message.content,
                        send_tokens=response.usage.prompt_tokens,
                        recv_tokens=response.usage.completion_tokens,
                        total_tokens=response.usage.total_tokens,
                    )

            else:

                response = await async_openai_client.chat.completions.create(
                    messages=messages,
                    **self.args.dict(),
                )
                self.collect_metrics(response)
                logger.log_prompt(
                    [
                        {
                            "role": "assistant",
                            "content": response.choices[0].message.content,
                        }
                    ]
                )
                return LLMResult(
                    content=response.choices[0].message.content,
                    send_tokens=response.usage.prompt_tokens,
                    recv_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                )
        except (OpenAIError, KeyboardInterrupt, json.decoder.JSONDecodeError) as error:
            raise

    def construct_messages(
        self, prepend_prompt: str, history: List[dict], append_prompt: str
    ):
        messages = []
        if prepend_prompt != "":
            messages.append({"role": "system", "content": prepend_prompt})
        if len(history) > 0:
            messages += history
        if append_prompt != "":
            messages.append({"role": "user", "content": append_prompt})
        return messages

    def collect_metrics(self, response):
        self.total_prompt_tokens += response.usage.prompt_tokens
        self.total_completion_tokens += response.usage.completion_tokens

    def get_spend(self) -> int:
        input_cost_map = {
            "gpt-3.5-turbo": 0.0015,
            "gpt-3.5-turbo-16k": 0.003,
            "gpt-3.5-turbo-0613": 0.0015,
            "gpt-3.5-turbo-16k-0613": 0.003,
            "gpt-3.5-turbo-1106": 0.0005,
            "gpt-3.5-turbo-0125": 0.0005,
            "gpt-4": 0.03,
            "gpt-4-0613": 0.03,
            "gpt-4-32k": 0.06,
            "gpt-4-1106-preview": 0.01,
            "gpt-4-0125-preview": 0.01,
            "llama-2-7b-chat-hf": 0.0,
        }

        output_cost_map = {
            "gpt-3.5-turbo": 0.002,
            "gpt-3.5-turbo-16k": 0.004,
            "gpt-3.5-turbo-0613": 0.002,
            "gpt-3.5-turbo-16k-0613": 0.004,
            "gpt-3.5-turbo-1106": 0.0015,
            "gpt-3.5-turbo-0125": 0.0015,
            "gpt-4": 0.06,
            "gpt-4-0613": 0.06,
            "gpt-4-32k": 0.12,
            "gpt-4-1106-preview": 0.03,
            "gpt-4-0125-preview": 0.03,
            "llama-2-7b-chat-hf": 0.0,
            # Local / Ollama models default to 0 cost; extend as needed.
            "llama3.1:latest": 0.0,
            "llama3.1:latest": 0.0,
        }

        model = self.args.model
        # For unknown models, assume zero cost instead of raising.
        input_cost = input_cost_map.get(model, 0.0)
        output_cost = output_cost_map.get(model, 0.0)

        return (
            self.total_prompt_tokens * input_cost / 1000.0
            + self.total_completion_tokens * output_cost / 1000.0
        )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
def get_embedding(text: str, attempts=3) -> np.array:
    """
    Get embeddings for a given text.

    - If Azure / OpenAI keys are configured, use them.
    - Otherwise, fall back to the same backend as DEFAULT_CLIENT, which for your
      use case will typically be a local Ollama server exposing an OpenAI-compatible API.
    """
    # Prefer the same configuration as DEFAULT_CLIENT
    client: Union[OpenAI, AzureOpenAI]
    embedding_model = os.environ.get("EMBEDDING_MODEL", "llama3.1:latest")

    if AZURE_API_KEY and AZURE_API_BASE:
        client = AzureOpenAI(
            api_key=AZURE_API_KEY,
            azure_endpoint=AZURE_API_BASE,
            api_version="2024-02-15-preview",
        )
    elif OPENAI_API_KEY:
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    else:
        # Fall back to the same base_url used for chat (e.g. Ollama)
        client = DEFAULT_CLIENT

    try:
        text = text.replace("\n", " ")
        response = client.embeddings.create(input=text, model=embedding_model)
        # openai>=1 style response: response.data[0].embedding is a List[float]
        return np.array(response.data[0].embedding, dtype=float)
    except Exception as e:
        logger.error(f"Error {e} when requesting openai models. Retrying")
        raise
