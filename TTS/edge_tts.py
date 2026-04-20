import asyncio
import os
import edge_tts

class EdgeTTS:
    """Edge TTS engine using the `edge-tts` library.

    Currently supports Vietnamese male neural voice `vi-VN-NamMinhNeural`.
    """

    def __init__(self):
        # Edge TTS does not have a character limit like some services, but we keep a reasonable default.
        self.max_chars = 5000
        self.voice = "vi-VN-NamMinhNeural"  # Male Vietnamese voice

    async def _generate(self, text: str, filepath: str):
        """Asynchronously generate speech and save to `filepath`."""
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(filepath)

    def run(self, text: str, filepath: str, random_voice: bool = False):
        """Generate speech synchronously.

        Parameters
        ----------
        text: str
            The text to synthesize.
        filepath: str
            Destination .mp3 file.
        random_voice: bool
            Ignored for Edge TTS (kept for API compatibility).
        """
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        # Run the async generation in a blocking manner
        asyncio.run(self._generate(text, filepath)
        )
