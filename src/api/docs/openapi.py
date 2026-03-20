from copy import deepcopy


def _schema_ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def _synthesis_parameters(*, include_alignments: bool) -> list[dict]:
    parameters = [
        {
            "name": "text",
            "in": "query",
            "required": True,
            "schema": {"type": "string", "maxLength": 1000},
            "description": "Text to synthesize.",
        },
        {
            "name": "voice",
            "in": "query",
            "required": False,
            "schema": {"type": "string"},
            "description": "Voice id to use. Falls back to the configured default voice.",
        },
        {
            "name": "speaker",
            "in": "query",
            "required": False,
            "schema": {"type": "string"},
            "description": "Named speaker for multi-speaker voices.",
        },
        {
            "name": "speaker_id",
            "in": "query",
            "required": False,
            "schema": {"type": "integer", "minimum": 0},
            "description": "Numeric speaker id for multi-speaker voices.",
        },
        {
            "name": "sentence_silence",
            "in": "query",
            "required": False,
            "schema": {"type": "number", "minimum": 0},
            "description": "Seconds of silence inserted between synthesized chunks.",
        },
        {
            "name": "length_scale",
            "in": "query",
            "required": False,
            "schema": {"type": "number"},
            "description": "Piper synthesis length scale.",
        },
        {
            "name": "noise_scale",
            "in": "query",
            "required": False,
            "schema": {"type": "number"},
            "description": "Piper synthesis noise scale.",
        },
        {
            "name": "noise_w_scale",
            "in": "query",
            "required": False,
            "schema": {"type": "number"},
            "description": "Piper phoneme width noise scale.",
        },
        {
            "name": "volume",
            "in": "query",
            "required": False,
            "schema": {"type": "number"},
            "description": "Output volume multiplier.",
        },
        {
            "name": "normalize_audio",
            "in": "query",
            "required": False,
            "schema": {"type": "boolean"},
            "description": "Normalize audio amplitude before returning the WAV.",
        },
    ]

    if include_alignments:
        parameters.append(
            {
                "name": "include_alignments",
                "in": "query",
                "required": False,
                "schema": {"type": "boolean"},
                "description": "When true, return timestamp JSON instead of raw WAV.",
            }
        )

    return parameters


def _synthesis_request_body(*, include_alignments: bool) -> dict:
    schema = deepcopy(_schema_ref("SynthesisRequest"))

    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": schema,
                "examples": {
                    "basic": {
                        "summary": "Basic synthesis request",
                        "value": {
                            "text": "Hello world.",
                            "voice": "en_US-lessac-medium",
                            **({"include_alignments": True} if include_alignments else {}),
                        },
                    }
                },
            }
        },
    }


def _synthesis_responses(*, default_json: bool) -> dict:
    responses = {
        "400": {
            "description": "Invalid request payload.",
            "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
        },
        "404": {
            "description": "Requested voice could not be resolved.",
            "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
        },
        "500": {
            "description": "Unexpected synthesis failure.",
            "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
        },
    }

    if default_json:
        responses["200"] = {
            "description": "Base64 WAV audio with phoneme and approximate word timestamps.",
            "content": {
                "application/json": {"schema": _schema_ref("TimestampResponse")}
            },
        }
    else:
        responses["200"] = {
            "description": "Raw WAV audio by default, or JSON timestamps when include_alignments=true.",
            "content": {
                "audio/wav": {
                    "schema": {
                        "type": "string",
                        "format": "binary",
                    }
                },
                "application/json": {"schema": _schema_ref("TimestampResponse")},
            },
        }

    return responses


def _download_parameters() -> list[dict]:
    return [
        {
            "name": "voice",
            "in": "query",
            "required": True,
            "schema": {"type": "string"},
            "description": "Voice id to download.",
        },
        {
            "name": "force_redownload",
            "in": "query",
            "required": False,
            "schema": {"type": "boolean"},
            "description": "Re-download even if the voice already exists locally.",
        },
    ]


def build_openapi_schema() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Piper TTS HTTP API",
            "version": "1.0.0",
            "description": "HTTP API for Piper text-to-speech, voice downloads, and alignment timestamps.",
        },
        "tags": [
            {"name": "synthesis", "description": "Generate audio and timestamps."},
            {"name": "voices", "description": "Inspect or download voices."},
            {"name": "system", "description": "Server health and tools."},
        ],
        "paths": {
            "/": {
                "get": {
                    "tags": ["synthesis"],
                    "summary": "Synthesize speech",
                    "description": "Returns raw WAV by default. Set include_alignments=true to receive JSON with timestamps.",
                    "parameters": _synthesis_parameters(include_alignments=True),
                    "responses": _synthesis_responses(default_json=False),
                },
                "post": {
                    "tags": ["synthesis"],
                    "summary": "Synthesize speech",
                    "description": "Returns raw WAV by default. Set include_alignments=true to receive JSON with timestamps.",
                    "requestBody": _synthesis_request_body(include_alignments=True),
                    "responses": _synthesis_responses(default_json=False),
                },
            },
            "/timestamps": {
                "get": {
                    "tags": ["synthesis"],
                    "summary": "Synthesize speech with timestamps",
                    "description": "Always returns JSON with base64 WAV audio and alignment timestamps.",
                    "parameters": _synthesis_parameters(include_alignments=False),
                    "responses": _synthesis_responses(default_json=True),
                },
                "post": {
                    "tags": ["synthesis"],
                    "summary": "Synthesize speech with timestamps",
                    "description": "Always returns JSON with base64 WAV audio and alignment timestamps.",
                    "requestBody": _synthesis_request_body(include_alignments=False),
                    "responses": _synthesis_responses(default_json=True),
                },
            },
            "/download": {
                "get": {
                    "tags": ["voices"],
                    "summary": "Download a voice",
                    "parameters": _download_parameters(),
                    "responses": {
                        "200": {
                            "description": "Downloaded voice id.",
                            "content": {
                                "text/plain": {
                                    "schema": {"type": "string"}
                                }
                            },
                        },
                        "400": {
                            "description": "Invalid request.",
                            "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
                        },
                        "403": {
                            "description": "Downloads are disabled.",
                            "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
                        },
                        "429": {
                            "description": "Download already in progress or rate limited.",
                            "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
                        },
                        "500": {
                            "description": "Download failed.",
                            "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
                        },
                    },
                },
                "post": {
                    "tags": ["voices"],
                    "summary": "Download a voice",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": _schema_ref("DownloadRequest")
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Downloaded voice id.",
                            "content": {
                                "text/plain": {
                                    "schema": {"type": "string"}
                                }
                            },
                        },
                        "400": {
                            "description": "Invalid request.",
                            "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
                        },
                        "403": {
                            "description": "Downloads are disabled.",
                            "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
                        },
                        "429": {
                            "description": "Download already in progress or rate limited.",
                            "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
                        },
                        "500": {
                            "description": "Download failed.",
                            "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
                        },
                    },
                },
            },
            "/health": {
                "get": {
                    "tags": ["system"],
                    "summary": "Health check",
                    "responses": {
                        "200": {
                            "description": "Default voice is ready.",
                            "content": {"application/json": {"schema": _schema_ref("HealthResponse")}},
                        },
                        "503": {
                            "description": "Default voice is unavailable or not loadable.",
                            "content": {"application/json": {"schema": _schema_ref("HealthResponse")}},
                        },
                    },
                }
            },
            "/voices": {
                "get": {
                    "tags": ["voices"],
                    "summary": "List local voices",
                    "responses": {
                        "200": {
                            "description": "Locally available voices keyed by voice id.",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object", "additionalProperties": {"type": "object"}}
                                }
                            },
                        }
                    },
                }
            },
            "/all-voices": {
                "get": {
                    "tags": ["voices"],
                    "summary": "List full remote voice catalog",
                    "responses": {
                        "200": {
                            "description": "Full Piper voice catalog from the upstream manifest.",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object", "additionalProperties": True}
                                }
                            },
                        },
                        "500": {
                            "description": "Unable to fetch the upstream catalog.",
                            "content": {"application/json": {"schema": _schema_ref("ErrorResponse")}},
                        },
                    },
                }
            },
            "/playroom": {
                "get": {
                    "tags": ["system"],
                    "summary": "Playroom UI",
                    "responses": {
                        "200": {
                            "description": "Browser-based playroom page.",
                            "content": {
                                "text/html": {"schema": {"type": "string"}}
                            },
                        }
                    },
                }
            },
        },
        "components": {
            "schemas": {
                "ErrorResponse": {
                    "type": "object",
                    "required": ["error"],
                    "properties": {
                        "error": {"type": "string"}
                    },
                },
                "HealthResponse": {
                    "type": "object",
                    "required": ["status", "voice"],
                    "properties": {
                        "status": {"type": "string", "enum": ["ok", "error"]},
                        "voice": {"type": "string"},
                        "error": {"type": "string"},
                    },
                },
                "DownloadRequest": {
                    "type": "object",
                    "required": ["voice"],
                    "properties": {
                        "voice": {"type": "string"},
                        "force_redownload": {"type": "boolean", "default": False},
                    },
                },
                "SynthesisRequest": {
                    "type": "object",
                    "required": ["text"],
                    "properties": {
                        "text": {"type": "string", "maxLength": 1000},
                        "voice": {"type": "string"},
                        "speaker": {"type": "string"},
                        "speaker_id": {"type": "integer", "minimum": 0},
                        "sentence_silence": {"type": "number", "minimum": 0},
                        "length_scale": {"type": "number"},
                        "noise_scale": {"type": "number"},
                        "noise_w_scale": {"type": "number"},
                        "volume": {"type": "number"},
                        "normalize_audio": {"type": "boolean"},
                        "include_alignments": {"type": "boolean"},
                    },
                },
                "PhonemeTimestamp": {
                    "type": "object",
                    "required": ["phoneme", "start", "end"],
                    "properties": {
                        "phoneme": {"type": "string"},
                        "start": {"type": "number"},
                        "end": {"type": "number"},
                    },
                },
                "WordTimestamp": {
                    "type": "object",
                    "required": ["word", "start", "end", "phoneme_indices"],
                    "properties": {
                        "word": {"type": "string"},
                        "start": {"type": "number"},
                        "end": {"type": "number"},
                        "phoneme_indices": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                    },
                },
                "AlignmentResult": {
                    "type": "object",
                    "required": ["phonemes", "words"],
                    "properties": {
                        "phonemes": {
                            "type": "array",
                            "items": _schema_ref("PhonemeTimestamp"),
                        },
                        "words": {
                            "type": "array",
                            "items": _schema_ref("WordTimestamp"),
                        },
                    },
                },
                "TimestampResponse": {
                    "type": "object",
                    "required": [
                        "audio_base64",
                        "sample_rate",
                        "alignment_supported",
                        "alignments",
                    ],
                    "properties": {
                        "audio_base64": {"type": "string", "format": "byte"},
                        "sample_rate": {"type": "integer"},
                        "alignment_supported": {"type": "boolean"},
                        "alignment_error": {"type": "string"},
                        "alignments": _schema_ref("AlignmentResult"),
                    },
                },
            }
        },
    }


__all__ = ["build_openapi_schema"]