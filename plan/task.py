from enum import Enum


class TaskType(str, Enum):
    def __new__(cls, value: str, desc: str = ""):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.desc = desc
        return obj

    decompose  = "decompose",  "break a large task into smaller, executable subtasks"
    search     = "search",     "search for information"
    mcp        = "mcp",        "call an MCP server"
    skill      = "skill",      "invoke a registered skill"
    tool       = "tool",       "use a configured tool or API"
    retrieve   = "retrieve",   "retrieve information from a vector store or database"
    read       = "read",       "read a document, file, or specific content"
    analyze    = "analyze",    "analyze collected information"
    synthesize = "synthesize", "combine multiple information sources into a unified result"
    summarize  = "summarize",  "summarize information"
    report     = "report",     "produce a report or final deliverable"
    validate   = "validate",   "self-check and evaluate output quality before delivering to the user"
