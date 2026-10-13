"""Adaptive quiz agent with deterministic manual/Normal Quiz tools and Groq AI Quiz."""

import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from memory import memory_summary
from tools import add_card, evaluate_answer, quiz_me, record_ai_evaluation, store_generated_question


load_dotenv()
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
VALID_ACTIONS = {"add_cards", "start_quiz", "start_normal_quiz", "submit_answer", "clarify"}


def _trace(step, title, content):
    return {"step": step, "title": title, "content": content}


def _cards_from_text(text):
    pairs = []
    for line in text.splitlines():
        match = re.match(r"\s*(?:[-•]|\d+\.)?\s*(.+?)\s*(?:->|→|\|)\s*(.+)", line)
        if match:
            pairs.append((match.group(1).strip(), match.group(2).strip()))
    return pairs


def _memory_context(memory):
    summary = memory_summary(memory)
    return {
        "manual_flashcards": [{"id": card["id"], "question": card["question"], "answer": card["answer"]} for card in memory["flashcards"][-10:]],
        "total_questions_answered": summary["total_questions_answered"],
        "accuracy_percentage": summary["accuracy_percentage"],
        "weak_topics": [{"topic": item["topic"], "weakness_score": item["weakness_score"]} for item in summary["weak_topics"]],
        "recent_questions": memory["recent_questions"],
        "active_question": memory["active_question"],
    }


def _groq_json(system_prompt, payload):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to .env before using the agent.")
    completion = Groq(api_key=key).chat.completions.create(
        model=MODEL, temperature=0,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": json.dumps(payload)}],
    )
    content = (completion.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("Groq returned an empty response.")
    # Recover from the common case where a model wraps valid JSON in a Markdown fence
    # or adds one short sentence around it. A balanced scan avoids being confused by
    # braces inside a JSON string such as a code sample.
    content = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", content, flags=re.IGNORECASE)
    start = content.find("{")
    if start < 0:
        raise RuntimeError("Groq returned a response that could not be parsed as JSON.")
    depth, quoted, escaped = 0, False, False
    for index, character in enumerate(content[start:], start):
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(content[start:index + 1])
                except json.JSONDecodeError as error:
                    raise RuntimeError(f"Groq returned JSON that could not be parsed: {error.msg}") from error
    raise RuntimeError("Groq returned an incomplete JSON object.")


def _plan_with_groq(user_input, context, has_answer):
    result = _groq_json(
        """You route requests for an adaptive flashcard app. Return JSON only with
action, plan, reason. action is add_cards, start_quiz, start_normal_quiz, submit_answer, or clarify.
Use start_normal_quiz only for an explicit Normal Quiz request. Use start_quiz for AI quiz
or next-AI-question requests; it works even with no flashcards.
Use submit_answer only when has_answer is true and an active_question exists.""",
        {"user_request": user_input, "memory": context, "has_answer": has_answer},
    )
    if result.get("action") not in VALID_ACTIONS:
        raise RuntimeError("Groq returned an unsupported tool decision.")
    return result


def _clean_question_text(value):
    """Keep model output display-safe; Streamlit receives plain text/Markdown only."""
    return re.sub(r"<[^>]+>", "", value).strip()


def _validate_question(data):
    required = ("topic", "difficulty", "question", "correct_answer", "explanation")
    if not isinstance(data, dict) or any(not isinstance(data.get(key), str) or not data[key].strip() for key in required):
        raise RuntimeError("Groq returned an incomplete quiz question.")
    clean = {key: _clean_question_text(data[key]) for key in required}
    if not all(clean.values()):
        raise RuntimeError("Groq returned unusable quiz text.")
    code = data.get("code", "")
    if code is not None and not isinstance(code, str):
        raise RuntimeError("Groq returned an invalid code field.")
    question_type = data.get("question_type", "technical")
    if not isinstance(question_type, str) or not question_type.strip():
        question_type = "technical"
    return {"topic": clean["topic"], "difficulty": clean["difficultx`y"], "question": clean["question"], "expected_answer": clean["correct_answer"], "explanation": clean["explanation"], "reason": clean["explanation"], "code": _clean_question_text(code) if code else "", "question_type": _clean_question_text(question_type)}


def _generate_question_with_groq(context, requested_topic):
    data = _groq_json(
        """You are an AI quiz generator for any coding or technical subject supplied as
requested_topic. Generate exactly ONE educational question specifically about that topic.
Return ONLY valid JSON. Keep the question reasonably concise but do not truncate important
information. Do not return HTML or Markdown outside JSON. Return topic, difficulty,
question, correct_answer, explanation, question_type, and optional code. Choose an
appropriate question_type such as conceptual, theory, coding, code output, debugging, or
technical interview; vary it from recent questions when useful. Support subjects including
programming languages, databases, operating systems, networks, web development, machine
learning, APIs, and debugging. Use weak_topics and performance to adjust difficulty and
avoid recent_questions. Difficulty must be easy, medium, or hard. Put source code only in
the optional code field, not in HTML or a Markdown fence.""",
        {**context, "requested_topic": requested_topic},
    )
    question = _validate_question(data)
    if question["difficulty"].lower() not in {"easy", "medium", "hard"}:
        question["difficulty"] = "medium"
    return question


def _validate_evaluation(data):
    if not isinstance(data, dict) or type(data.get("correct")) is not bool:
        raise RuntimeError("Groq returned an invalid answer evaluation.")
    feedback, explanation = data.get("feedback"), data.get("explanation")
    correct_answer = data.get("correct_answer")
    if not all(isinstance(value, str) and value.strip() for value in (feedback, explanation, correct_answer)):
        raise RuntimeError("Groq returned incomplete answer feedback.")
    return {"correct": data["correct"], "feedback": _clean_question_text(feedback)[:500], "correct_answer": _clean_question_text(correct_answer)[:300], "explanation": _clean_question_text(explanation)[:500], "next_focus": _clean_question_text(data.get("next_focus", "Continue with the same topic."))[:300]}


def _evaluate_with_groq(active_question, user_answer, context):
    data = _groq_json(
        """Evaluate the learner answer semantically for the supplied question. Return JSON only:
correct (boolean), feedback, correct_answer, explanation, weakness_change (-1, 0, or 1),
and next_focus. Judge meaning fairly, not only exact text. Do not modify memory.""",
        {"question": active_question["question"], "expected_answer": active_question["answer"], "user_answer": user_answer, "learning_context": context},
    )
    result = _validate_evaluation(data)
    result["weakness_change"] = data.get("weakness_change", -1 if result["correct"] else 1)
    return result


def _failure(trace, context, error):
    message = f"Groq reasoning is unavailable: {error}"
    trace.extend([_trace(len(trace) + 1, "OBSERVATION", message), _trace(len(trace) + 2, "NEXT ACTION DECISION", "Check the Groq configuration and retry."), _trace(len(trace) + 3, "FINAL RESPONSE", message)])
    return {"result": {"status": "error", "message": message}, "trace": trace, "summary": memory_summary_from_context(context), "final_response": message}


def _response_error(trace, memory, error):
    """Report malformed model output honestly without misreporting an API outage."""
    message = f"The AI quiz response could not be used: {error}. Please try again."
    trace.extend([_trace(len(trace) + 1, "OBSERVATION", message), _trace(len(trace) + 2, "FINAL RESPONSE", message)])
    return {"result": {"status": "error", "message": message}, "trace": trace, "summary": memory_summary(memory), "final_response": message}


def memory_summary_from_context(context):
    return {"total_cards": len(context["manual_flashcards"]), "weak_areas": len(context["weak_topics"])}


def run_agent(user_input, memory, answer=None, topic=None):
    """Single entry point for local flashcard tools and Groq-powered AI Quiz actions."""
    text = user_input.strip()
    context = _memory_context(memory)
    trace = [_trace(1, "MEMORY READ", f"Answered: {context['total_questions_answered']} | Accuracy: {context['accuracy_percentage']}% | Weak topics: {', '.join(item['topic'] for item in context['weak_topics']) or 'None'}")]
    lower_text = text.lower()
    manual_pairs = _cards_from_text(text)
    if manual_pairs or lower_text.startswith("add flashcard"):
        # Manual flashcards are a deterministic local workflow.  The UI submits
        # this format, so it must not depend on a network call or an API key.
        trace.append(_trace(len(trace) + 1, "USER ACTION", "User submitted manual flashcard question(s) and answer(s)."))
        decision = {"action": "add_cards", "plan": "Store the supplied flashcards with the local Python tool.", "reason": "Manual flashcards use deterministic Python tools and memory."}
    elif "normal quiz" in lower_text:
        trace.append(_trace(len(trace) + 1, "USER ACTION", "User started a Normal Quiz."))
        decision = {"action": "start_normal_quiz", "plan": "Use Python to select an adaptive custom flashcard.", "reason": "Normal Quiz was explicitly selected."}
    elif answer is not None and memory.get("current_quiz_mode") == "normal":
        trace.append(_trace(len(trace) + 1, "USER ACTION", "User submitted a Normal Quiz answer."))
        decision = {"action": "submit_answer", "plan": "Evaluate the custom flashcard with Python.", "reason": "A Normal Quiz answer is active."}
    elif "ai quiz" in lower_text and not (topic or "").strip():
        result = {"status": "error", "message": "Enter a topic to study before starting an AI Quiz."}
        trace.extend([_trace(2, "TOPIC RECEIVED", "No topic was provided."), _trace(3, "OBSERVATION", result["message"]), _trace(4, "FINAL RESPONSE", result["message"])])
        return {"result": result, "trace": trace, "summary": memory_summary(memory), "final_response": result["message"]}
    else:
        try:
            decision = _plan_with_groq(text, context, answer is not None)
        except Exception as error:
            return _failure(trace, context, str(error))
    action = decision["action"]
    decision_source = "Python selected" if action in {"add_cards", "start_normal_quiz"} or (action == "submit_answer" and memory.get("current_quiz_mode") == "normal") else "Groq selected"
    trace.extend([
        _trace(len(trace) + 1, "PLAN", decision.get("plan", "Groq selected the next learning action.")),
        _trace(len(trace) + 2, "TOOL DECISION", f"{decision_source} {action}: {decision.get('reason', '')}"),
    ])

    if action == "add_cards":
        pairs = _cards_from_text(text)
        if not pairs:
            result = {"status": "error", "message": "Use one custom flashcard per line: Question -> Answer."}
            trace.append(_trace(len(trace) + 1, "OBSERVATION", result["message"]))
        else:
            added = [add_card(memory, question, card_answer) for question, card_answer in pairs]
            result = {"status": "success", "message": f"Added {len(added)} flashcard(s).", "added": added}
            trace.extend([
                _trace(len(trace) + 1, "TOOL CALL", f"Python add_card(...) executed {len(added)} time(s)."),
                _trace(len(trace) + 2, "OBSERVATION", result["message"]),
                _trace(len(trace) + 3, "MEMORY UPDATE", f"Stored card IDs: {', '.join(str(card['card_id']) for card in added)}."),
            ])
    elif action == "start_normal_quiz":
        trace.append(_trace(len(trace) + 1, "TOOL CALL", "Python quiz_me() is selecting a custom flashcard."))
        result = quiz_me(memory)
        if result["status"] == "success":
            memory["current_quiz_mode"] = "normal"
            step = len(trace)
            trace.extend([_trace(step + 1, "QUESTION DISPLAYED", result["question"]), _trace(step + 2, "MEMORY UPDATE", f"Active custom card: {result['card_id']}")])
        else:
            result = {"status": "empty", "message": "No flashcards available. Add flashcards first or use AI Quiz."}
            trace.append(_trace(len(trace) + 1, "OBSERVATION", result["message"]))
    elif action == "start_quiz":
        requested_topic = (topic or "").strip()
        if not requested_topic:
            result = {"status": "error", "message": "Enter a topic to study before starting an AI Quiz."}
            trace.append(_trace(4, "OBSERVATION", result["message"]))
            final_text = result["message"]
            trace.append(_trace(5, "FINAL RESPONSE", final_text))
            return {"result": result, "trace": trace, "summary": memory_summary(memory), "final_response": final_text}
        memory["current_ai_topic"] = requested_topic
        trace.extend([_trace(4, "TOPIC RECEIVED", f"Requested topic: {requested_topic}"), _trace(5, "GROQ QUESTION GENERATION", "Groq is generating a topic-specific question from performance and recent history.")])
        try:
            generated = _generate_question_with_groq(context, requested_topic)
        except Exception as error:
            return _response_error(trace, memory, str(error))
        result = store_generated_question(memory, generated)
        question = result["question"]
        trace.extend([_trace(6, "QUESTION DISPLAYED", f"Generated {question['difficulty']} {question['topic']} question."), _trace(7, "QUESTION STORED", f"Python stored active question {question['id']}; Groq did not write memory."), _trace(8, "NEXT ACTION DECISION", question["reason"])])
    elif action == "submit_answer":
        if memory.get("current_quiz_mode") == "normal" and memory.get("active_card_id"):
            card_id = memory["active_card_id"]
            trace.append(_trace(len(trace) + 1, "USER ANSWER RECEIVED", "Python received the normal-quiz answer."))
            result = evaluate_answer(memory, card_id, answer)
            if result["status"] == "success":
                result["quiz_mode"] = "normal"
                topic_stats = memory["topic_performance"].setdefault("Custom flashcards", {"correct": 0, "wrong": 0, "weakness_score": 0})
                topic_stats["correct" if result["correct"] else "wrong"] += 1
                topic_stats["weakness_score"] = max(0, topic_stats["weakness_score"] + (-1 if result["correct"] else 1))
                result["topic_performance"] = topic_stats.copy()
                result["feedback"] = "Answer checked against your custom flashcard."
                result["explanation"] = "The stored flashcard answer is shown below."
                result["next_focus"] = "Continue with another custom flashcard."
                step = len(trace)
                trace.extend([_trace(step + 1, "PYTHON ANSWER EVALUATION", f"{'Correct' if result['correct'] else 'Incorrect'} by exact flashcard comparison."), _trace(step + 2, "MEMORY UPDATE", f"Correct: {result['performance']['correct']} | Wrong: {result['performance']['wrong']}"), _trace(step + 3, "NEXT ACTION DECISION", result["next_focus"])])
        else:
            active = memory.get("active_question")
            if not active:
                result = {"status": "error", "message": "There is no active quiz question to answer."}
                trace.append(_trace(4, "OBSERVATION", result["message"]))
            else:
                trace.append(_trace(4, "USER ANSWER RECEIVED", "Python received the learner answer."))
                memory["last_ai_user_answer"] = answer
                try:
                    evaluation = _evaluate_with_groq(active, answer, context)
                except Exception as error:
                    return _failure(trace, context, str(error))
                trace.append(_trace(5, "GROQ ANSWER EVALUATION", "Groq evaluated the submitted answer against the expected answer."))
                result = record_ai_evaluation(memory, evaluation)
                result["quiz_mode"] = "ai"
                result["explanation"] = evaluation["explanation"]
                memory["last_ai_result"] = result.copy()
                trace.extend([_trace(6, "OBSERVATION", f"{'Correct' if result['correct'] else 'Incorrect'}: {result['feedback']}"), _trace(7, "MEMORY UPDATE", f"Correct: {result['performance']['correct']} | Wrong: {result['performance']['wrong']} | Topic weakness: {result['topic_performance']['weakness_score']}"), _trace(8, "NEXT ACTION DECISION", result["next_focus"])])
    else:
        result = {"status": "error", "message": "Add custom flashcards, start an AI quiz, or submit an active answer."}
        trace.append(_trace(4, "OBSERVATION", result["message"]))

    final_text = result.get("feedback", result.get("message", "Action completed."))
    trace.append(_trace(len(trace) + 1, "FINAL RESPONSE", final_text))
    memory["conversation_history"].append({"user": text, "result": final_text})
    return {"result": result, "trace": trace, "summary": memory_summary(memory), "final_response": final_text}
