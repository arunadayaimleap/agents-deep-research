import json
import re
from pydantic import BaseModel
from typing import Any, Callable, Optional


class OutputParserError(Exception):
    """
    Exception raised when the output parser fails to parse the output.
    """
    def __init__(self, message, output=None):
        self.message = message
        self.output = output
        super().__init__(self.message)
        
    def __str__(self):
        if self.output:
            return f"{self.message}\nProblematic output: {self.output}"
        return self.message


def find_json_in_string(string: str) -> str:
    """
    Method to extract all text in the left-most brace that appears in a string.
    Used to extract JSON from a string (note that this function does not validate the JSON).

    Example:
        string = "bla bla bla {this is {some} text{{}and it's sneaky}} because {it's} confusing"
        output = "{this is {some} text{{}and it's sneaky}}"
    """
    stack = 0
    start_index = None

    for i, c in enumerate(string):
        if c == '{':
            if stack == 0:
                start_index = i  # Start index of the first '{'
            stack += 1  # Push to stack
        elif c == '}':
            stack -= 1  # Pop stack
            if stack == 0:
                # Return the substring from the start of the first '{' to the current '}'
                return string[start_index:i + 1] if start_index is not None else ""

    # If no complete set of braces is found, return an empty string
    return ""


def _fix_common_json_issues(s: str) -> str:
    """Fix common LLM JSON mistakes (trailing commas, etc.)."""
    s = re.sub(r',\s*}', '}', s)
    s = re.sub(r',\s*]', ']', s)
    return s


def _is_json_schema_echo(obj: Any) -> bool:
    """
    True when the model echoed a JSON Schema / OpenAPI fragment instead of instance data.
    Common when instructions embed model_json_schema() and the model copies it verbatim.
    """
    if not isinstance(obj, dict):
        return False
    if "$defs" in obj or "$schema" in obj:
        return True
    # Schema object: type + properties, but no top-level data keys for our agents
    if obj.get("type") == "object" and "properties" in obj:
        if "research_complete" in obj or "tasks" in obj:
            return False
        return True
    return False


def _accept_or_reject_parsed(obj: Any) -> Any:
    """Return obj unless it is a schema echo (then None)."""
    if obj is None:
        return None
    if _is_json_schema_echo(obj):
        return None
    return obj


def _strip_hybrid_json_schema_instance(obj: Any) -> Any:
    """
    Some models return JSON Schema ($defs, properties) merged with real instance fields.
    If recognizable data is present, return a clean instance-shaped dict only.
    """
    if not isinstance(obj, dict):
        return obj
    has_noise = "$defs" in obj or "$schema" in obj or (
        obj.get("type") == "object" and "properties" in obj and "topics" in obj
    )
    if not has_noise:
        return obj
    # TopicCompilation: topics[] alongside schema metadata
    topics = obj.get("topics")
    if isinstance(topics, list) and topics and isinstance(topics[0], dict) and "title" in topics[0]:
        return {"topics": topics}
    # IndirectSearchPlan
    queries = obj.get("queries")
    if isinstance(queries, list) and queries and all(isinstance(q, str) for q in queries):
        return {
            "queries": queries,
            "planner_notes": obj.get("planner_notes") if isinstance(obj.get("planner_notes"), str) else "",
        }
    return obj


def parse_json_output(output: str) -> Any:
    """Take a string output and parse it as JSON. Handles markdown code blocks and common LLM mistakes."""
    if not output or not output.strip():
        raise OutputParserError("Failed to parse output as JSON", output)

    # Remove any <thought>...</thought> blocks before parsing
    output_clean = re.sub(r'<thought>.*?</thought>', '', output, flags=re.DOTALL)
    output_clean = output_clean.strip()

    def try_parse(s: str):
        s = s.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            try:
                return json.loads(_fix_common_json_issues(s))
            except json.JSONDecodeError:
                return None

    def normalize(obj: Any) -> Any:
        if obj is None:
            return None
        return _accept_or_reject_parsed(_strip_hybrid_json_schema_instance(obj))

    # 1. Direct parse
    result = normalize(try_parse(output_clean))
    if result is not None:
        return result

    # 2. Extract from markdown code blocks
    candidates = []
    if "```json" in output_clean:
        for block in re.findall(r'```json\s*([\s\S]*?)```', output_clean):
            candidates.append(block.strip())
    if "```" in output_clean:
        parts = re.split(r'```', output_clean)
        for i in range(1, len(parts), 2):
            block = parts[i].strip()
            if block and block.lower() not in ('json', ''):
                candidates.append(block[4:].strip() if block.lower().startswith('json') else block)

    for c in candidates:
        result = normalize(try_parse(c))
        if result is not None:
            return result

    # 3. Find JSON object by brace matching
    parsed_output = find_json_in_string(output_clean)
    if parsed_output:
        result = normalize(try_parse(parsed_output))
        if result is not None:
            return result

    raise OutputParserError("Failed to parse output as JSON", output[:500] + "..." if len(output) > 500 else output)


def create_type_parser(
    type: BaseModel,
    fallback_on_validation_error: Optional[Callable[[str], BaseModel]] = None,
) -> Callable[[str], BaseModel]:
    """Create a function that takes a string output and parses it as a specified Pydantic model.
    
    If fallback_on_validation_error is provided and model_validate fails (e.g. LLM output
    tool-call JSON instead of the expected schema), the fallback is called with the raw
    output string.
    """

    def convert_json_string_to_type(output: str) -> BaseModel:
        """Take a string output and parse it as a Pydantic model"""
        try:
            output_dict = parse_json_output(output)
            return type.model_validate(output_dict)
        except (OutputParserError, Exception) as e:
            if fallback_on_validation_error:
                return fallback_on_validation_error(output)
            raise

    return convert_json_string_to_type
