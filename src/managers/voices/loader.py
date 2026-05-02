import gc
import json
import logging
from pathlib import Path
from typing import Any, List

import onnxruntime
from piper import PiperConfig, PiperVoice

LOGGER = logging.getLogger(__name__)


def resolve_model_path(model: str, data_dirs: List[Path]) -> Path:
    model_path = Path(model)
    if model_path.exists():
        return model_path

    for data_dir in data_dirs:
        candidate = data_dir / f"{model}.onnx"
        LOGGER.debug("Checking '%s'", candidate)
        if candidate.exists():
            return candidate

    raise ValueError(f"Unable to find voice: {model}")


def load_voice(
    model_path: Path,
    *,
    use_cuda: bool,
    session_options: onnxruntime.SessionOptions,
    download_dir: Path,
) -> PiperVoice:
    config_path = Path(f"{model_path}.json")
    with open(config_path, "r", encoding="utf-8") as handle:
        config_dict = json.load(handle)

    providers: List[Any] = (
        [("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC"})]
        if use_cuda
        else ["CPUExecutionProvider"]
    )

    return PiperVoice(
        config=PiperConfig.from_dict(config_dict),
        session=onnxruntime.InferenceSession(
            str(model_path),
            sess_options=session_options,
            providers=providers,
        ),
        download_dir=download_dir,
    )


def unload_voice(voice: PiperVoice) -> None:
    try:
        del voice.session
    except AttributeError:
        pass
    finally:
        gc.collect()


__all__ = ["load_voice", "resolve_model_path", "unload_voice"]
