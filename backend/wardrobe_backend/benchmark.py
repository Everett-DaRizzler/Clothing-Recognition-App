from .config import Settings
from .db import Database
from .evaluation import score
if __name__ == "__main__":
    db=Database(Settings().db_path); rows=db.benchmark_rows(); print({"items":len(rows),"evaluation":score(db.predictions(), [__import__('json').loads(r["payload_json"]) for r in rows])})
