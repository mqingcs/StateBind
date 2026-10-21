DIRECT_PROMPT = """Answer the measurement question using only visible evidence in the image.
Give the numeric reading and its unit.
Do not infer a customary or typical value.

Question: {question}"""


PERCEPTION_PROMPT = """You are a visual measurement parser.

Use only visible evidence in the image and the user's question.
Do NOT calculate or output the final numeric reading.
Do NOT use customary values or hidden assumptions.
Coordinates are normalized to 0-1000. Use null or "unknown" when evidence is not visible.

Question: {question}

Return only the requested JSON object."""


PERCEPTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "design",
        "instrument_subtype",
        "scale_axis",
        "unit",
        "anchors",
        "readout",
        "coarse_interval",
        "ambiguity",
    ],
    "properties": {
        "design": {"type": "string", "enum": ["linear", "digital", "dial", "composite", "unknown"]},
        "instrument_subtype": {"type": "string"},
        "scale_axis": {
            "type": "object",
            "required": ["start", "end", "confidence"],
            "properties": {
                "start": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "end": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
        "unit": {
            "type": "object",
            "required": ["text", "confidence"],
            "properties": {
                "text": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
        "anchors": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "value", "point", "confidence"],
                "properties": {
                    "text": {"type": "string"},
                    "value": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                    "point": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
        "readout": {
            "type": "object",
            "required": ["operator", "reference_band", "target_band", "confidence"],
            "properties": {
                "operator": {
                    "type": "string",
                    "enum": [
                        "absolute_position",
                        "span_difference",
                        "boundary_position",
                        "dual_scale_alignment",
                        "unknown",
                    ],
                },
                "reference_band": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 2,
                                "maxItems": 2,
                            },
                            "minItems": 2,
                            "maxItems": 2,
                        },
                        {"type": "null"},
                    ]
                },
                "target_band": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 2,
                                "maxItems": 2,
                            },
                            "minItems": 2,
                            "maxItems": 2,
                        },
                        {"type": "null"},
                    ]
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
        "coarse_interval": {
            "type": "object",
            "required": ["lower", "upper"],
            "properties": {
                "lower": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                "upper": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            },
        },
        "ambiguity": {
            "type": "object",
            "required": ["anchor", "target", "double_scale", "notes"],
            "properties": {
                "anchor": {"type": "boolean"},
                "target": {"type": "boolean"},
                "double_scale": {"type": "boolean"},
                "notes": {"type": "string"},
            },
        },
    },
}


VBV_PROMPT = """You are a visual measurement position verifier.

The panel contains one unmarked REFERENCE image and five copies marked CANDIDATE A-E.
Each candidate proposes a possible visual position for the measurement asked in the question.
Select the one marker that best coincides with the actual visible indicator, liquid boundary,
object endpoint, or target boundary required by the question.

Do NOT calculate, infer, or report any numeric reading.
Do NOT prefer a candidate merely because of its label or panel position.
Select "none" if no proposed marker is visually supported.

Question: {question}

Return only the requested JSON object."""


VBV_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["selection", "confidence", "visual_reason"],
    "properties": {
        "selection": {"type": "string", "enum": ["A", "B", "C", "D", "E", "none"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "visual_reason": {"type": "string"},
    },
}
