from src.lindorm_memobase_client import LindormMemobaseSearchSync

if __name__ == "__main__":
    memobase_manager = LindormMemobaseSearchSync()
    memobase_manager.process_data_file("datasets/locomo10.json")
