import argparse
from .config import Settings
def main():
    p=argparse.ArgumentParser(); p.add_argument("--check-hardware",action="store_true"); p.add_argument("--download-model",action="store_true"); a=p.parse_args(); s=Settings()
    if not s.model_is_allowed: raise SystemExit("Phase 1 only permits Denali-AI/qwen3-vl-2b-sft-grpo-v9")
    if a.check_hardware:
        try:
            import torch; print({"torch":torch.__version__,"cuda":torch.cuda.is_available(),"gpu":torch.cuda.get_device_name(0) if torch.cuda.is_available() else None})
        except ImportError: print("PyTorch is not installed. Install the requirements first.")
        return
    if a.download_model:
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        AutoProcessor.from_pretrained(s.model_id, revision=s.model_revision); Qwen3VLForConditionalGeneration.from_pretrained(s.model_id, revision=s.model_revision)
        from .db import Database
        Database(s.db_path).set_model_status("qwen3-vl-2b", "installed"); print(f"Downloaded only {s.model_id}"); return
    import uvicorn; uvicorn.run("wardrobe_backend.api:app",host=s.host,port=s.port,reload=False)
if __name__ == "__main__": main()
