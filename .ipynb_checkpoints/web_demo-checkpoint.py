"""This script refers to the dialogue example of streamlit, the interactive
generation code of chatglm2 and transformers.

We mainly modified part of the code logic to adapt to the
generation of our model.
Please refer to these links below for more information:
    1. streamlit chat example:
        https://docs.streamlit.io/knowledge-base/tutorials/build-conversational-apps
    2. chatglm2:
        https://github.com/THUDM/ChatGLM2-6B
    3. transformers:
        https://github.com/huggingface/transformers
Please run with the command `streamlit run path/to/web_demo.py
    --server.address=0.0.0.0 --server.port 7860`.
Using `python path/to/web_demo.py` may cause unknown problems.
"""
# isort: skip_file
import copy
import warnings
from dataclasses import asdict, dataclass
from typing import Callable, List, Optional

import torch
from torch import nn

import transformers
from transformers.generation.utils import (LogitsProcessorList,
                                           StoppingCriteriaList)
from transformers.utils import logging

from transformers import AutoTokenizer, AutoModelForCausalLM  # isort: skip
from modelscope import snapshot_download, AutoTokenizer, AutoModelForCausalLM
import os
from datetime import datetime


logger = logging.get_logger(__name__)

user_prompt = '<|im_start|>user\n{user}<|im_end|>\n'
robot_prompt = '<|im_start|>assistant\n{robot}<|im_end|>\n'
cur_query_prompt = '<|im_start|>user\n{user}<|im_end|>\n\
    <|im_start|>assistant\n'


class ChatHistory():
    def __init__(self, port, initial_prompt=None):
        self.initial_prompt = initial_prompt
        self.total_prompt = f'<s><|im_start|>system\n{initial_prompt}<|im_end|>\n'
        
        today = datetime.now().strftime("%Y-%m-%d")
        if not os.path.exists(today):
            os.mkdir(today)
        timenow = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        self.log_path = '{folder}/{curtime}_{port}.log'.format(folder=today,curtime=timenow, port=port)

    def combine_history(self, prompt):
        total_prompt = self.total_prompt + cur_query_prompt.format(user=prompt)
        return total_prompt

    def clear_history(self):
        self.total_prompt = f'<s><|im_start|>system\n{self.initial_prompt}<|im_end|>\n'

    def update(self, role, cur_message):
        if role == 'user':
            cur_prompt = user_prompt.format(user=cur_message)
        elif role == 'robot':
            cur_prompt = robot_prompt.format(robot=cur_message)
        else:
            raise RuntimeError

        self.total_prompt += cur_prompt

    def save_history(self):
        with open(self.log_path, 'w', encoding='utf-8') as file:
            # 将字符串写入文件
            file.write(self.total_prompt)


@dataclass
class GenerationConfig:
    # this config is used for chat to provide more diversity
    max_length: int = 32768
    top_p: float = 0.8
    temperature: float = 0.8
    do_sample: bool = True
    repetition_penalty: float = 1.005


@torch.inference_mode()
def generate_interactive(
    model,
    tokenizer,
    prompt,
    generation_config: Optional[GenerationConfig] = None,
    logits_processor: Optional[LogitsProcessorList] = None,
    stopping_criteria: Optional[StoppingCriteriaList] = None,
    prefix_allowed_tokens_fn: Optional[Callable[[int, torch.Tensor],
                                                List[int]]] = None,
    additional_eos_token_id: Optional[int] = None,
    **kwargs,
):
    inputs = tokenizer([prompt], padding=True, return_tensors='pt')
    input_length = len(inputs['input_ids'][0])
    for k, v in inputs.items():
        inputs[k] = v.cuda()
    input_ids = inputs['input_ids']
    _, input_ids_seq_length = input_ids.shape[0], input_ids.shape[-1]
    if generation_config is None:
        generation_config = model.generation_config
    generation_config = copy.deepcopy(generation_config)
    model_kwargs = generation_config.update(**kwargs)
    bos_token_id, eos_token_id = (  # noqa: F841  # pylint: disable=W0612
        generation_config.bos_token_id,
        generation_config.eos_token_id,
    )
    if isinstance(eos_token_id, int):
        eos_token_id = [eos_token_id]
    if additional_eos_token_id is not None:
        eos_token_id.append(additional_eos_token_id)
    has_default_max_length = kwargs.get(
        'max_length') is None and generation_config.max_length is not None
    if has_default_max_length and generation_config.max_new_tokens is None:
        warnings.warn(
            f"Using 'max_length''s default \
                ({repr(generation_config.max_length)}) \
                to control the generation length. "
            'This behaviour is deprecated and will be removed from the \
                config in v5 of Transformers -- we'
            ' recommend using `max_new_tokens` to control the maximum \
                length of the generation.',
            UserWarning,
        )
    elif generation_config.max_new_tokens is not None:
        generation_config.max_length = generation_config.max_new_tokens + \
            input_ids_seq_length
        if not has_default_max_length:
            logger.warn(  # pylint: disable=W4902
                f"Both 'max_new_tokens' (={generation_config.max_new_tokens}) "
                f"and 'max_length'(={generation_config.max_length}) seem to "
                "have been set. 'max_new_tokens' will take precedence. "
                'Please refer to the documentation for more information. '
                '(https://huggingface.co/docs/transformers/main/'
                'en/main_classes/text_generation)',
                UserWarning,
            )

    if input_ids_seq_length >= generation_config.max_length:
        input_ids_string = 'input_ids'
        logger.warning(
            f'Input length of {input_ids_string} is {input_ids_seq_length}, '
            f"but 'max_length' is set to {generation_config.max_length}. "
            'This can lead to unexpected behavior. You should consider'
            " increasing 'max_new_tokens'.")

    # 2. Set generation parameters if not already defined
    logits_processor = logits_processor if logits_processor is not None \
        else LogitsProcessorList()
    stopping_criteria = stopping_criteria if stopping_criteria is not None \
        else StoppingCriteriaList()

    logits_processor = model._get_logits_processor(
        generation_config=generation_config,
        input_ids_seq_length=input_ids_seq_length,
        encoder_input_ids=input_ids,
        prefix_allowed_tokens_fn=prefix_allowed_tokens_fn,
        logits_processor=logits_processor,
    )

    stopping_criteria = model._get_stopping_criteria(
        generation_config=generation_config,
        stopping_criteria=stopping_criteria)

    if transformers.__version__ >= '4.42.0':
        logits_warper = model._get_logits_warper(generation_config,
                                                 device='cuda')
    else:
        logits_warper = model._get_logits_warper(generation_config)

    unfinished_sequences = input_ids.new(input_ids.shape[0]).fill_(1)
    scores = None
    while True:
        model_inputs = model.prepare_inputs_for_generation(
            input_ids, **model_kwargs)
        # forward pass to get next token
        outputs = model(
            **model_inputs,
            return_dict=True,
            output_attentions=False,
            output_hidden_states=False,
        )
        # response, history = model.chat(tokenizer, "hello", history=[])

        next_token_logits = outputs.logits[:, -1, :]

        # pre-process distribution
        next_token_scores = logits_processor(input_ids, next_token_logits)
        next_token_scores = logits_warper(input_ids, next_token_scores)

        # sample
        probs = nn.functional.softmax(next_token_scores, dim=-1)
        if generation_config.do_sample:
            next_tokens = torch.multinomial(probs, num_samples=1).squeeze(1)
        else:
            next_tokens = torch.argmax(probs, dim=-1)

        # update generated ids, model inputs, and length for next step
        input_ids = torch.cat([input_ids, next_tokens[:, None]], dim=-1)
        model_kwargs = model._update_model_kwargs_for_generation(
            outputs, model_kwargs, is_encoder_decoder=False)
        unfinished_sequences = unfinished_sequences.mul(
            (min(next_tokens != i for i in eos_token_id)).long())

        output_token_ids = input_ids[0].cpu().tolist()
        output_token_ids = output_token_ids[input_length:]
        for each_eos_token_id in eos_token_id:
            if output_token_ids[-1] == each_eos_token_id:
                output_token_ids = output_token_ids[:-1]
        response = tokenizer.decode(output_token_ids)

        yield response
        # stop when each sentence is finished
        # or if we exceed the maximum length
        if unfinished_sequences.max() == 0 or stopping_criteria(
                input_ids, scores):
            break


def load_model():
    model_dir = snapshot_download('Shanghai_AI_Laboratory/internlm2_5-7b-chat')
    model = AutoModelForCausalLM.from_pretrained(model_dir, device_map="auto", trust_remote_code=True, torch_dtype=torch.float16)

    tokenizer = AutoTokenizer.from_pretrained(model_dir, device_map="auto", trust_remote_code=True)
    
    return model, tokenizer


def prepare_generation_config(max_length=32768, top_p=0.8, temperature=0.8):

    generation_config = GenerationConfig(max_length=max_length,
                                         top_p=top_p,
                                         temperature=temperature)

    return generation_config


# 接收一次输入并打印推理结果
def chat_once(generation_config, prompt, history, model, tokenizer):
    real_prompt = history.combine_history(prompt)

    history.update('user', prompt)

    privious_response = ""
    for cur_response in generate_interactive(
                model=model,
                tokenizer=tokenizer,
                prompt=real_prompt,
                additional_eos_token_id=92542,
                **asdict(generation_config),
           ):
        # Display robot response
        # if len(cur_response) - len(privious_response) > 2:
        print(cur_response[len(privious_response):], end='')
        privious_response = cur_response
            # print(111)
            
    print(cur_response[len(privious_response):])

    # Add robot response to chat history
    history.update('robot', cur_response)

    torch.cuda.empty_cache()


def main():
    # torch.cuda.empty_cache()
    
    print('load model begin.')
    model, tokenizer = load_model()
    print('load model end.')

    generation_config = prepare_generation_config()

    port = 22
    initial_prompt = "请扮演一位正在和恋人交谈的可靠男性医生，并在每次对话前用【】标注出现在的心情，只使用一个词，例如：【开心】"

    # 创建history类用于存储历史数据
    history = ChatHistory(port, initial_prompt)

    listening = True
    while listening:
        new_prompt = input("你好：")

        if new_prompt == "STOP SERVER!!!":
            history.save_history()
            break
            
        chat_once(generation_config, new_prompt, history, model, tokenizer)


if __name__ == '__main__':
    main()
