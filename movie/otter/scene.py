"""Scene base class.

A scene is a pure function of time: `render(stage, ctx, t)` draws frame t.
Subclasses set `name`, `title`, `duration`, `cam` and implement `draw`.
The narration (scenes/narration.py) supplies the subtitles and the timing.
"""
from __future__ import annotations

from .camera import CamPath, View
from .stage import Frame
from .widgets import captions as draw_captions


class Scene:
    name = 'sXX'
    title = ''
    duration = 10.0
    cam: CamPath = CamPath((0, 'FULL'))
    vignette = 0.5
    vo = None                    # otter.voiceover.VoTiming (narration timing), attached by render.py
    show_captions = True         # False for clean renders (subtitles delivered as a file)

    @property
    def length(self):
        """Output duration: the animation stretched to fit the narration."""
        return self.vo.duration if self.vo else self.duration

    def view(self, t) -> View:
        return self.cam(t)

    def draw(self, f: Frame, t: float):
        raise NotImplementedError

    def overlay(self, f: Frame, t: float):
        """Screen-space layer drawn after the vignette (panels, text)."""

    def scene_time(self, t_out):
        return self.vo.scene_time(t_out) if self.vo else t_out

    def render(self, stage, ctx, t_out, view=None, captions=True):
        """t_out is output time; with a voice-over it is mapped onto the scene clock.
        `view` overrides the camera (used to draw this scene's last frame
        through the next scene's camera during the cross-dissolve)."""
        t = self.scene_time(t_out)
        f = Frame(stage, ctx, view or self.view(t), t)
        f.background()
        self.draw(f, t)
        f.flush()
        if self.vignette:
            f.vignette(self.vignette)
        f.caption_band()
        self.overlay(f, t)
        if captions and self.show_captions and self.vo:
            draw_captions(ctx, self.vo.cues, t_out)
        self.post(f, t)

    def post(self, f: Frame, t: float):
        """Last layer (e.g. fades to black)."""
