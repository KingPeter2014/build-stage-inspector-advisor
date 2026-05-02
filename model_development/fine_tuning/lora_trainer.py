"""
model_development/fine_tuning/lora_trainer.py
LoRA / QLoRA fine-tuning using HuggingFace PEFT + TRL.
Run this as a standalone script or call from a pipeline orchestrator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from datasets import load_dataset, Dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import SFTTrainer


@dataclass
class LoRATrainingConfig:
    base_model: str = "meta-llama/Llama-3.2-3B-Instruct"
    dataset_path: str = "data/fine_tuning/train.jsonl"
    output_dir: str = "artifacts/fine_tuned"

    # LoRA hyperparameters
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: ["q_proj", "v_proj"])

    # Training hyperparameters
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    max_seq_length: int = 2048
    use_4bit_quantisation: bool = True

    # Logging
    logging_steps: int = 10
    save_steps: int = 100
    mlflow_tracking_uri: str = "http://localhost:5000"


def train(cfg: LoRATrainingConfig) -> str:
    """Run LoRA fine-tuning and return path to saved adapter."""
    import mlflow
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)

    # --- Quantisation config (QLoRA) ---
    bnb_config = None
    if cfg.use_4bit_quantisation:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype="bfloat16",
        )

    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        cfg.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    # --- LoRA config ---
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=cfg.lora_dropout,
        target_modules=cfg.target_modules,
        bias="none",
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # --- Dataset ---
    dataset = load_dataset("json", data_files=cfg.dataset_path, split="train")

    training_args = TrainingArguments(
        output_dir=cfg.output_dir,
        num_train_epochs=cfg.num_train_epochs,
        per_device_train_batch_size=cfg.per_device_train_batch_size,
        gradient_accumulation_steps=cfg.gradient_accumulation_steps,
        learning_rate=cfg.learning_rate,
        logging_steps=cfg.logging_steps,
        save_steps=cfg.save_steps,
        fp16=True,
        report_to="mlflow",
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
        max_seq_length=cfg.max_seq_length,
        dataset_text_field="text",
        peft_config=peft_config,
    )

    with mlflow.start_run():
        mlflow.log_params(cfg.__dict__)
        trainer.train()
        trainer.save_model(cfg.output_dir)

    return cfg.output_dir


if __name__ == "__main__":
    cfg = LoRATrainingConfig()
    output = train(cfg)
    print(f"Adapter saved to: {output}")
