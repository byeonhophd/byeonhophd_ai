import os
import argparse
from optimum.rbln import RBLNXLMRobertaModel

def parse_arguments():
    """
    Parse the command line arguments
    """
    parser = argparse.ArgumentParser(description="Compile and export RBLN XLM Roberta model")

    parser.add_argument(
        "--model_id",
        type=str,
        choices=["BAAI/bge-m3", "dragonkue/BGE-m3-ko"],
        default="dragonkue/BGE-m3-ko",
        help="(str) Model identifier.",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=1,
        help="(int) Batch size for model export, default: 1",
    )
    parser.add_argument(
        "--max_seq_len",
        type=int,
        default=8192,
        help="(int) Maximum sequence length for model export, default: 8192",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="models",
        help="(str) Directory to save the compiled model, default: 'models'",
    )
    return parser.parse_args()

def main():
    args = parse_arguments()
    model_id = args.model_id

    # Constructing the output directory name
    model_save_dir = os.path.join(
        args.output_dir,
        f"rbln_{os.path.basename(model_id)}"
        f"_batch{args.batch_size}"
        f"_max{args.max_seq_len}",
    )
    print(f"Saving compiled model to {model_save_dir}")
    os.makedirs(model_save_dir, exist_ok=True)

    # Compile and export
    print(f"Loading model: {model_id}")
    model = RBLNXLMRobertaModel.from_pretrained(
        model_id=model_id,
        export=True,  # Export a PyTorch model to RBLN model with Optimum
        rbln_batch_size=args.batch_size,
        rbln_max_seq_len=args.max_seq_len,
    )

    # Save compiled results to disk
    print(f"Saving compiled model to {model_save_dir}")
    model.save_pretrained(model_save_dir)

if __name__ == "__main__":
    main()