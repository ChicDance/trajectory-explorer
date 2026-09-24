from pathlib import Path

from tasi.dlr import DLRUTDatasetManager

CACHE_DIR = Path(__file__).resolve().parent.parent / "data_cache"


def main() -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    manager = DLRUTDatasetManager(version="latest", path=str(CACHE_DIR))
    print(f"Loading {manager.name} into {CACHE_DIR} ...")
    export_path = manager.load()
    print(f"Done. Dataset at: {export_path}")
    for f in manager.trajectory(path=CACHE_DIR):
        print(" traj file:", f)


if __name__ == "__main__":
    main()
