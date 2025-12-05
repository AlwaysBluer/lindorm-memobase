import os
from collections import defaultdict
from tqdm import tqdm
import httpx
import json
import time
import asyncio
from jinja2 import Template
from openai import OpenAI
from prompts import ANSWER_PROMPT

from .memobase_add import string_to_uuid
from dotenv import load_dotenv
from lindormmemobase import LindormMemobase
from lindormmemobase.models.blob import OpenAICompatibleMessage

root_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(root_dir, "config.yaml")

load_dotenv()


class LindormMemobaseSearchSync:

    def __init__(
            self,
            output_path="./lindorm-output/results.json",
            top_k=10,
            max_memory_context_size=4000,
    ):
        if os.path.exists(config_path):
            self.memobase = LindormMemobase.from_yaml_file(config_path)
        self.top_k = top_k
        http_client = httpx.Client(
            headers={
                "x-ld-ak": os.getenv("LINDORM_USERNAME"),
                "x-ld-sk": os.getenv("LINDORM_PASSWORD")
            }
        )
        self.lindormai_client = OpenAI(
            base_url=os.environ.get("LINDORM_AI_URL"),
            api_key="dummy",
            http_client=http_client,
        )
        if not os.path.exists(output_path):
            self.results = defaultdict(list)
        else:
            with open(output_path, "r") as f:
                self.results = json.load(f)
        self.output_path = output_path
        self.max_memory_context_size = max_memory_context_size
        self.ANSWER_PROMPT = ANSWER_PROMPT

    def search_memory(self, user_id, query, max_retries=3, retry_delay=1):
        """同步版本的 search_memory，使用 asyncio.run 包装异步调用"""
        memories = ""
        retries = 0
        real_uid = string_to_uuid(user_id)
        start_time = time.time()

        while retries < max_retries:
            try:
                # 使用 asyncio.run 来执行异步方法
                memories = asyncio.run(
                    self.memobase.get_conversation_context(
                        user_id=real_uid,
                        conversation=[OpenAICompatibleMessage(role="user", content=query)],
                        max_token_size=2048,
                        time_range_in_days=60,
                        event_similarity_threshold=0.7,
                    )
                )
                print(f"user_id: {user_id}, memories: {memories}")
                break
            except Exception as e:
                print(f"ServerError: {e}")
                print("Retrying...")
                retries += 1
                if retries >= max_retries:
                    raise e
                time.sleep(retry_delay)

        end_time = time.time()
        return memories, end_time - start_time

    def answer_question(
            self, speaker_1_user_id, speaker_2_user_id, question, answer, category
    ):
        """同步版本的 answer_question"""
        # 串行执行两个搜索
        speaker_1_memories, speaker_1_memory_time = self.search_memory(speaker_1_user_id, question)
        speaker_2_memories, speaker_2_memory_time = self.search_memory(speaker_2_user_id, question)

        template = Template(self.ANSWER_PROMPT)
        answer_prompt = template.render(
            speaker_1_user_id=speaker_1_user_id.split("_")[0],
            speaker_2_user_id=speaker_2_user_id.split("_")[0],
            speaker_1_memories=speaker_1_memories,
            speaker_2_memories=speaker_2_memories,
            question=question,
        )

        t1 = time.time()
        response = self.lindormai_client.chat.completions.create(
            model=os.getenv("MODEL", "qwen-max-latest"),
            messages=[{"role": "system", "content": answer_prompt}],
            temperature=0.0,
        )
        t2 = time.time()
        response_time = t2 - t1
        return (
            response.choices[0].message.content,
            speaker_1_memories,
            speaker_2_memories,
            speaker_1_memory_time,
            speaker_2_memory_time,
            response_time,
        )

    def process_question(self, val, speaker_a_user_id, speaker_b_user_id):
        """同步版本的 process_question"""
        question = val.get("question", "")
        answer = val.get("answer", "")
        category = val.get("category", -1)
        evidence = val.get("evidence", [])
        adversarial_answer = val.get("adversarial_answer", "")

        (
            response,
            speaker_1_memories,
            speaker_2_memories,
            speaker_1_memory_time,
            speaker_2_memory_time,
            response_time,
        ) = self.answer_question(
            speaker_a_user_id, speaker_b_user_id, question, answer, category
        )

        result = {
            "question": question,
            "answer": answer,
            "category": category,
            "evidence": evidence,
            "response": response,
            "adversarial_answer": adversarial_answer,
            "speaker_1_memories": speaker_1_memories,
            "speaker_2_memories": speaker_2_memories,
            "num_speaker_1_memories": len(speaker_1_memories),
            "num_speaker_2_memories": len(speaker_2_memories),
            "speaker_1_memory_time": speaker_1_memory_time,
            "speaker_2_memory_time": speaker_2_memory_time,
            "response_time": response_time,
        }

        # Save results after each question is processed
        with open(self.output_path, "w") as f:
            json.dump(self.results, f, indent=4)

        return result

    def process_data_file(self, file_path, exclude_category={5}):
        """同步版本的 process_data_file"""
        with open(file_path, "r") as f:
            data = json.load(f)

        for idx, item in tqdm(
                enumerate(data), total=len(data), desc="Processing conversations"
        ):
            if str(idx) in self.results:
                print(f"Skipping {idx} because it already exists")
                continue

            self.results[idx] = []
            qa = item["qa"]
            conversation = item["conversation"]
            speaker_a = conversation["speaker_a"]
            speaker_b = conversation["speaker_b"]
            qa_filtered = [
                i for i in qa if i.get("category", -1) not in exclude_category
            ]
            speaker_a_user_id = f"{speaker_a}_{idx}"
            speaker_b_user_id = f"{speaker_b}_{idx}"
            print(
                f"Filter category: {exclude_category}, {len(qa)} -> {len(qa_filtered)}"
            )

            results = self.process_questions(
                qa_filtered,
                speaker_a_user_id,
                speaker_b_user_id,
            )
            self.results[idx].extend(results)
            with open(self.output_path, "w") as f:
                json.dump(self.results, f, indent=4)

        # Final save at the end
        with open(self.output_path, "w") as f:
            json.dump(self.results, f, indent=4)

    def process_questions(
            self, qa_list, speaker_a_user_id, speaker_b_user_id
    ):
        """同步版本的 process_questions"""
        results = []
        for val in tqdm(qa_list, desc="Answering Questions"):
            result = self.process_question(val, speaker_a_user_id, speaker_b_user_id)
            results.append(result)

        return results
