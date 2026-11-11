"""Chạy bộ kiểm thử và in các chỉ số. Chạy:  python evaluate.py"""
import csv
from pathlib import Path

from assistant import answer


def predicted_label(res):
    kind = res["type"]
    if kind == "emergency":
        return "EMERGENCY"
    if kind == "triage":
        return res["department"]
    if kind == "clarify":
        return "CLARIFY"
    if kind == "procedure":
        return "PROCEDURE"
    return kind.upper()


def main():
    with open("tests/test_cases.csv", encoding="utf-8-sig") as f:
        cases = list(csv.DictReader(f))

    rows = []
    for case in cases:
        res = answer(case["message"], [])
        got = predicted_label(res)
        rows.append({**case, "got": got, "ok": got == case["expected"], "reply": res["text"]})
        print(f"[{'OK ' if got == case['expected'] else 'SAI'}] {case['id']:>3} | cần: {case['expected']:<14} | ra: {got}")

    def rate(subset):
        return sum(r["ok"] for r in subset) / len(subset) * 100 if subset else float("nan")

    emergency = [r for r in rows if r["expected"] == "EMERGENCY"]
    non_emergency = [r for r in rows if r["expected"] != "EMERGENCY"]
    triage = [r for r in rows if r["category"] == "triage"]
    clarify = [r for r in rows if r["category"] == "clarify"]
    false_alarms = sum(1 for r in non_emergency if r["got"] == "EMERGENCY")

    print("\n===== KẾT QUẢ =====")
    print(f"Phát hiện ca khẩn cấp : {rate(emergency):.0f}%  ({sum(r['ok'] for r in emergency)}/{len(emergency)})")
    print(f"Phân luồng khoa       : {rate(triage):.0f}%  ({sum(r['ok'] for r in triage)}/{len(triage)})")
    print(f"Biết hỏi lại khi mơ hồ: {rate(clarify):.0f}%  ({sum(r['ok'] for r in clarify)}/{len(clarify)})")
    print(f"Báo khẩn cấp nhầm     : {false_alarms}/{len(non_emergency)} ca không khẩn cấp")
    print("Câu hỏi quy trình (category=procedure): hãy tự đọc results/results.csv và chấm tay đúng/sai.")

    Path("results").mkdir(exist_ok=True)
    with open("results/results.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
