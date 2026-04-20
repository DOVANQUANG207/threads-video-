#!/usr/bin/env python3
# Copyright    2026  Xiaomi Corp.        (authors:  Han Zhu)
#
import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
# See ../../LICENSE for clarification regarding multiple authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Gradio demo for GHVoice.

Supports voice cloning and voice design.

Usage:
    GHvoice-demo --model /path/to/checkpoint --port 8000
"""

import argparse
import logging
import json
import os
import re
import shutil
from typing import Any, Dict

import gradio as gr
import numpy as np
import torch

from voices import GHVoice, GHVoiceGenerationConfig
from voices.utils.lang_map import LANG_NAMES, lang_display_name


def get_best_device():
    """Auto-detect the best available device: CUDA > MPS > CPU."""
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def apply_custom_dictionary(text: str) -> str:
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
            # Add word boundaries \b so that "t" doesn't match inside "thích"
            pattern = re.compile(r'\b' + re.escape(key) + r'\b', re.IGNORECASE)
            text = pattern.sub(mapping[key], text)
    except Exception as e:
        logging.warning(f"Error applying custom dictionary: {e}")

    return text


# ---------------------------------------------------------------------------
# Saved Voices Backend
# ---------------------------------------------------------------------------
SAVED_VOICES_DIR = os.path.join(os.getcwd(), "saved_voices")
os.makedirs(SAVED_VOICES_DIR, exist_ok=True)

def get_saved_voices():
    voices = []
    if os.path.exists(SAVED_VOICES_DIR):
        for d in os.listdir(SAVED_VOICES_DIR):
            if os.path.isdir(os.path.join(SAVED_VOICES_DIR, d)):
                voices.append(d)
    return sorted(voices)

def load_voice_profile(name):
    if not name:
        return None, None
    voice_dir = os.path.join(SAVED_VOICES_DIR, name)
    audio_path = os.path.join(voice_dir, "ref.wav")
    text_path = os.path.join(voice_dir, "ref.txt")
    
    if not os.path.exists(audio_path):
        return None, None
        
    text = ""
    if os.path.exists(text_path):
        with open(text_path, "r", encoding="utf-8") as f:
            text = f.read().strip()
            
    return audio_path, text

def save_voice_profile(name, audio_path, text):
    if not name or not name.strip():
        return "Vui lòng nhập tên cho giọng nói này."
    if not audio_path:
        return "Vui lòng cung cấp âm thanh mẫu."
        
    name = name.strip()
    # Basic sanitize
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    
    voice_dir = os.path.join(SAVED_VOICES_DIR, name)
    os.makedirs(voice_dir, exist_ok=True)
    
    dest_audio = os.path.join(voice_dir, "ref.wav")
    shutil.copy(audio_path, dest_audio)
    
    dest_text = os.path.join(voice_dir, "ref.txt")
    with open(dest_text, "w", encoding="utf-8") as f:
        f.write(text or "")
        
    return f"Đã lưu thành công giọng nói '{name}'!"


# ---------------------------------------------------------------------------
# Language list — all 600+ supported languages
# ---------------------------------------------------------------------------
_ALL_LANGUAGES = ["Auto"] + sorted(lang_display_name(n) for n in LANG_NAMES)


# ---------------------------------------------------------------------------
# Voice Design instruction templates
# ---------------------------------------------------------------------------
# Each option is displayed as "English / 中文".
# The model expects English for accents and Chinese for dialects.
_CATEGORIES = {
    "Giới tính": ["Nam / Male", "Nữ / Female"],
    "Độ tuổi": [
        "Trẻ em / Child",
        "Thiếu niên / Teenager",
        "Thanh niên / Young Adult",
        "Trung niên / Middle-aged",
        "Người già / Elderly",
    ],
    "Tông giọng": [
        "Rất thấp / Very Low",
        "Thấp / Low",
        "Vừa phải / Moderate",
        "Cao / High",
        "Rất cao / Very High",
    ],
    "Phong cách": ["Thì thầm / Whisper"],
    "Khẩu âm Tiếng Anh": [
        "Mỹ / American",
        "Úc / Australian",
        "Anh / British",
        "Trung Quốc / Chinese",
        "Canada / Canadian",
        "Ấn Độ / Indian",
        "Hàn Quốc / Korean",
        "Bồ Đào Nha / Portuguese",
        "Nga / Russian",
        "Nhật Bản / Japanese",
    ],
    "Phương ngôn Tiếng Trung": [
        "Hà Nam / Henan",
        "Thiểm Tây / Shaanxi",
        "Tứ Xuyên / Sichuan",
        "Quý Châu / Guizhou",
        "Vân Nam / Yunnan",
        "Quế Lâm / Guilin",
        "Tế Nam / Jinan",
        "Thạch Gia Trang / Shijiazhuang",
        "Cam Túc / Gansu",
        "Ninh Hạ / Ningxia",
        "Thanh Đảo / Qingdao",
        "Đông Bắc / Northeast",
    ],
}

_ATTR_INFO = {
    "English Accent / 英文口音": "Only effective for English speech.",
    "Chinese Dialect / 中文方言": "Only effective for Chinese speech.",
}

# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="GHvoice-demo",
        description="Launch a Gradio demo for GHVoice.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--model",
        default="k2-fsa/OmniVoice",
        help="Model checkpoint path or HuggingFace repo id.",
    )
    parser.add_argument(
        "--device", default=None, help="Device to use. Auto-detected if not specified."
    )
    parser.add_argument("--ip", default="0.0.0.0", help="Server IP (default: 0.0.0.0).")
    parser.add_argument(
        "--port", type=int, default=7860, help="Server port (default: 7860)."
    )
    parser.add_argument(
        "--root-path",
        default=None,
        help="Root path for reverse proxy.",
    )
    parser.add_argument(
        "--share", action="store_true", default=False, help="Create public link."
    )
    parser.add_argument(
        "--no-asr",
        action="store_true",
        default=False,
        help="Skip loading Whisper ASR model. Reference text auto-transcription"
        " will be unavailable.",
    )
    return parser


# ---------------------------------------------------------------------------
# Build demo
# ---------------------------------------------------------------------------


def build_demo(
    model: GHVoice,
    checkpoint: str,
    generate_fn=None,
) -> gr.Blocks:

    sampling_rate = model.sampling_rate

    # -- shared generation core --
    def _gen_core(
        text,
        language,
        ref_audio,
        instruct,
        num_step,
        guidance_scale,
        denoise,
        speed,
        duration,
        preprocess_prompt,
        postprocess_output,
        mode,
        ref_text=None,
    ):
        if not text or not text.strip():
            return None, "Vui lòng nhập văn bản cần chuyển thành giọng nói."

        # Apply custom dictionary replacements
        text = apply_custom_dictionary(text.strip())

        gen_config = GHVoiceGenerationConfig(
            num_step=int(num_step or 32),
            guidance_scale=float(guidance_scale) if guidance_scale is not None else 2.0,
            denoise=bool(denoise) if denoise is not None else True,
            preprocess_prompt=bool(preprocess_prompt),
            postprocess_output=bool(postprocess_output),
            audio_chunk_duration=8.0,
            audio_chunk_threshold=10.0,
        )

        lang = language if (language and language != "Auto") else None

        kw: Dict[str, Any] = dict(
            text=text.strip(), language=lang, generation_config=gen_config
        )

        if speed is not None and float(speed) != 1.0:
            kw["speed"] = float(speed)
        if duration is not None and float(duration) > 0:
            kw["duration"] = float(duration)

        if mode == "clone":
            if not ref_audio:
                return None, "Vui lòng tải lên file âm thanh mẫu."
            kw["voice_clone_prompt"] = model.create_voice_clone_prompt(
                ref_audio=ref_audio,
                ref_text=ref_text,
            )

        if instruct and instruct.strip():
            kw["instruct"] = instruct.strip()

        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            audio = model.generate(**kw)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:
            return None, f"Lỗi: {type(e).__name__}: {e}"

        waveform = (audio[0] * 32767).astype(np.int16)
        return (sampling_rate, waveform), "Hoàn thành."

    # Allow external wrappers (e.g. spaces.GPU for ZeroGPU Spaces)
    _gen = generate_fn if generate_fn is not None else _gen_core

    # =====================================================================
    # UI
    # =====================================================================
    theme = gr.themes.Soft(
        font=["Inter", "Arial", "sans-serif"],
    )
    css = """
    .gradio-container {max-width: 100% !important; font-size: 16px !important;}
    .gradio-container h1 {font-size: 1.5em !important;}
    .gradio-container .prose {font-size: 1.1em !important;}
    .compact-audio audio {height: 60px !important;}
    .compact-audio .waveform {min-height: 80px !important;}
    """

    # Reusable: language dropdown component
    def _lang_dropdown(label="Ngôn ngữ (tùy chọn)", value="Auto"):
        return gr.Dropdown(
            label=label,
            choices=_ALL_LANGUAGES,
            value=value,
            allow_custom_value=False,
            interactive=True,
            info="Để 'Auto' để tự động nhận diện ngôn ngữ.",
        )

    # Reusable: optional generation settings accordion
    def _gen_settings():
        with gr.Accordion("Cài đặt nâng cao (tùy chọn)", open=False):
            sp = gr.Slider(
                0.5,
                1.5,
                value=1.0,
                step=0.05,
                label="Tốc độ",
                info="1.0 = bình thường. >1 nhanh hơn, <1 chậm hơn. Bị bỏ qua nếu đặt Độ dài.",
            )
            du = gr.Number(
                value=None,
                label="Độ dài (giây)",
                info=(
                    "Để trống để dùng tốc độ."
                    " Đặt một giá trị cố định sẽ ghi đè tốc độ."
                ),
            )
            ns = gr.Slider(
                4,
                64,
                value=32,
                step=1,
                label="Số bước suy luận",
                info="Mặc định: 32. Càng thấp càng nhanh, càng cao chất lượng càng tốt.",
            )
            dn = gr.Checkbox(
                label="Khử nhiễu (Denoise)",
                value=True,
                info="Mặc định: bật. Tắt để không khử nhiễu.",
            )
            gs = gr.Slider(
                0.0,
                4.0,
                value=2.0,
                step=0.1,
                label="Thang đo hướng dẫn (CFG)",
                info="Mặc định: 2.0.",
            )
            pp = gr.Checkbox(
                label="Tiền xử lý mẫu (Preprocess)",
                value=True,
                info="Loại bỏ khoảng lặng và cắt gọt âm thanh mẫu.",
            )
            po = gr.Checkbox(
                label="Hậu xử lý kết quả (Postprocess)",
                value=True,
                info="Loại bỏ các khoảng lặng dài trong âm thanh được tạo ra.",
            )
        return ns, gs, dn, sp, du, pp, po

    with gr.Blocks(theme=theme, css=css, title="GH Voice Demo - Việt hóa") as demo:
        gr.Markdown(
            """
# GH Voice - Giao diện Tiếng Việt 🌍
Mô hình chuyển đổi văn bản thành giọng nói (TTS) tiên tiến hỗ trợ hơn **600 ngôn ngữ**.

- **Sao chép giọng nói (Voice Clone)** — Bắt chước bất kỳ giọng nói nào từ âm thanh mẫu.
- **Thiết kế giọng nói (Voice Design)** — Tạo giọng nói tùy chỉnh dựa trên các thuộc tính.

Được phát triển dựa trên [GH Voice].
"""
        )

        with gr.Tabs():
            # ==============================================================
            # Voice Clone
            # ==============================================================
            with gr.TabItem("Sao chép giọng nói"):
                with gr.Row():
                    with gr.Column(scale=1):
                        vc_text = gr.Textbox(
                            label="Văn bản cần tổng hợp",
                            lines=4,
                            placeholder="Nhập nội dung bạn muốn chuyển thành giọng nói...",
                        )
                        vc_ref_audio = gr.Audio(
                            label="Âm thanh mẫu (Reference Audio)",
                            type="filepath",
                            elem_classes="compact-audio",
                        )
                        gr.Markdown(
                            "<span style='font-size:0.85em;color:#888;'>"
                            "Khuyên dùng: Đoạn âm thanh từ 3–10 giây. "
                            "</span>"
                        )
                        vc_ref_text = gr.Textbox(
                            label="Văn bản của âm thanh mẫu (tùy chọn)",
                            lines=2,
                            placeholder="Nhập lời của đoạn âm thanh mẫu. Để trống để tự động nhận diện.",
                        )
                        vc_lang = _lang_dropdown("Ngôn ngữ (tùy chọn)")
                        with gr.Accordion("Hướng dẫn bổ sung (tùy chọn)", open=False):
                            vc_instruct = gr.Textbox(label="Hướng dẫn (Instruct)", lines=2)
                        (
                            vc_ns,
                            vc_gs,
                            vc_dn,
                            vc_sp,
                            vc_du,
                            vc_pp,
                            vc_po,
                        ) = _gen_settings()
                        vc_btn = gr.Button("Bắt đầu tạo / Generate", variant="primary")
                    with gr.Column(scale=1):
                        vc_audio = gr.Audio(
                            label="Kết quả âm thanh",
                            type="numpy",
                        )
                        vc_status = gr.Textbox(label="Trạng thái", lines=2)
                        
                        with gr.Accordion("💾 Lưu giọng nói thành hồ sơ riêng", open=False):
                            gr.Markdown("<span style='font-size:0.85em;color:#888;'>Lưu lại đoạn âm thanh mẫu và văn bản này để tái sử dụng ở tab **Train giọng** bên cạnh.</span>")
                            vc_save_name = gr.Textbox(label="Tên giọng nói", lines=1, placeholder="Ví dụ: Giọng nam MC")
                            vc_save_btn = gr.Button("Lưu thành giọng mới", size="sm")
                            vc_save_status = gr.Textbox(label="Trạng thái lưu", lines=1)
                            vc_save_btn.click(
                                save_voice_profile,
                                inputs=[vc_save_name, vc_ref_audio, vc_ref_text],
                                outputs=[vc_save_status]
                            )

                def _clone_fn(
                    text, lang, ref_aud, ref_text, instruct, ns, gs, dn, sp, du, pp, po
                ):
                    return _gen(
                        text,
                        lang,
                        ref_aud,
                        instruct,
                        ns,
                        gs,
                        dn,
                        sp,
                        du,
                        pp,
                        po,
                        mode="clone",
                        ref_text=ref_text or None,
                    )

                vc_btn.click(
                    _clone_fn,
                    inputs=[
                        vc_text,
                        vc_lang,
                        vc_ref_audio,
                        vc_ref_text,
                        vc_instruct,
                        vc_ns,
                        vc_gs,
                        vc_dn,
                        vc_sp,
                        vc_du,
                        vc_pp,
                        vc_po,
                    ],
                    outputs=[vc_audio, vc_status],
                )

            # ==============================================================
            # Train Giong (Voice Profile)
            # ==============================================================
            with gr.TabItem("Train giọng (Giọng đã lưu)"):
                with gr.Row():
                    with gr.Column(scale=1):
                        vt_text = gr.Textbox(
                            label="Văn bản cần tổng hợp",
                            lines=4,
                            placeholder="Nhập nội dung bạn muốn chuyển thành giọng nói...",
                        )
                        with gr.Row():
                            vt_profile = gr.Dropdown(
                                label="Chọn giọng nói đã lưu",
                                choices=get_saved_voices()
                            )
                            vt_refresh_btn = gr.Button("🔄 Làm mới danh sách", size="sm")
                        
                        vt_lang = _lang_dropdown()
                        with gr.Accordion("Hướng dẫn bổ sung (tùy chọn)", open=False):
                            vt_instruct = gr.Textbox(label="Hướng dẫn (Instruct)", lines=2)
                        (
                            vt_ns,
                            vt_gs,
                            vt_dn,
                            vt_sp,
                            vt_du,
                            vt_pp,
                            vt_po,
                        ) = _gen_settings()
                        vt_btn = gr.Button("Bắt đầu tạo / Generate", variant="primary")
                    with gr.Column(scale=1):
                        vt_audio = gr.Audio(
                            label="Kết quả âm thanh",
                            type="numpy",
                        )
                        vt_status = gr.Textbox(label="Trạng thái", lines=2)

                def _refresh_voices():
                    return gr.update(choices=get_saved_voices())
                vt_refresh_btn.click(_refresh_voices, inputs=[], outputs=[vt_profile])

                def _train_fn(
                    text, profile_name, lang, instruct, ns, gs, dn, sp, du, pp, po
                ):
                    ref_aud, ref_text = load_voice_profile(profile_name)
                    if not ref_aud:
                        return None, "Không tìm thấy giọng nói đã chọn. Vui lòng lưu một giọng mới ở tab 'Sao chép giọng nói'."
                    return _gen(
                        text, lang, ref_aud, instruct, ns, gs, dn, sp, du, pp, po,
                        mode="clone", ref_text=ref_text or None,
                    )

                vt_btn.click(
                    _train_fn,
                    inputs=[
                        vt_text, vt_profile, vt_lang, vt_instruct,
                        vt_ns, vt_gs, vt_dn, vt_sp, vt_du, vt_pp, vt_po,
                    ],
                    outputs=[vt_audio, vt_status],
                )

            # ==============================================================
            # Voice Design
            # ==============================================================
            with gr.TabItem("Thiết kế giọng nói"):
                with gr.Row():
                    with gr.Column(scale=1):
                        vd_text = gr.Textbox(
                            label="Văn bản cần tổng hợp",
                            lines=4,
                            placeholder="Nhập nội dung bạn muốn chuyển thành giọng nói...",
                        )
                        vd_lang = _lang_dropdown()

                        _AUTO = "Tự động"
                        vd_groups = []
                        for _cat, _choices in _CATEGORIES.items():
                            vd_groups.append(
                                gr.Dropdown(
                                    label=_cat,
                                    choices=[_AUTO] + _choices,
                                    value=_AUTO,
                                    info=_ATTR_INFO.get(_cat),
                                )
                            )

                        (
                            vd_ns,
                            vd_gs,
                            vd_dn,
                            vd_sp,
                            vd_du,
                            vd_pp,
                            vd_po,
                        ) = _gen_settings()
                        vd_btn = gr.Button("Bắt đầu tạo / Generate", variant="primary")
                    with gr.Column(scale=1):
                        vd_audio = gr.Audio(
                            label="Kết quả âm thanh",
                            type="numpy",
                        )
                        vd_status = gr.Textbox(label="Trạng thái", lines=2)

                def _build_instruct(groups):
                    """Extract instruct text from UI dropdowns.

                    Language unification and validation is handled by
                    _resolve_instruct inside _preprocess_all.
                    """
                    selected = [g for g in groups if g and g != "Tự động"]
                    if not selected:
                        return None
                    parts = []
                    for v in selected:
                        if " / " in v:
                            zh_en, en = v.split(" / ", 1)
                            # The model expects English keywords
                            parts.append(en.strip().lower())
                        else:
                            parts.append(v)
                    return ", ".join(parts)

                def _design_fn(text, lang, ns, gs, dn, sp, du, pp, po, *groups):
                    return _gen(
                        text,
                        lang,
                        None,
                        _build_instruct(groups),
                        ns,
                        gs,
                        dn,
                        sp,
                        du,
                        pp,
                        po,
                        mode="design",
                    )

                vd_btn.click(
                    _design_fn,
                    inputs=[
                        vd_text,
                        vd_lang,
                        vd_ns,
                        vd_gs,
                        vd_dn,
                        vd_sp,
                        vd_du,
                        vd_pp,
                        vd_po,
                    ]
                    + vd_groups,
                    outputs=[vd_audio, vd_status],
                )

    return demo


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args(argv)

    device = args.device or get_best_device()

    checkpoint = args.model
    if not checkpoint:
        parser.print_help()
        return 0
    logging.info(f"Loading model from {checkpoint}, device={device} ...")
    model = GHVoice.from_pretrained(
        checkpoint,
        device_map=device,
        dtype=torch.float16,
        load_asr=not args.no_asr,
    )
    print("Model loaded.")

    demo = build_demo(model, checkpoint)

    demo.queue().launch(
        server_name=args.ip,
        server_port=args.port,
        share=args.share,
        root_path=args.root_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
