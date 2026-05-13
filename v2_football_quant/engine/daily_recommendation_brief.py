import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from engine.v4_daily_recommendation_brief import main


if __name__ == "__main__":
    main()
