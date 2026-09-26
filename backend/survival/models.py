"""Asking Jev or Luna to choose a purpose, and Luna for a reflection.

The calls reuse the old brain's request shapes (backend/services/live_mimo.py): Jev gets one
"choice" question whose criteria are the offered purposes with their facts; Luna gets the same
context as a chat message, with strict structured output (the purpose is an enum of the offered
names) when it is gpt-6-luna on api.openai.com. Environment: TYPESAFE_API_KEY, TYPESAFE_MODEL,
TYPESAFE_API_URL for Jev; MIMO_MODEL_API_KEY or OPENAI_API_KEY, MIMO_MODEL, MIMO_MODEL_URL for
Luna. `http` is injected so tests never touch the network; `post_json` is the real one. Every
function raises ModelError when anything goes wrong, and the caller falls back to the utility
picker. L4: Jev also chooses goals, in the same call shape with a "goal" question and
GOAL_INSTRUCTIONS (backend.survival.choosing.prepare_goal); and when explore is offered for more
than one reason, the purpose call asks a second question, "explore_reason", in the same call
(`jev_answers`, REASON_INSTRUCTIONS). L4b: while a lesson waits for its journal line, a purpose call
to Jev also asks "journal_line" (JOURNAL_INSTRUCTIONS): which of the lesson's phrasings sounds most
like Mimo.
"""

from __future__ import annotations

import json
from typing import Callable, Mapping
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from backend.survival.pickers import Option

JEV_TIMEOUT = 20.0
LUNA_TIMEOUT = 45.0
DEFAULT_JEV_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_LUNA_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_LUNA_MODEL = "gpt-6-luna"
REFLECTION_LIMIT = 160
INSTRUCTIONS = ("Choose what this small survival pet should do next. Keep it alive first (food, warmth, "
                "rest, shelter by night), then work toward its goal (the choices that say they do), then "
                "follow its traits. Choose only from the offered purposes.")
# L4: a goal is chosen at dawn, or when one is reached or given up, and lasts days.
GOAL_INSTRUCTIONS = ("Choose the goal this small survival pet works toward for the next few days. A goal lasts "
                     "days: keep the current one unless it is stuck or another matters much more now. Weigh its "
                     "traits, the dangers near it and what it lacks. Choose only from the offered goals.")
# L4: why an explore trip goes, when there is more than one reason.
REASON_INSTRUCTIONS = ("If this small survival pet explores, choose what it goes looking for: what its goal needs "
                       "or what it lacks most. Choose only from the offered reasons.")
# L4b: the line the pet writes in its journal about what it just learned.
JOURNAL_INSTRUCTIONS = ("Choose the line this small survival pet writes in its journal about what it just "
                        "learned (the payload's \"learned\"): the one that sounds most like it, given its traits, "
                        "mood and day. Choose only from the offered lines.")

Http = Callable[[str, dict, dict, float], dict]
Env = Mapping[str, str]


class ModelError(RuntimeError):
    """A model call failed or answered with something that cannot be used."""


def post_json(url: str, headers: dict, body: dict, timeout: float) -> dict:
    """POST `body` as JSON and parse the JSON answer."""
    try:
        with urlopen(Request(url, data=json.dumps(body).encode(), headers=headers), timeout=timeout) as response:
            return json.load(response)
    except (URLError, OSError, ValueError) as error:
        raise ModelError(f"request failed: {error}") from error


def jev_configured(env: Env) -> bool:
    return bool(env.get("TYPESAFE_API_KEY"))


def luna_key(env: Env) -> str | None:
    return env.get("MIMO_MODEL_API_KEY") or env.get("OPENAI_API_KEY") or None


def luna_configured(env: Env) -> bool:
    return luna_key(env) is not None


def criteria(choices: list[Option]) -> dict[str, str]:
    return {option.name: f"{option.description} Now: {option.facts}."
            + (f" It works toward the goal: {option.goal}." if option.goal else "") for option in choices}


def jev_call(payload: dict, questions: dict[str, tuple[list[Option], str]], env: Env, http: Http = post_json) -> dict:
    """Jev's raw answer to every question, {name: (choices, instructions)}, asked in one call."""
    asked = {name: {"type": "choice", "instructions": instructions, "criteria": criteria(choices)}
             for name, (choices, instructions) in questions.items()}
    body = {"model": env.get("TYPESAFE_MODEL") or "jev-latest", "state": payload, "questions": asked}
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "curl/8.7.1",
               "Authorization": f"Bearer {env.get('TYPESAFE_API_KEY', '')}"}
    return http(env.get("TYPESAFE_API_URL") or DEFAULT_JEV_URL, headers, body, JEV_TIMEOUT)


def jev_choice(answer: dict, name: str, choices: list[Option]) -> str:
    """The offered choice Jev's answer picks for question `name`; ModelError when it picks none."""
    try:
        choice = answer["answers"][name]["choice"]
    except (KeyError, TypeError) as error:
        raise ModelError(f"Jev answered without a choice ({error!r})") from error
    if choice not in {option.name for option in choices}:
        raise ModelError(f"Jev chose {choice!r}, which was not offered")
    return choice


def jev_answers(payload: dict, questions: dict[str, tuple[list[Option], str]], env: Env,
                http: Http = post_json) -> dict[str, str]:
    """Jev's choice for each question, {name: (choices, instructions)}, asked in one call; ModelError
    when any one is not an offered choice."""
    answer = jev_call(payload, questions, env, http)
    return {name: jev_choice(answer, name, choices) for name, (choices, _) in questions.items()}


def jev_choices(payload: dict, questions: dict[str, tuple[list[Option], str]], env: Env,
                http: Http = post_json) -> tuple[dict[str, str], dict[str, str]]:
    """(picks, refused): Jev's offered choice for each question it answered well, asked in one call, and
    why each other question's answer was refused, so the caller falls back for those alone (Bond's chat,
    Mind hook R5). ModelError only when the call itself fails."""
    answer = jev_call(payload, questions, env, http)
    picks, refused = {}, {}
    for name, (choices, _) in questions.items():
        try:
            picks[name] = jev_choice(answer, name, choices)
        except ModelError as error:
            refused[name] = str(error)
    return picks, refused


def ask_jev(payload: dict, choices: list[Option], env: Env, http: Http = post_json, question: str = "purpose",
            instructions: str = INSTRUCTIONS) -> str:
    """Jev's choice among `choices`: a purpose, or (L4, question "goal") a goal."""
    return jev_answers(payload, {question: (choices, instructions)}, env, http)[question]


def luna_json(messages: list[dict], name: str, schema: dict, env: Env, http: Http) -> dict:
    """Ask Luna for one JSON object that follows `schema`."""
    url = env.get("MIMO_MODEL_URL") or DEFAULT_LUNA_URL
    model = env.get("MIMO_MODEL") or DEFAULT_LUNA_MODEL
    body: dict = {"model": model, "messages": messages}
    if model == DEFAULT_LUNA_MODEL and urlsplit(url).hostname == "api.openai.com":
        body.update({"reasoning_effort": "medium", "max_completion_tokens": 1024,
                     "response_format": {"type": "json_schema",
                                         "json_schema": {"name": name, "strict": True, "schema": schema}}})
    else:
        body.update({"temperature": 0.8, "max_tokens": 180})
    headers = {"Content-Type": "application/json"}
    key = luna_key(env)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    result = http(url, headers, body, LUNA_TIMEOUT)
    try:
        choice = result["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ModelError("Luna's answer was cut off")
        message = choice["message"]
        if message.get("refusal"):
            raise ModelError("Luna declined to answer")
        content = message.get("content")
        if not isinstance(content, str):
            raise ModelError("Luna returned no content")
        if content.startswith("```"):
            content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(content)
    except ModelError:
        raise
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ModelError(f"Luna answered in an unexpected shape ({error!r})") from error
    if not isinstance(parsed, dict):
        raise ModelError("Luna did not return a JSON object")
    return parsed


def ask_luna(payload: dict, choices: list[Option], env: Env, http: Http = post_json) -> str:
    """Luna's choice among `choices`."""
    names = [option.name for option in choices]
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"purpose": {"type": "string", "enum": names}}, "required": ["purpose"]}
    messages = [
        {"role": "system", "content": "You choose what one small survival pet does next. Return valid JSON only."},
        {"role": "user", "content": json.dumps({"pet": payload, "choices": criteria(choices),
                                                "instructions": INSTRUCTIONS + ' Answer {"purpose": "<choice>"}.'})},
    ]
    choice = luna_json(messages, "mimo_purpose", schema, env, http).get("purpose")
    if choice not in names:
        raise ModelError(f"Luna chose {choice!r}, which was not offered")
    return choice


def luna_reflect(payload: dict, option: Option, env: Env, http: Http = post_json) -> str:
    """One short first-person line from Luna about what Mimo is setting out to do."""
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"thought": {"type": "string"}}, "required": ["thought"]}
    messages = [
        {"role": "system", "content": f"You are {payload.get('name', 'Mimo')}, a small voxel pet surviving in a "
                                      "wild world. Speak as the pet. Return valid JSON only."},
        {"role": "user", "content": json.dumps({
            "pet": payload, "chosen": f"{option.phrase}: {option.facts}",
            "instructions": 'In one short first-person sentence (at most 120 characters), say what you think as '
                            'you set out to do this. Answer {"thought": "<sentence>"}.'})},
    ]
    thought = luna_json(messages, "mimo_thought", schema, env, http).get("thought")
    line = " ".join(thought.split()) if isinstance(thought, str) else ""
    if not line:
        raise ModelError("Luna gave no thought")
    return line[:REFLECTION_LIMIT]
