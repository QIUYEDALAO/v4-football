"""
日志 + 告警模块 v1.0
========================
统一日志管理：
  - 控制台输出 INFO 级别
  - 文件输出 DEBUG 级别（每日轮转、保留30天）
  - 关键事件自动记录结构化日志
  - 预留 Telegram 告警接口

用法：
  from logger import logger, log_event
  logger.info("每日推荐已生成")
  log_event("RECOMMEND", {"fixture_id": 123, "score": 78.5})
"""

from loguru import logger
import sys
from pathlib import Path
from datetime import datetime

LOG_DIR = Path("/Users/chenguoqing/.openclaw/workspace/v2_football_quant/logs")
LOG_DIR.mkdir(exist_ok=True)

# 移除默认 handler
logger.remove()

# 控制台：INFO 级别
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO",
    colorize=True,
)

# 文件：DEBUG 级别，每日轮转
logger.add(
    LOG_DIR / "v2_quant_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
    rotation="00:00",
    retention="30 days",
    level="DEBUG",
    encoding="utf-8",
)

# 关键事件日志（结构化）
EVENT_LOG = LOG_DIR / "events.jsonl"


def log_event(event_type: str, data: dict, level: str = "INFO"):
    """结构化事件日志"""
    import json
    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": event_type,
        "level": level,
        "data": data,
    }
    with open(EVENT_LOG, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    log_func = getattr(logger, level.lower(), logger.info)
    log_func(f"[{event_type}] {data}")


# 关键节点的日志宏
def log_recommend(fixture_id: int, score: float, odds: float, league: str):
    log_event("RECOMMEND", {
        "fixture_id": fixture_id, "score": score,
        "odds": odds, "league": league,
    })
    logger.success(f"✅ 推荐: #{fixture_id} {league} 评分{score} 赔率{odds}")


def log_skip(fixture_id: int, reason: str):
    log_event("SKIP", {"fixture_id": fixture_id, "reason": reason}, "WARNING")
    logger.warning(f"⚠️ 跳过: #{fixture_id} {reason}")


def log_bankroll(stake: float, remaining: float, action: str):
    log_event("BANKROLL", {"stake": stake, "remaining": remaining, "action": action})


def log_clv(placed: float, closing: float, clv: float):
    emoji = "✅" if clv > 0 else "❌"
    log_event("CLV", {"placed": placed, "closing": closing, "clv": round(clv, 4)})
    logger.info(f"{emoji} CLV: {placed:.2f}→{closing:.2f} = {clv:+.4f}")


# 预留 Telegram 告警接口
def send_telegram_alert(message: str):
    """预留：接入 Telegram Bot API"""
    # TODO: 配置 TELEGRAM_BOT_TOKEN + CHAT_ID
    # requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={
    #     "chat_id": CHAT_ID, "text": f"🚨 V2量化预警\n{message}"
    # })
    logger.info(f"[ALERT_PENDING] {message}")


if __name__ == "__main__":
    logger.info("日志系统初始化完成")
    log_event("SYSTEM_START", {"version": "1.0"})
    log_recommend(12345, 78.5, 1.85, "英超")
    log_skip(67890, "low_liquidity")
    log_bankroll(150, 1850, "bet_placed")
    log_clv(1.85, 1.82, -0.0162)
    print(f"\n日志文件: {LOG_DIR}")
