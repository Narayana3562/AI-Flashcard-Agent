# Adaptive Flashcard Quiz Agent

Adaptive Flashcard Quiz Agent is a Python study application for creating flashcards, practising them, tracking performance, and prioritising weak areas.

## Architecture

```text
Manual Flashcards -> Python add_card() -> Python Memory
Normal Quiz -> Python quiz_me() + evaluate_answer() -> Performance Memory + Weak-Card Prioritization
AI Quiz -> Groq -> Dynamic Technical Question Generation and Answer Evaluation
```

The manual-flashcard and Normal Quiz paths are deterministic Python workflows. They work without network access or `GROQ_API_KEY`. Groq is used only by AI Quiz to generate a technical question and to semantically evaluate its answer. Python is always responsible for writing memory.

## CA-1 requirements covered

- One shared `run_agent()` entry point.
- Persistent flashcard, performance, active-question, recent-question, topic-performance, and conversation memory.
- Real deterministic Python tools: `add_card()`, `quiz_me()`, and `evaluate_answer()`.
- Actual tool execution and observations shown in an execution trace.
- Correct/wrong counts and weakness scores that influence later Normal Quiz selection.
- Groq-powered AI Quiz generation and evaluation when configured.
- Streamlit UI and a Jupyter notebook that reuse the same project modules.

## Tools and memory

`add_card(question, answer)` creates a custom flashcard and its initial performance record. `quiz_me()` selects a custom flashcard using weakness score, incorrect attempts, and recent-card variety. `evaluate_answer()` checks the Normal Quiz answer and updates correct/wrong counts and weakness score.

Memory records custom and generated questions, per-question performance, per-topic performance, recently asked questions, active quiz state, and conversation history. A wrong answer increases weakness; a correct answer reduces it (never below zero). This lets a later Normal Quiz prioritise a previously weak custom card.

## Quiz modes

### Manual Flashcards and Normal Quiz

The user enters a question and answer in the Flashcards page. The agent records the user action, calls local Python `add_card()`, observes the result, updates Python memory, and returns the result. No Groq request occurs.

Starting Normal Quiz calls local `quiz_me()`. Submitting its answer calls local `evaluate_answer()`. These paths remain available offline and demonstrate the core adaptive-agent behaviour.

### AI Quiz

The user enters a technical topic such as Python, DBMS, SQL, APIs, Operating Systems, or debugging. Groq generates one topic-specific question. After the user answers, Groq evaluates it semantically. Validated results are then stored by Python using the project memory tools. AI Quiz requires `GROQ_API_KEY` and network access.

## Execution trace

The application shows the real workflow for each interaction. A manual addition trace includes:

```text
MEMORY READ -> USER ACTION -> PLAN -> TOOL DECISION -> TOOL CALL
-> OBSERVATION -> MEMORY UPDATE -> FINAL RESPONSE
```

Normal Quiz traces show local selection/evaluation and memory updates. AI Quiz traces additionally show Groq question generation or answer evaluation. The trace is an observation of the shared agent's actual calls, not a simulated sequence.

## Project structure

```text
adaptive_flashcard_agent/
|- app.py                         # Streamlit UI
|- agent.py                       # Shared workflow and Groq AI Quiz integration
|- tools.py                       # Deterministic Python tools
|- memory.py                      # Session and local-disk memory
|- adaptive_flashcard_agent.ipynb # Offline Normal Quiz demonstration
|- requirements.txt
|- .env.example
`- .gitignore
```

## Run locally

1. Create and activate a virtual environment:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Run the application:

   ```powershell
   streamlit run app.py
   ```

3. To enable AI Quiz, create `.env` from `.env.example` and set:

   ```text
   GROQ_API_KEY=your_actual_key
   ```

Do not hardcode the API key. It is not needed for manual flashcards or Normal Quiz.

## Failure handling

- Missing/invalid manual flashcard input: Python reports the expected `Question -> Answer` format and does not change memory.
- No custom flashcards: `quiz_me()` returns an actionable empty-state message.
- Missing `GROQ_API_KEY` or Groq request failure: only the AI Quiz action reports the configuration/request error; existing Python memory is preserved.
- Malformed Groq AI Quiz output: it is rejected before Python writes it to memory.

## Notebook demonstration

`adaptive_flashcard_agent.ipynb` imports the shared `run_agent()` and memory functions. It runs offline from top to bottom, demonstrates manual additions, a correct and an incorrect Normal Quiz answer, performance/weakness updates, later weak-card prioritisation, and the actual execution traces. It contains no duplicated agent or tool logic.
