import uuid
import json
import os
import asyncio
from dotenv import load_dotenv
from lindormmemobase import LindormMemobase, ChatBlob, Config
from lindormmemobase.models.blob import OpenAICompatibleMessage, BlobType

load_dotenv()

root_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(root_dir, "config.yaml")


def string_to_uuid(s: str, salt="memobase_client") -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, s + salt))


class LindormMemobaseADDSync:
    def __init__(self, data_path, batch_size=12, reprocess=False, timeout=30):
        if os.path.exists(config_path):
            config = Config.load_config(config_path)
            self.memobase = LindormMemobase(config)
        else:
            raise FileNotFoundError(f"Config file not found: {config_path}")

        self.batch_size = batch_size
        self.data_path = data_path
        self.data = None
        self.reprocess = reprocess
        self.timeout = timeout  # 添加超时设置
        if data_path:
            self.load_data()

    def load_data(self):
        with open(self.data_path, "r") as f:
            self.data = json.load(f)
        print(f"✓ 加载了 {len(self.data)} 条数据")
        return self.data

    async def force_flush_unprocessed_memory(self, user_id):
        real_user_id = string_to_uuid(user_id)
        print(f"   正在强制刷新用户 {user_id} 的缓冲区...")
        try:
            result = await asyncio.wait_for(
                self.memobase.process_buffer(
                    user_id=real_user_id,
                    blob_type=BlobType.chat
                ),
                timeout=self.timeout
            )
            if result:
                print(f"   ✓ 缓冲区处理完成")
            else:
                print(f"   ⚠ 缓冲区处理返回空结果")
        except asyncio.TimeoutError:
            print(f"   ✗ 缓冲区处理超时 ({self.timeout}秒)")
            raise

    async def add_memory(self, user_id, messages, flush_on_client=False):
        real_user_id = string_to_uuid(user_id)

        # 调试信息
        print(f"   正在添加 {len(messages)} 条消息到用户 {user_id}...")
        print(f"   real_user_id: {real_user_id}")
        print(f"   消息示例: {messages[0] if messages else 'N/A'}")

        # 创建 blobs
        try:
            blobs = [OpenAICompatibleMessage(**message) for message in messages]
            print(f"   ✓ 成功创建 {len(blobs)} 个消息对象")
        except Exception as e:
            print(f"   ✗ 创建消息对象失败: {e}")
            raise

        blob_ids = await asyncio.wait_for(
            self.memobase.add_blob_to_buffer(real_user_id, ChatBlob(messages=blobs)),
            timeout=self.timeout
        )

        print(f"   ✓ 对话块 {len(blob_ids) if blob_ids else 0} 已添加: {blob_ids}")

        if flush_on_client:
            print(f"   检查缓冲区状态...")
            status = await asyncio.wait_for(
                self.memobase.detect_buffer_full_or_not(real_user_id, BlobType.chat),
                timeout=self.timeout
            )
            print(f"   缓冲区状态: {status}")

            if status.get("is_full"):
                print(f"   缓冲区已满，自动处理 {len(status.get('buffer_full_ids', []))} 个数据块...")
                result = await asyncio.wait_for(
                    self.memobase.process_buffer(
                        user_id=real_user_id,
                        blob_type=BlobType.chat,
                        blob_ids=status["buffer_full_ids"]
                    ),
                    timeout=self.timeout * 2  # 处理缓冲区可能需要更长时间
                )
                if result:
                    print(f"   ✓ 缓冲区处理完成")
                else:
                    print(f"   ⚠ 缓冲区处理返回空结果")



    async def add_memories_for_speaker(self, speaker, messages, desc, flush_on_client=False):
        print(f"\n开始处理: {desc}, 共 {len(messages)} 条消息")

        # 计算批次数量
        num_batches = (len(messages) + self.batch_size - 1) // self.batch_size

        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(messages))
            batch_messages = messages[start_idx:end_idx]

            print(f"  批次 {batch_idx + 1}/{num_batches}: 处理消息 {start_idx} - {end_idx}")
            await self.add_memory(speaker, batch_messages, flush_on_client)
            print(f"  ✓ 批次 {batch_idx + 1}/{num_batches} 完成")

        if flush_on_client:
            await self.force_flush_unprocessed_memory(speaker)

    async def process_conversation(self, item, idx, flush_on_client=False):
        print(f"\n{'=' * 60}")
        print(f"处理对话 {idx}")
        print(f"{'=' * 60}")

        conversation = item["conversation"]
        speaker_a = conversation["speaker_a"]
        speaker_b = conversation["speaker_b"]

        speaker_a_user_id = f"{speaker_a}_{idx}"
        speaker_b_user_id = f"{speaker_b}_{idx}"

        print(f"说话人A: {speaker_a} (用户ID: {speaker_a_user_id})")
        print(f"说话人B: {speaker_b} (用户ID: {speaker_b_user_id})")

        conversation_keys = [k for k in conversation.keys()
                             if k not in ["speaker_a", "speaker_b"]
                             and "date" not in k
                             and "timestamp" not in k]

        print(f"找到 {len(conversation_keys)} 个对话片段")

        for key in conversation_keys:
            print(f"\n处理对话片段: {key}")
            date_time_key = key + "_date_time"
            timestamp = conversation.get(date_time_key)
            chats = conversation[key]

            print(f"  时间戳: {timestamp}")
            print(f"  聊天记录数: {len(chats)}")

            messages = []
            messages_reverse = []
            for chat in chats:
                if chat["speaker"] == speaker_a:
                    messages.append({
                        "role": "user",
                        "content": chat["text"],
                        "alias": speaker_a,
                        "created_at": timestamp,
                    })
                    messages_reverse.append({
                        "role": "assistant",
                        "content": chat["text"],
                        "alias": speaker_a,
                        "created_at": timestamp,
                    })
                elif chat["speaker"] == speaker_b:
                    messages.append({
                        "role": "assistant",
                        "content": chat["text"],
                        "alias": speaker_b,
                        "created_at": timestamp,
                    })
                    messages_reverse.append({
                        "role": "user",
                        "content": chat["text"],
                        "alias": speaker_b,
                        "created_at": timestamp,
                    })
                else:
                    raise ValueError(f"Unknown speaker: {chat['speaker']}")

            # 串行处理
            await self.add_memories_for_speaker(
                speaker_a_user_id,
                messages,
                f"[{idx}] 添加记忆 - {speaker_a}",
                flush_on_client,
            )
            await self.add_memories_for_speaker(
                speaker_b_user_id,
                messages_reverse,
                f"[{idx}] 添加记忆 - {speaker_b}",
                flush_on_client,
            )

        print(f"\n✓ 对话 {idx} 处理完成")

    async def process_all_conversations_async(self, max_samples=None, flush_on_client=False):
        """异步串行处理所有对话"""
        if not self.data:
            raise ValueError(
                "No data loaded. Please set data_path and call load_data() first."
            )

        data_to_process = self.data[:max_samples] if max_samples else self.data
        print(f"\n开始处理 {len(data_to_process)} 个对话")
        print(f"flush_on_client: {flush_on_client}")
        print(f"timeout: {self.timeout}秒")

        for idx, item in enumerate(data_to_process):
            await self.process_conversation(item, idx, flush_on_client)

        print(f"\n{'=' * 60}")
        print(f"✓ 所有对话处理完成!")
        print(f"{'=' * 60}")

    def process_all_conversations(self, max_samples=None, flush_on_client=False):
        """同步入口：串行处理所有对话"""
        asyncio.run(self.process_all_conversations_async(max_samples, flush_on_client))
