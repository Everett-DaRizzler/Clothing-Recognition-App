import json, re, time
from pathlib import Path
from ..prompt import ANALYSIS_PROMPT
from ..schema import ClothingAnalysis
from .base import ClothingAnalyzer
class Qwen3VL2BAnalyzer(ClothingAnalyzer):
    model_id = "qwen3-vl-2b"
    def __init__(self, model_name: str, revision: str = "main", device: str = "auto"): self.model_name, self.revision, self.device, self._model, self._processor = model_name, revision, device, None, None
    def _load(self):
        if self._model is not None: return
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        import torch
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        self._processor = AutoProcessor.from_pretrained(self.model_name, revision=self.revision)
        self._model = Qwen3VLForConditionalGeneration.from_pretrained(self.model_name, revision=self.revision, torch_dtype=dtype, device_map=self.device)
    def analyze(self, image_path: Path, image_id: str) -> ClothingAnalysis:
        self._load(); started=time.perf_counter(); from PIL import Image; image=Image.open(image_path).convert("RGB")
        messages=[{"role":"user","content":[{"type":"image","image":image},{"type":"text","text":ANALYSIS_PROMPT}]}]; text=self._processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs=self._processor(text=[text], images=[image], padding=True, return_tensors="pt").to(self._model.device); output=self._model.generate(**inputs, max_new_tokens=512); raw=self._processor.batch_decode(output[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]
        parsed=self._parse(raw); parsed.update(imageId=image_id,modelId=self.model_id,modelVersion=self.model_name,rawResponse=raw,inferenceTimeMs=round((time.perf_counter()-started)*1000)); return ClothingAnalysis.model_validate(parsed)
    def _parse(self, raw):
        match=re.search(r"\{.*\}",raw,re.S)
        if not match: return {"parseSuccess":False}
        try:
            data=json.loads(match.group(0)); required={"category","type","color","secondaryColors","pattern","fabric","fit","style","occasion","season","confidence"}
            if not isinstance(data,dict) or not required.issubset(data): return {"parseSuccess":False}
            return {**data,"parseSuccess":True}
        except json.JSONDecodeError: return {"parseSuccess":False}
