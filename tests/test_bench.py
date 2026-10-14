"""bench/score.py answer parsing and bench/run_llm.py stream-json parsing."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))
import run_llm, score  # noqa: E402


def test_answer_files_and_scoring():
    ans = ("- `src/flask/views.py` — `MethodView.dispatch_request`\n"
           "- C:\\Users\\x\\AppData\\Local\\Temp\\atlas-bench\\runs\\flask_A_1_1\\src\\flask\\app.py: make_response\n"
           "- app/[slug]/orders/page.js and ./lib/notify.js, flask/views.py again")
    assert score.answer_files(ans) == ["src/flask/views.py", "src/flask/app.py", "app/[slug]/orders/page.js",
                                       "lib/notify.js", "flask/views.py"]
    case = {"gold_files": ["src/flask/views.py", "src/flask/sansio/x.py"], "gold_functions": ["View.dispatch_request"]}
    s = score.score_row({"answer": ans, "input_tokens": 1, "cache_creation": 2, "cache_read": 3}, case)
    assert (s["hit3"], s["recall3"], s["func_hit"], s["tokens_in"]) == (True, 0.5, True, 6)
    s = score.score_row({"answer": "views.py::dispatch", "input_tokens": 0, "cache_creation": 0, "cache_read": 0}, case)
    assert s["func_hit"] is False  # `dispatch` is not `dispatch_request`


def test_parse_log(tmp_path):
    ev = [
        {"type": "system", "subtype": "init", "skills": ["repo-atlas"], "plugins": [], "model": "m"},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "1", "name": "Read", "input": {"file_path": "C:\\r\\src\\a.py"}},
            {"type": "tool_use", "id": "2", "name": "Read", "input": {"file_path": "C:\\r\\.atlas\\INDEX.md"}},
            {"type": "tool_use", "id": "3", "name": "Bash", "input": {"command": "python .claude/skills/repo-atlas/scripts/locate.py . 'x'"}},
            {"type": "tool_use", "id": "4", "name": "Skill", "input": {"skill": "repo-atlas"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "1", "content": "x" * 100},
            {"type": "tool_result", "tool_use_id": "2", "content": [{"type": "text", "text": "y" * 50}]},
            {"type": "tool_result", "tool_use_id": "3", "content": "z" * 10}]}},
        {"type": "result", "result": "src/a.py", "num_turns": 3, "total_cost_usd": 0.1,
         "usage": {"input_tokens": 5, "cache_creation_input_tokens": 6, "cache_read_input_tokens": 7, "output_tokens": 8}},
    ]
    log = tmp_path / "x.jsonl"
    log.write_text("\n".join(map(json.dumps, ev)), "utf-8")
    r = run_llm.parse_log(log)
    assert (r["skills_visible"], r["tool_calls"], r["src_bytes_read"], r["tool_output_bytes"]) == (True, 4, 100, 160)
    assert (r["skill_invoked"], r["answer"], r["output_tokens"]) == (True, "src/a.py", 8)
