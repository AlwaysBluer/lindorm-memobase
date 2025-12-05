from src.lindorm_memobase_client import LindormMemobaseADDSync

if __name__ == "__main__":
    memobase_manager = LindormMemobaseADDSync(
        data_path="datasets/locomo10.json",
        timeout=60  # 设置60秒超时
    )
    memobase_manager.process_all_conversations(flush_on_client=False, max_samples=1)
