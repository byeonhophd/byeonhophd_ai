import os
import argparse
from optimum.rbln import RBLNLlamaForCausalLM


def parsing_argument():
    """
    Parse the command line arguments
    """
    parser = argparse.ArgumentParser(description="Compile and export RBLN Llama model")

    parser.add_argument(
        "--model_name",
        type=str,
        choices=["EEVE-Korean-Instruct-10.8B-v1.0"],
        default="EEVE-Korean-Instruct-10.8B-v1.0",
        help="(str) model type, eeve model name.",
    )
    parser.add_argument(
        "--tensor_parallel_size",
        type=int,
        default=8,
        help="(int) set tensor parallel size in eeve model, default: 8",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=1,
        help="(int) batch size for model export, default: 1",
    )
    parser.add_argument(
        "--max_seq_len",
        type=int,
        default=4096,
        help="(int) maximum sequence length for model export, default: 4096",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="models",
        help="(str) directory to save the compiled model, default: 'models'",
    )
    return parser.parse_args()


def main():
    args = parsing_argument()
    model_id = f"yanolja/{args.model_name}"

    # Constructing the output directory name
    model_save_dir = os.path.join(
        args.output_dir,
        f"rbln_vllm_{os.path.basename(model_id)}"
        f"_npu{args.tensor_parallel_size}"
        f"_batch{args.batch_size}"
        f"_max{args.max_seq_len}",
    )
    print(f"Saving compiled model to {model_save_dir}")
    os.makedirs(model_save_dir, exist_ok=True)

    # Compile and export
    print(f"Loading model: {model_id}")
    model = RBLNLlamaForCausalLM.from_pretrained(
        model_id=model_id,
        export=True,  # export a PyTorch model to RBLN model with optimum
        rbln_batch_size=args.batch_size,
        rbln_max_seq_len=args.max_seq_len,
        rbln_tensor_parallel_size=args.tensor_parallel_size,
    )

    # Save compiled results to disk
    print(f"Saving compiled model to {model_save_dir}")
    model.save_pretrained(model_save_dir)


if __name__ == "__main__":
    main()