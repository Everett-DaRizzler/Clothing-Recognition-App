import json, re, time
from pathlib import Path
from ..prompt import ANALYSIS_PROMPT
from ..schema import ClothingAnalysis
from .base import ClothingAnalyzer

class StyleWell4BAnalyzer(ClothingAnalyzer):
    model_id = "stylewell-4b"
    def __init__(self, model_name: str, revision: str = "main", device: str = "auto", max_image_pixels: int | None = None):
        self.model_name, self.revision, self.device, self._model, self._processor = model_name, revision, device, None, None
        self.max_image_pixels = max_image_pixels
    def _load(self):
        if self._model is not None: return
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        processor_options = {"min_pixels": 65536, "max_pixels": self.max_image_pixels} if self.max_image_pixels is not None else {}
        self._processor = AutoProcessor.from_pretrained(self.model_name, revision=self.revision, **processor_options)
        self._model = Qwen3VLForConditionalGeneration.from_pretrained(self.model_name, revision=self.revision, dtype="auto", device_map=self.device).eval()
    def is_cached(self):
        from huggingface_hub import try_to_load_from_cache
        return isinstance(try_to_load_from_cache(self.model_name, "config.json", revision=self.revision), str)
    def analyze(self, image_path: Path, image_id: str) -> ClothingAnalysis:
        self._load(); started=time.perf_counter(); from PIL import Image; image=Image.open(image_path).convert("RGB")
        messages=[{"role":"user","content":[{"type":"image","image":image},{"type":"text","text":ANALYSIS_PROMPT}]}]
        inputs=self._processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt").to(self._model.device)
        import torch
        with torch.inference_mode(): generated=self._model.generate(**inputs, max_new_tokens=512)
        trimmed=[out_ids[len(in_ids):] for in_ids,out_ids in zip(inputs.input_ids,generated)]; raw=self._processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
        parsed=self._parse(raw); parsed.update(imageId=image_id,modelId=self.model_id,modelVersion=self.model_name,rawResponse=raw,inferenceTimeMs=round((time.perf_counter()-started)*1000)); return ClothingAnalysis.model_validate(parsed)
    def _parse(self, raw):
        match=re.search(r"\{.*\}",raw,re.S)
        if not match: return {"parseSuccess":False}
        try:
            data=json.loads(match.group(0)); required={"category","type","color","pattern","fabric","fit","occasion","season"}
            if not isinstance(data,dict) or not required.issubset(data): return {"parseSuccess":False}
            for key in ("style","occasion","season"):
                if data.get(key) is None: data[key]=[]
                elif not isinstance(data[key],list): data[key]=[data[key]]
            for key in ("category","type","color","pattern","fabric","fit"):
                if isinstance(data.get(key), list): data[key]=data[key][0] if data[key] else None
            if isinstance(data.get("confidence"), (int,float)):
                data["confidence"]={key: data["confidence"] for key in ("category","type","color","pattern","fabric","fit","style","occasion","season")}
            return {**data,"parseSuccess":True}
        except json.JSONDecodeError: return {"parseSuccess":False}
