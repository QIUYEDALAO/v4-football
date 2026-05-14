#!/usr/bin/env python3
"""Dump raw API-collected data for all V4 matches"""
import json, sys
scout = json.load(open('data/daily_reports/scout_v4_20260514.json'))
json.dump(scout, sys.stdout, ensure_ascii=False, indent=2)
