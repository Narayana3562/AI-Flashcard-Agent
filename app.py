"""Streamlit dashboard UI; all study decisions remain in agent.py."""

import streamlit as st

from agent import run_agent
from memory import load_memory, memory_summary, migrate_activity_timestamps, record_activity, save_memory


st.set_page_config(page_title="Adaptive Flashcard Agent", page_icon="", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
    :root { color-scheme: light; }
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stHeader"] {
        background: #FFFFFF !important; color: #000000 !important;
    }
    [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {
        background: #FFFFFF !important; border-right: 1px solid #E5E5E5 !important;
    }
    [data-testid="stSidebar"] *, h1, h2, h3, p, label, span, div, a, small { color: #000000 !important; }
    [data-testid="stSidebar"] .stRadio label {
        background: #FFFFFF !important; border-radius: 8px; padding: .6rem .65rem; margin: .12rem 0;
    }
    [data-testid="stSidebar"] .stRadio label:has(input:checked) { background: #000000 !important; }
    [data-testid="stSidebar"] .stRadio label:has(input:checked) *,
    [data-testid="stSidebar"] .stRadio label:has(input:checked) svg { color: #FFFFFF !important; fill: #FFFFFF !important; }
    [data-testid="stSidebar"] input { accent-color: #000000 !important; }
    .block-container { max-width: 1180px; padding: 3rem 3.25rem 4rem; }
    .eyebrow, .page-description, .metric-label, .question-label, .reason, .sidebar-subtitle { color: #000000 !important; }
    .eyebrow { font-size: .72rem; font-weight: 700; letter-spacing: .11em; margin-bottom: .35rem; }
    .page-description { font-size: 1rem; margin-top: -.25rem; }
    .section-rule { border: 0; border-top: 1px solid #E5E5E5; margin: 1.8rem 0 2rem; }
    .metric-card, .panel, .question-card {
        background: #FFFFFF !important; border: 1px solid #E5E5E5 !important; border-radius: 8px; box-shadow: none !important;
    }
    .metric-card { padding: 1.25rem 1.35rem; min-height: 112px; }
    .metric-label { font-size: .78rem; font-weight: 600; letter-spacing: .03em; text-transform: uppercase; }
    .metric-value { color: #000000 !important; font-size: 2rem; font-weight: 700; margin-top: .45rem; }
    .panel { padding: 1.45rem; }
    .question-card { padding: 1.5rem; margin-bottom: 1rem; }
    .question-label { font-size: .75rem; font-weight: 700; letter-spacing: .09em; }
    .question-text { color: #000000 !important; font-size: 1.35rem; font-weight: 650; margin: .45rem 0 .8rem; }
    .reason { font-size: .9rem; }
    .sidebar-brand { color: #000000 !important; font-weight: 750; font-size: 1.15rem; margin: 1.2rem .35rem .15rem; }
    .sidebar-subtitle { font-size: .76rem; letter-spacing: .04em; margin: 0 .35rem 1.65rem; }
    .stButton > button, .stFormSubmitButton > button {
        background: #000000 !important; color: #FFFFFF !important; border: 1px solid #000000 !important;
        border-radius: 7px !important; box-shadow: none !important; font-weight: 600; padding: .48rem 1rem;
    }
    .stButton > button *, .stFormSubmitButton > button * { color: #FFFFFF !important; }
    .stButton > button:hover, .stFormSubmitButton > button:hover { background: #FFFFFF !important; color: #000000 !important; }
    .stButton > button:hover *, .stFormSubmitButton > button:hover * { color: #000000 !important; }
    .stTextInput input, .stSelectbox select, [data-baseweb="select"] > div {
        background: #FFFFFF !important; color: #000000 !important; border: 1px solid #E5E5E5 !important;
        border-radius: 7px !important; box-shadow: none !important;
    }
    .stTextInput input::placeholder { color: #000000 !important; opacity: .55; }
    .stTextInput input:focus, [data-baseweb="select"] > div:focus-within {
        border-color: #000000 !important; box-shadow: none !important;
    }
    .stTextInput label, [data-testid="stDataFrame"], [data-testid="stDataFrame"] *,
    [data-testid="stExpander"], [data-testid="stExpander"] *, [data-testid="stAlert"], [data-testid="stAlert"] * {
        color: #000000 !important;
    }
    [data-testid="stDataFrame"], [data-testid="stExpander"], [data-testid="stAlert"] {
        background: #FFFFFF !important; border: 1px solid #E5E5E5 !important; border-radius: 8px !important; box-shadow: none !important;
    }
    [data-testid="stDataFrame"] * { white-space: normal !important; overflow-wrap: anywhere !important; }
    [data-testid="stCode"], [data-testid="stCode"] pre, [data-testid="stCode"] code, pre, code {
        background: #F7F7F7 !important; color: #000000 !important; border: 1px solid #E5E5E5 !important;
        white-space: pre-wrap !important; overflow-wrap: anywhere !important;
    }
    .answer-correct, .answer-incorrect { padding: .8rem 1rem; border-radius: 7px; font-weight: 700; margin: .8rem 0; }
    .answer-correct { color: #137333 !important; border: 1px solid #137333; background: #FFFFFF; }
    .answer-incorrect { color: #B3261E !important; border: 1px solid #B3261E; background: #FFFFFF; }
    [data-testid="stAlert"] svg, button svg, a svg { fill: #000000 !important; color: #000000 !important; }
    [data-testid="stAlert"] { background: #FFFFFF !important; }
    [role="tab"], [role="tablist"] { background: #FFFFFF !important; color: #000000 !important; border-color: #E5E5E5 !important; }
    *:focus-visible { outline: 1px solid #000000 !important; outline-offset: 1px; box-shadow: none !important; }
    @media (max-width: 700px) { .block-container { padding: 2rem 1.25rem; } }
</style>""", unsafe_allow_html=True)

if "memory" not in st.session_state:
    st.session_state.memory = load_memory()
else:
    # Keep an already-open browser session compatible when the app is updated.
    st.session_state.memory.setdefault("last_ai_question", None)
    st.session_state.memory.setdefault("last_ai_result", None)
    st.session_state.memory.setdefault("last_ai_user_answer", "")
    st.session_state.memory.setdefault("current_ai_topic", "")
    st.session_state.memory.setdefault("activity_log", [])
if "last_trace" not in st.session_state:
    st.session_state.last_trace = st.session_state.memory.get("last_trace", [])
if "last_result" not in st.session_state:
    st.session_state.last_result = st.session_state.memory.get("last_result")
if migrate_activity_timestamps(st.session_state.memory):
    save_memory(st.session_state.memory)


def agent_turn(goal, answer=None, topic=None):
    """Pass UI events to the shared agent without duplicating its logic."""
    response = run_agent(goal, st.session_state.memory, answer=answer, topic=topic)
    st.session_state.last_trace = response["trace"]
    st.session_state.last_result = response["result"]
    st.session_state.memory["last_trace"] = response["trace"]
    st.session_state.memory["last_result"] = response["result"]
    result = response["result"]
    if result.get("status") == "success":
        if goal.startswith("Add flashcard"):
            record_activity(st.session_state.memory, "Flashcard added", "Added a custom flashcard to your study set.")
        elif goal == "Start Normal Quiz.":
            record_activity(st.session_state.memory, "Normal quiz started", "Started a quiz using your custom flashcards.")
        elif goal in {"Start AI Quiz.", "Next AI Question."}:
            record_activity(st.session_state.memory, "AI quiz started", f"Started an AI quiz on {topic or st.session_state.memory.get('current_ai_topic', 'your selected topic')}.")
        elif goal == "Submit answer":
            outcome = "Correct answer" if result.get("correct") else "Incorrect answer"
            record_activity(st.session_state.memory, outcome, "Your answer was recorded and the learning memory was updated.")
    save_memory(st.session_state.memory)
    return response["result"]


def page_heading(label, title, description):
    st.markdown(f'<div class="eyebrow">{label}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<p class="page-description">{description}</p>', unsafe_allow_html=True)
    st.markdown('<hr class="section-rule">', unsafe_allow_html=True)


def metric_card(column, label, value):
    column.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>', unsafe_allow_html=True)


def show_metrics(summary):
    columns = st.columns(5)
    metric_card(columns[0], "Custom Cards", summary["total_cards"])
    metric_card(columns[1], "Answered", summary["total_questions_answered"])
    metric_card(columns[2], "Accuracy", f"{summary['accuracy_percentage']}%")
    metric_card(columns[3], "Correct", summary["correct_answers"])
    metric_card(columns[4], "Weak Topics", summary["weak_areas"])


def go_to(page, quiz_mode=None):
    st.session_state.navigation = page
    if quiz_mode:
        st.session_state.quiz_mode = quiz_mode


with st.sidebar:
    st.markdown('<div class="sidebar-brand">Adaptive Flashcard Agent</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-subtitle">PLAN &bull; TOOLS &bull; MEMORY</div>', unsafe_allow_html=True)
    navigation = st.radio("Navigation", ("Dashboard", "Flashcards", "Quiz", "Memory & Performance", "Agent Activity"), key="navigation", label_visibility="collapsed")

summary = memory_summary(st.session_state.memory)

if navigation == "Dashboard":
    page_heading("LEARNING OVERVIEW", "Dashboard", "Your high-level progress and the next best actions for studying.")
    columns = st.columns(4)
    metric_card(columns[0], "Total Flashcards", summary["total_cards"])
    metric_card(columns[1], "Questions Attempted", summary["total_questions_answered"])
    metric_card(columns[2], "Overall Accuracy", f"{summary['accuracy_percentage']}%")
    metric_card(columns[3], "Number of Weak Areas", summary["weak_areas"])
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.subheader("Quick actions")
    add_col, normal_col, ai_col = st.columns(3)
    add_col.button("Add Flashcard", key="dashboard_add", on_click=go_to, args=("Flashcards",))
    normal_col.button("Start Normal Quiz", key="dashboard_normal", on_click=go_to, args=("Quiz", "Normal Quiz"))
    ai_col.button("Start AI Quiz", key="dashboard_ai", on_click=go_to, args=("Quiz", "AI Quiz"))
    st.markdown("<div style='height: 1.2rem'></div>", unsafe_allow_html=True)
    activity_col, weak_col = st.columns(2)
    with activity_col:
        st.subheader("Recent activity")
        activity = st.session_state.memory.get("activity_log", [])
        if activity:
            for item in reversed(activity[-4:]):
                st.markdown(f"<div class='panel'><strong>{item['activity']}</strong><br><span class='reason'>{item['detail']} · {item['timestamp']}</span></div>", unsafe_allow_html=True)
        else:
            st.caption("No learning activity recorded yet. Add a flashcard or start a quiz to begin.")
    with weak_col:
        st.subheader("Weak areas to practise")
        if summary["weak_topics"]:
            for item in summary["weak_topics"][:3]:
                st.markdown(f"<div class='panel'><strong>{item['topic']}</strong><br><span class='reason'>Weakness score: {item['weakness_score']} · {item['wrong']} incorrect answer(s)</span></div>", unsafe_allow_html=True)
        else:
            st.caption("No weak areas identified yet. Your quiz results will reveal what to practise.")

elif navigation == "Flashcards":
    page_heading("FLASHCARD MANAGEMENT", "Flashcards", "Add questions and answers to the agent's memory.")
    st.subheader("Add flashcard")
    with st.form("add_card_form", clear_on_submit=True):
        question = st.text_input("Question")
        correct_answer = st.text_input("Answer")
        add_clicked = st.form_submit_button("Add Flashcard")
    if add_clicked:
        result = agent_turn(f"Add flashcard:\n{question} -> {correct_answer}")
        if result["status"] == "success":
            st.info(result["message"])
        else:
            st.error(result["message"])
    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)
    st.subheader("Stored flashcards")
    cards = st.session_state.memory["flashcards"]
    if cards:
        show_answers = st.checkbox("Show answers", value=False)
        rows = [{"ID": f"{card['id']:02d}", "QUESTION": card["question"]} for card in cards]
        if show_answers:
            rows = [{**row, "ANSWER": card["answer"]} for row, card in zip(rows, cards)]
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.caption("No flashcards have been added yet.")

elif navigation == "Quiz":
    page_heading("ADAPTIVE QUIZ", "Quiz", "Choose a custom-flashcard quiz or a topic-specific Groq AI quiz.")
    mode = st.radio("Quiz mode", ("Normal Quiz", "AI Quiz"), horizontal=True, key="quiz_mode")
    memory = st.session_state.memory
    active_ai = memory["active_question"]
    active_normal_id = memory["active_card_id"]
    last_result = st.session_state.last_result

    if mode == "Normal Quiz":
        st.subheader("Normal Quiz")
        if not memory["flashcards"]:
            st.info("No flashcards available. Add flashcards first or use AI Quiz.")
        if st.button("Start Normal Quiz", disabled=bool(active_ai or active_normal_id)):
            result = agent_turn("Start Normal Quiz.")
            if result["status"] != "success":
                st.info(result["message"])
            else:
                # The snapshot above was taken before the button handler ran;
                # render the card selected by quiz_me() from updated memory.
                active_normal_id = memory["active_card_id"]
        if active_normal_id:
            active = next(card for card in memory["flashcards"] if card["id"] == active_normal_id)
            st.markdown('<div class="question-card"><div class="question-label">CUSTOM FLASHCARD</div></div>', unsafe_allow_html=True)
            st.write(active["question"])
            with st.form("normal_answer_form", clear_on_submit=True):
                normal_answer = st.text_input("Your answer")
                normal_submitted = st.form_submit_button("Submit Answer")
            if normal_submitted:
                agent_turn("Submit answer", answer=normal_answer)
                st.rerun()
        elif last_result and last_result.get("quiz_mode") == "normal" and memory["current_quiz_mode"] is None:
            if last_result["correct"]:
                st.markdown('<div class="answer-correct">Correct</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="answer-incorrect">Incorrect</div>', unsafe_allow_html=True)
            st.write(last_result["feedback"])
            st.caption(f"Correct answer: {last_result['correct_answer']}")
            if st.button("Next Question", key="next_normal"):
                # Discard only the completed Normal Quiz result before asking
                # quiz_me() for a fresh local card.
                st.session_state.last_result = None
                memory["last_result"] = None
                agent_turn("Start Normal Quiz.")
                st.rerun()

    else:
        st.subheader("AI Quiz")
        if "ai_topic_input" not in st.session_state:
            st.session_state.ai_topic_input = memory["current_ai_topic"]
        topic = st.text_input("Enter a topic to study", key="ai_topic_input", placeholder="For example: Python OOP, DBMS, Operating Systems, SQL, APIs, or debugging")
        if st.button("Start AI Quiz", disabled=bool(active_ai or active_normal_id)):
            with st.spinner("Generating your topic-specific question…"):
                result = agent_turn("Start AI Quiz.", topic=topic)
            if result["status"] != "success":
                st.info(result["message"])
        if active_ai:
            st.markdown(f'<div class="question-card"><div class="question-label">{active_ai["topic"].upper()} · {active_ai["difficulty"].upper()} · {active_ai.get("question_type", "technical").upper()}</div></div>', unsafe_allow_html=True)
            st.markdown(active_ai["question"])
            if active_ai.get("code"):
                st.code(active_ai["code"])
            with st.form("ai_answer_form", clear_on_submit=True):
                ai_answer = st.text_input("Your answer")
                ai_submitted = st.form_submit_button("Submit Answer")
            if ai_submitted:
                with st.spinner("Evaluating your answer…"):
                    agent_turn("Submit answer", answer=ai_answer)
                st.rerun()
        elif memory["last_ai_question"] and memory["last_ai_result"]:
            completed_question = memory["last_ai_question"]
            completed_result = memory["last_ai_result"]
            st.markdown(f'<div class="question-card"><div class="question-label">{completed_question["topic"].upper()} · {completed_question["difficulty"].upper()} · {completed_question.get("question_type", "technical").upper()}</div></div>', unsafe_allow_html=True)
            st.markdown(completed_question["question"])
            if completed_question.get("code"):
                st.code(completed_question["code"])
            if completed_result["correct"]:
                st.markdown('<div class="answer-correct">Correct</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="answer-incorrect">Incorrect</div>', unsafe_allow_html=True)
            st.write(completed_result["feedback"])
            st.caption(f"Your answer: {memory['last_ai_user_answer']}")
            st.caption(f"Correct answer: {completed_result['correct_answer']}")
            st.write(completed_result.get("explanation", ""))
            if st.button("Next AI Question"):
                with st.spinner("Generating your next question…"):
                    result = agent_turn("Next AI Question.", topic=memory["current_ai_topic"])
                if result["status"] != "success":
                    st.info(result["message"])

elif navigation == "Memory & Performance":
    page_heading("AGENT MEMORY", "Memory & Performance", "Performance information stored and used by the agent in later quizzes.")
    show_metrics(summary)
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    analysis_left, analysis_right = st.columns(2)
    with analysis_left:
        st.subheader("Weak areas")
        if summary["weak_topics"]:
            st.dataframe([{"TOPIC": item["topic"], "CORRECT": item["correct"], "INCORRECT": item["wrong"], "WEAKNESS SCORE": item["weakness_score"]} for item in summary["weak_topics"]], width="stretch", hide_index=True)
        else:
            st.caption("No weak areas identified yet.")
    with analysis_right:
        st.subheader("Strong areas")
        if summary["strong_topics"]:
            st.dataframe([{"TOPIC": item["topic"], "CORRECT": item["correct"], "INCORRECT": item["wrong"]} for item in summary["strong_topics"]], width="stretch", hide_index=True)
        else:
            st.caption("Strong areas will appear after consistently correct answers.")
    st.markdown("<div style='height: 1.2rem'></div>", unsafe_allow_html=True)
    st.subheader("Performance by question")
    if summary["question_records"]:
        rows = []
        for card in summary["question_records"]:
            stats = st.session_state.memory["performance"][str(card["id"])]
            rows.append({"SOURCE": card.get("source", "custom").upper(), "TOPIC": card.get("topic", "Custom flashcards"), "QUESTION": card["question"], "CORRECT": stats["correct"], "WRONG": stats["wrong"], "WEAKNESS SCORE": stats["weakness_score"]})
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.caption("No performance data recorded yet.")
    st.markdown("<div style='height: 1.2rem'></div>", unsafe_allow_html=True)
    st.subheader("Recently asked questions")
    recent_questions = st.session_state.memory["recent_questions"]
    if recent_questions:
        st.write(" • ".join(item["question"] for item in recent_questions))
    else:
        st.caption("No cards have been asked yet.")
    st.subheader("Weak topics")
    if summary["weak_topics"]:
        st.write(" • ".join(f"{item['topic']} ({item['weakness_score']})" for item in summary["weak_topics"]))
    else:
        st.caption("No weak cards recorded yet.")

elif navigation == "Agent Activity":
    page_heading("PLAN → ACT → OBSERVE", "Agent Activity", "The real execution trace from the most recent agent interaction.")
    trace = st.session_state.last_trace
    if trace:
        rows = [{"STEP": item["step"], "TYPE": item["title"], "DETAILS": item["content"]} for item in trace]
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.markdown('<div class="panel">Agent activity will appear after you add a flashcard or start a quiz.</div>', unsafe_allow_html=True)
