"""Session and local-disk state for the Adaptive Flashcard Quiz Agent."""

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


MEMORY_FILE = Path(__file__).with_name("study_memory.json")


def create_memory():
    return {
        "flashcards": [],
        "generated_questions": [],
        "performance": {},
        "topic_performance": {},
        "recent_cards": [],
        "recent_questions": [],
        "conversation_history": [],
        "activity_log": [],
        "next_card_id": 1,
        "next_generated_id": 1,
        "active_card_id": None,
        "active_question": None,
        "last_ai_question": None,
        "last_ai_result": None,
        "last_ai_user_answer": "",
        "current_quiz_mode": None,
        "current_ai_topic": "",
        "last_trace": [],
        "last_result": None,
    }


def load_memory():
    """Load the last local study session, falling back safely to fresh memory."""
    memory = create_memory()
    if not MEMORY_FILE.exists():
        return memory
    try:
        saved = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(saved, dict):
            return memory
        # Only known top-level state is restored, so a damaged file cannot alter shape.
        for key in memory:
            if key in saved:
                memory[key] = saved[key]
        return memory
    except (OSError, json.JSONDecodeError):
        return memory


def save_memory(memory):
    """Atomically save the serialisable study state so a reload retains progress."""
    temporary_file = MEMORY_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_file.replace(MEMORY_FILE)


def migrate_activity_timestamps(memory):
    """Convert activity records written by earlier UTC versions to IST."""
    changed = False
    for item in memory.get("activity_log", []):
        timestamp = item.get("timestamp", "")
        if not timestamp.endswith(" UTC"):
            continue
        try:
            utc_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        item["timestamp"] = utc_time.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M IST")
        changed = True
    return changed


def record_activity(memory, activity, detail):
    """Keep a short, durable record of real user learning activity."""
    memory["activity_log"] = (
        memory.get("activity_log", [])
        + [{
            "activity": activity,
            "detail": detail,
            "timestamp": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M IST"),
        }]
    )[-10:]


def memory_summary(memory):
    """Calculate display-ready learning statistics from actual memory."""
    performance = memory["performance"]
    correct = sum(item["correct"] for item in performance.values())
    wrong = sum(item["wrong"] for item in performance.values())
    questions = memory["flashcards"] + memory["generated_questions"]
    weak_cards = [
        card for card in questions
        if performance.get(str(card["id"]), {}).get("weakness_score", 0) > 0
    ]
    topic_totals = {}
    for question in questions:
        topic = question.get("topic", "General knowledge")
        stats = performance.get(str(question["id"]), {"correct": 0, "wrong": 0, "weakness_score": 0})
        totals = topic_totals.setdefault(topic, {"correct": 0, "wrong": 0, "weakness_score": 0})
        for key in totals:
            totals[key] += stats[key]
    weak_topics = [
        {"topic": topic, **stats}
        for topic, stats in topic_totals.items()
        if stats["weakness_score"] > 0
    ]
    weak_topics.sort(key=lambda item: (-item["weakness_score"], item["topic"]))
    strong_topics = [
        {"topic": topic, **stats}
        for topic, stats in topic_totals.items()
        if stats["correct"] > stats["wrong"] and stats["weakness_score"] == 0
    ]
    strong_topics.sort(key=lambda item: (-(item["correct"] - item["wrong"]), item["topic"]))
    answered = correct + wrong
    return {
        "total_cards": len(memory["flashcards"]),
        "generated_questions": len(memory["generated_questions"]),
        "total_questions_answered": answered,
        "correct_answers": correct,
        "incorrect_answers": wrong,
        "accuracy_percentage": round((correct / answered) * 100, 1) if answered else 0.0,
        "weak_areas": len(weak_topics),
        "weak_cards": weak_cards,
        "weak_topics": weak_topics,
        "strong_topics": strong_topics,
        "question_records": questions,
    }
