import re

with open("data/runtime/dashboard/intel_ops_console.html") as f:
    html = f.read()

audit_split = html.split('data-audit-hidden="true"')
main_view = audit_split[0] if audit_split else html
audit_sections = audit_split[1:] if len(audit_split) > 1 else []

forbidden_main = ["V4_QQ_ENABLED", "actual_send", "qq_sent",
                  "需BOSS批准", "等待BOSS批准", "是否可推送"]

print("=== MAIN VIEW AUDIT ===")
all_clean = True
for term in forbidden_main:
    count = main_view.count(term)
    tag = "CLEAN" if count == 0 else "FOUND " + str(count) + "x"
    if count > 0:
        all_clean = False
    print("  [%-12s] %s" % (tag, term))

main_v4qq_count = main_view.count("V4 QQ")
print("  [%-12s] V4 QQ" % ("CLEAN" if main_v4qq_count == 0 else "FOUND " + str(main_v4qq_count) + "x"))
main_qq_count = main_view.count("QQ")
print("  [%-12s] QQ (total in main)" % ("CLEAN" if main_qq_count == 0 else "FOUND " + str(main_qq_count) + "x"))

print("\n  Main view clean: %s" % str(all_clean and main_v4qq_count == 0))

print("\n=== AUDIT SECTIONS ===")
for term in ["V4_QQ_ENABLED", "actual_send", "qq_sent", "V4 QQ"]:
    count = html.count(term)
    in_audit = sum(s.count(term) for s in audit_sections)
    print("  %s: total=%d, in_audit=%d" % (term, count, in_audit))

print("\n=== TOP STATUS CARDS ===")
print("  status-card count: %d" % main_view.count("status-card"))

print("\n=== KEY ELEMENTS ===")
print("  Title has 情报决策总台: %s" % ("YES" if "情报决策总台" in html else "NO"))
print("  数据已更新 · 系统正常: %s" % ("YES" if "数据已更新" in html else "NO"))

audit_attr = 'data-audit-hidden="true"'
print("  data-audit-hidden=true: %s" % ("YES" if audit_attr in html else "NO"))

a_start = html.find('grade-A')
if a_start > 0:
    next_grade_b_tag = html.find('grade-B', a_start)
    a_section = html[a_start:next_grade_b_tag] if next_grade_b_tag > 0 else html[a_start:a_start+1000]
    print("  A card has card-status: %s" % ("YES" if "card-status" in a_section else "NO"))

print("  A card time_bins visible: %s" % ("YES" if "0-15m" in html and "grade-A" in html else "NO"))
print("  B card 0-15m occurrences: %d" % main_view.count("0-15m"))
c_collapsed = "c-section-body" in html and "c-section-body open" not in html
print("  C default-collapsed: %s" % ("YES" if c_collapsed else "NO"))
print("  Validation collapsed: %s" % ("YES" if "展开：完整验证数据" in html else "NO"))
print("  Candidate numbers A/B/C: %s" % ("YES" if "1 / 4 / 6" in html or "1/4/6" in html else "NO"))
print("  Validation 130: %s" % ("YES" if "130" in html else "NO"))
print("  Validation 57.7%: %s" % ("YES" if "57.7%" in html else "NO"))
neg_margin = "margin:-" in html or "margin : -" in html
print("  No negative margin: %s" % ("YES" if not neg_margin else "NO"))
print("  Body padding 18px: %s" % ("YES" if "padding:18px" in html else "CHECK"))
