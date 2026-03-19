AGENT_NAME = "data-generation-agent"
AGENT_VERSION = "0.1.0"
AGENT_MODE = "deterministic_minimal"

AGENT_SCOPE = [
    "deterministic_template_generation",
    "boundary_value_generation",
    "relationship_linking",
    "validation_before_output",
    "cleanup_instruction_output",
]

NON_GOALS = [
    "llm_first_generation",
    "production_data_copy",
    "business_assertion_rewrite",
]
