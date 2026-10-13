"""Real Python tools called by the quiz agent."""

import re


def add_card(memory, question, answer):
    """Add a flashcard and initialise its learning performance."""
    question, answer = question.strip(), answer.strip()
    if not question or not answer:
        return {"status": "error", "message": "Question and answer are both required."}

    card_id = memory["next_card_id"]
    memory["next_card_id"] += 1
    memory["flashcards"].append({"id": card_id, "question": question, "answer": answer, "source": "custom", "topic": "Custom flashcards", "difficulty": "custom"})
    memory["performance"][str(card_id)] = {"correct": 0, "wrong": 0, "weakness_score": 0}
    return {"status": "success", "card_id": card_id, "message": "Flashcard added successfully."}


def store_generated_question(memory, question_data):
    """Store validated Groq output; Groq never writes Python memory itself."""
    question_id = f"ai-{memory['next_generated_id']}"
    memory["next_generated_id"] += 1
    record = {
        "id": question_id, "source": "ai", "topic": question_data["topic"],
        "difficulty": question_data["difficulty"], "question": question_data["question"],
        "answer": question_data["expected_answer"], "reason": question_data["reason"],
        "explanation": question_data.get("explanation", ""),
        "code": question_data.get("code", ""),
        "question_type": question_data.get("question_type", "technical"),
    }
    memory["generated_questions"].append(record)
    memory["performance"][question_id] = {"correct": 0, "wrong": 0, "weakness_score": 0}
    memory["active_question"] = record.copy()
    memory["last_ai_question"] = None
    memory["last_ai_result"] = None
    memory["last_ai_user_answer"] = ""
    memory["active_card_id"] = None
    memory["current_quiz_mode"] = "ai"
    return {"status": "success", "question": record}


def record_ai_evaluation(memory, evaluation):
    """Apply a validated Groq judgement to Python-owned memory and performance."""
    active = memory.get("active_question")
    if not active:
        return {"status": "error", "message": "There is no active quiz question to answer."}
    stats = memory["performance"][str(active["id"])]
    correct = evaluation["correct"]
    stats["correct" if correct else "wrong"] += 1
    change = -1 if correct else 1
    stats["weakness_score"] = max(0, stats["weakness_score"] + change)
    topic = active.get("topic", "General knowledge")
    topic_stats = memory["topic_performance"].setdefault(topic, {"correct": 0, "wrong": 0, "weakness_score": 0})
    topic_stats["correct" if correct else "wrong"] += 1
    topic_stats["weakness_score"] = max(0, topic_stats["weakness_score"] + change)
    memory["recent_questions"] = (memory["recent_questions"] + [{"id": active["id"], "question": active["question"], "topic": topic, "difficulty": active.get("difficulty", "")}])[-5:]
    memory["recent_cards"] = (memory["recent_cards"] + [active["id"]])[-5:]
    memory["last_ai_question"] = active.copy()
    memory["active_question"] = None
    memory["active_card_id"] = None
    return {"status": "success", "correct": correct, "correct_answer": active["answer"], "feedback": evaluation["feedback"], "next_focus": evaluation["next_focus"], "performance": stats.copy(), "topic_performance": topic_stats.copy()}


def quiz_me(memory):
    """Select the next card using weakness, mistakes, and recent-card variety."""
    cards = memory["flashcards"]
    if not cards:
        return {"status": "empty", "message": "Add at least one flashcard before starting a quiz."}

    # Do not repeat the card that was just completed when another card exists.
    # The adaptive scoring below is otherwise unchanged, so weak cards remain
    # prioritised on subsequent questions.
    last_card_id = memory["recent_cards"][-1] if memory["recent_cards"] else None
    eligible_cards = [card for card in cards if card["id"] != last_card_id] or cards
    recent = set(memory["recent_cards"][-2:])
    # Use the full recent-card history to break equal-priority ties fairly.
    # Cards never asked before are treated as oldest, so newly added cards
    # remain eligible instead of being starved by lower-ID cards.
    last_seen = {}
    for position, card_id in enumerate(memory["recent_cards"]):
        last_seen[card_id] = position
    scored = []
    for card in eligible_cards:
        stats = memory["performance"][str(card["id"])]
        # A recently asked card is penalised, but a genuinely weak card can still win.
        # This substantial penalty gives a new card a chance once a weak card has
        # been answered correctly, while still allowing high weakness to dominate.
        recent_penalty = 4 if card["id"] in recent else 0
        priority = (stats["weakness_score"] * 10) + (stats["wrong"] * 3) - recent_penalty
        scored.append((priority, stats["weakness_score"], stats["wrong"], -last_seen.get(card["id"], -1), -card["id"], card))

    # Stable recency/ID tie-breakers keep selection deterministic without
    # starving cards that were added later.
    priority, weakness, wrong, _, _, card = max(scored, key=lambda item: item[:-1])
    if weakness:
        reason = f"Highest weakness score: {weakness} (with {wrong} incorrect attempt(s))."
    elif card["id"] not in recent:
        reason = "No weak cards yet; selected a card not asked recently."
    else:
        reason = "All available cards were recently considered; selected the best available card."
    memory["active_card_id"] = card["id"]
    return {
        "status": "success", "card_id": card["id"], "question": card["question"],
        "selection_reason": reason, "priority": priority,
    }


def _normalise(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def evaluate_answer(memory, card_id, user_answer):
    """Evaluate an answer and update performance and recent-card memory."""
    card = next((item for item in memory["flashcards"] if item["id"] == card_id), None)
    if card is None:
        return {"status": "error", "message": "The selected flashcard no longer exists."}
    correct = _normalise(user_answer) == _normalise(card["answer"])
    stats = memory["performance"][str(card_id)]
    if correct:
        stats["correct"] += 1
        stats["weakness_score"] = max(0, stats["weakness_score"] - 1)
    else:
        stats["wrong"] += 1
        stats["weakness_score"] += 1
    memory["recent_cards"] = (memory["recent_cards"] + [card_id])[-5:]
    memory["active_card_id"] = None
    memory["current_quiz_mode"] = None
    return {
        "status": "success", "correct": correct, "card_id": card_id,
        "correct_answer": card["answer"], "performance": stats.copy(),
    }
