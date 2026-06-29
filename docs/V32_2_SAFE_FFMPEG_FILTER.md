# V32.2 Safe FFmpeg Filter Fix

Fixes FFmpeg render failure caused by invalid crop filter expressions using `on`.

V32.2 uses a conservative scale/crop filter first so Render Test MP4 works reliably.
Camera movement/Ken Burns can be reintroduced later after render stability is confirmed.
