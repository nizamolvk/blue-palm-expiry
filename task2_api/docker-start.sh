#!/bin/sh
set -eu
python - <<'PY'
from task2_api.database import Base, make_engine, make_session_factory
from task2_api.load_data import load_csv
import task4_agent.models
from task4_agent.reminder_agent import run

engine = make_engine()
Base.metadata.create_all(engine)
session = make_session_factory(engine)()
try:
    load_csv(session)
    run(session)
finally:
    session.close()
PY
exec uvicorn task4_agent.main:app --host 0.0.0.0 --port 8000
