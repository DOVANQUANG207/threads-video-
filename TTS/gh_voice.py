import os
import torch
import numpy as np
import logging
import json
import re
from pydub import AudioSegment
from voices import GHVoice as GHVoiceModel, GHVoiceGenerationConfig
from utils import settings

class GHVoice:
    _model = None

    def __init__(self):
        self.max_chars = 2000
        if GHVoice._model is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            # Get model path from config with fallbacks
            tts_config = settings.config.get("settings", {}).get("tts", {})
            model_path = tts_config.get("gh_voice_model", "k2-fsa/OmniVoice")
            logging.info(f"Loading GH Voice model from {model_path} on {device}...")
            
            # Use float16 for CUDA to save memory and increase speed
            dtype = torch.float16 if device == "cuda" else torch.float32
            
            GHVoice._model = GHVoiceModel.from_pretrained(
                model_path,
                device_map=device,
                dtype=dtype,
                load_asr=False, # Disable ASR to save memory
            )
            logging.info("GH Voice model loaded successfully.")
        
        # Default voice name from config or use "Ngọc Huyền 01"
        tts_config = settings.config.get("settings", {}).get("tts", {})
        self.voice_name = tts_config.get("gh_voice_name", "Ngọc Huyền 01")
        self.load_voice_profile(self.voice_name)

    def apply_custom_dictionary(self, text: str) -> str:
        """Apply word replacements from vietnamese_dict.json."""
        dict_path = os.path.join(os.getcwd(), "vietnamese_dict.json")
        if not os.path.exists(dict_path):
            return text

        try:
            with open(dict_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)

            # Sort keys by length descending to avoid partial replacements
            sorted_keys = sorted(mapping.keys(), key=len, reverse=True)
            for key in sorted_keys:
                # Use regex to match whole words only (case-insensitive)
                pattern = re.compile(r'\b' + re.escape(key) + r'\b', re.IGNORECASE)
                text = pattern.sub(mapping[key], text)
        except Exception as e:
            logging.warning(f"Error applying custom dictionary: {e}")

        return text

    def load_voice_profile(self, name):
        saved_voices_dir = os.path.join(os.getcwd(), "saved_voices")
        voice_dir = os.path.join(saved_voices_dir, name)
        audio_path = os.path.join(voice_dir, "ref.wav")
        text_path = os.path.join(voice_dir, "ref.txt")
        
        if not os.path.exists(audio_path):
            logging.warning(f"Voice profile '{name}' not found at {audio_path}")
            self.ref_audio = None
            self.ref_text = None
            return
            
        self.ref_audio = audio_path
        self.ref_text = ""
        if os.path.exists(text_path):
            try:
                with open(text_path, "r", encoding="utf-8") as f:
                    self.ref_text = f.read().strip()
            except Exception as e:
                logging.error(f"Error reading ref.txt for voice '{name}': {e}")

    def run(self, text: str, filepath: str, random_voice: bool = False):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Apply dictionary
        text = self.apply_custom_dictionary(text.strip())
        
        gen_config = GHVoiceGenerationConfig(
            num_step=32,
            guidance_scale=2.0,
            denoise=True,
            preprocess_prompt=True,
            postprocess_output=True,
            audio_chunk_duration=8.0,
            audio_chunk_threshold=10.0,
        )

        kw = dict(
            text=text,
            language="Vietnamese",
            generation_config=gen_config
        )

        if self.ref_audio:
            kw["voice_clone_prompt"] = GHVoice._model.create_voice_clone_prompt(
                ref_audio=self.ref_audio,
                ref_text=self.ref_text,
            )

        logging.info(f"Generating audio for: {text[:50]}...")
        with torch.no_grad():
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            audio = GHVoice._model.generate(**kw)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        # Convert numpy to pydub AudioSegment
        waveform = (audio[0] * 32767).astype(np.int16)
        
        audio_segment = AudioSegment(
            waveform.tobytes(),
            frame_rate=GHVoice._model.sampling_rate,
            sample_width=2, # 16-bit
            channels=1
        )
        
        # Save to filepath (which usually ends in .mp3)
        audio_segment.export(filepath, format="mp3")
        logging.info(f"Audio saved to {filepath}")
