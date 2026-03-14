from starlette.requests import Request
from starlette.responses import HTMLResponse

from piper_http.core.context import AppContext
from piper_http.renderers.playroom.page import build_playroom_html


def build_playroom_handler(context: AppContext):
    def playroom(request: Request) -> HTMLResponse:
        return HTMLResponse(
            build_playroom_html(
                default_voice=context.voice_manager.default_model_id,
                speaker_id=context.args.speaker,
                length_scale=context.args.length_scale,
                noise_scale=context.args.noise_scale,
                noise_w_scale=context.args.noise_w_scale,
                sentence_silence=context.args.sentence_silence,
            )
        )

    return playroom
