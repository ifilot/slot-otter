"""Scene base class.

A scene is a pure function of time: `render(stage, ctx, t)` draws frame t.
Subclasses set `name`, `duration`, `captions`, `cam` and implement `draw`.
"""
from __future__ import annotations

from .camera import CamPath, View
from .stage import Frame
from .widgets import captions as draw_captions


class Scene:
    name = 'sXX'
    title = ''
    duration = 10.0
    captions: list = []          # [(t0, t1, text)]
    cam: CamPath = CamPath((0, 'FULL'))
    vignette = 0.5
    vo = None                    # otter.voiceover.VoTiming for the voice-over cut

    @property
    def length(self):
        """Output duration: the silent duration, or the stretched voice-over one."""
        return self.vo.duration if self.vo else self.duration

    def view(self, t) -> View:
        return self.cam(t)

    def draw(self, f: Frame, t: float):
        raise NotImplementedError

    def overlay(self, f: Frame, t: float):
        """Screen-space layer drawn after the vignette (panels, text)."""

    def render(self, stage, ctx, t_out):
        """t_out is output time; with a voice-over it is mapped onto the scene clock."""
        t = self.vo.scene_time(t_out) if self.vo else t_out
        f = Frame(stage, ctx, self.view(t), t)
        f.background()
        self.draw(f, t)
        f.flush()
        if self.vignette:
            f.vignette(self.vignette)
        f.caption_band()
        self.overlay(f, t)
        if self.vo:
            draw_captions(ctx, self.vo.cues, t_out)
        else:
            draw_captions(ctx, self.cues(t), t)
        self.post(f, t)

    def cues(self, t):
        return self.captions

    def post(self, f: Frame, t: float):
        """Last layer (e.g. fades to black)."""
