"""
Chạy: python main.py
"""

from crew_interview import run_interview_crew
from crew_evaluate  import run_evaluate_crew
from crew_summary   import run_summary_crew, AnsweredQuestion


# ─────────────────────────────────────────────
# Helper nhập nhiều dòng (giống crew_cv)
# ─────────────────────────────────────────────

def multi_input(prompt: str) -> str:
    print(prompt)
    print("(Nhập nhiều dòng. Gõ 'END' để kết thúc)\n")
    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


# ─────────────────────────────────────────────
# BƯỚC 1 — Nhập CV / JD / số câu hỏi
# ─────────────────────────────────────────────

print("=" * 60)
print("  INTERVIEW SIMULATOR — Full Flow")
print("=" * 60)

cv_text = multi_input("\n=== NHẬP CV ===")
jd_text = multi_input("\n=== NHẬP JD ===")

num_q = 5

cv_summary = cv_text[:800]   # dùng lại cho evaluate


# ─────────────────────────────────────────────
# BƯỚC 1 — Sinh bộ câu hỏi
# ─────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  BƯỚC 1: Đang sinh {num_q} câu hỏi...")
print(f"{'='*60}\n")

plan = run_interview_crew(cv_text=cv_text, jd_text=jd_text, num_questions=num_q)

print(f"\n✅ Sinh xong {plan.total_questions} câu hỏi "
      f"(ước tính {plan.estimated_duration_minutes} phút)\n")


# ─────────────────────────────────────────────
# BƯỚC 2 — Hỏi & chấm từng câu
# ─────────────────────────────────────────────

print(f"{'='*60}")
print(f"  BƯỚC 2: Bắt đầu phỏng vấn")
print(f"{'='*60}\n")

answered_questions: list[AnsweredQuestion] = []

for q in plan.questions:
    print(f"── Câu {q.order_index}/{plan.total_questions} "
          f"[{q.category.upper()} | {q.difficulty}] ──")
    print(f"❓ {q.question_text}\n")

    user_ans = multi_input("💬 Trả lời của bạn").strip()

    print("\n⏳ Đang chấm điểm...\n")
    ev = run_evaluate_crew(
        question_text=q.question_text,
        user_answer=user_ans,
        hint_text=q.hint_text,
        category=q.category,
        difficulty=q.difficulty,
        cv_summary=cv_summary,
    )

    print(f"  📊 Điểm     : {ev.score}/10")
    print(f"  💬 Nhận xét : {ev.comment}")
    print(f"  ✅ Điểm mạnh: {ev.strengths}")
    print(f"  ⚠️  Điểm yếu : {ev.weaknesses}")
    print(f"  💡 Gợi ý    : {ev.improvement_tips}\n")

    answered_questions.append(AnsweredQuestion(
        order_index=q.order_index,
        question_text=q.question_text,
        category=q.category,
        difficulty=q.difficulty,
        user_answer=user_ans,
        score=ev.score,
        comment=ev.comment,
        better_answer=ev.better_answer,
    ))

    input("[ Nhấn Enter để tiếp tục câu tiếp theo... ]\n")


# ─────────────────────────────────────────────
# BƯỚC 3 — Tổng kết
# ─────────────────────────────────────────────

print(f"{'='*60}")
print(f"  BƯỚC 3: Đang tổng kết buổi phỏng vấn...")
print(f"{'='*60}\n")

summary = run_summary_crew(
    questions=answered_questions,
    cv_text=cv_text,
    jd_text=jd_text,
)

print("\n" + "=" * 60)
print("  KẾT QUẢ PHỎNG VẤN")
print("=" * 60)
print(f"  Tổng điểm   : {summary.total_score}/10")
print(f"  Xếp loại    : {summary.grade}")
print(f"  Đề xuất     : {summary.hiring_recommendation}")
print(f"  Lý do       : {summary.hiring_reason}")
print(f"\n  Nhận xét tổng thể:\n  {summary.overall_feedback}")
print(f"\n  Điểm mạnh   : {summary.strengths}")
print(f"  Điểm yếu    : {summary.weaknesses}")

print(f"\n  Điểm theo loại:")
for cs in summary.category_scores:
    print(f"    - {cs.category:12s}: {cs.avg_score}/10 ({cs.question_count} câu) — {cs.assessment}")

print(f"\n  Lời khuyên:")
for i, tip in enumerate(summary.top_recommendations, 1):
    print(f"    {i}. {tip}")

print("\n" + "=" * 60)