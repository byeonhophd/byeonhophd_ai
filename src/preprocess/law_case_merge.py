import os
import json
import argparse
from tqdm import tqdm

def merge_law_case(args):
    # Load all law_case data
    law_case_dir = os.path.join('data', 'case_xml', 'case_details_postprocessed')
    law_case_list = os.listdir(law_case_dir)

    # Merge all law_case data
    law_case_data = []
    for law_case in tqdm(law_case_list):
        with open(os.path.join(law_case_dir, law_case), 'r') as f:
            law_case_data.append(json.load(f))
    
    for case in law_case_data:
        case["content"] = case["content"].replace("   ", " ")

    with open(os.path.join(args.save_dir, 'law_case_processed.json'), 'w') as f:
        json.dump(law_case_data, f, indent=4, ensure_ascii=False)
    
    print('Merged law_case data saved at {}'.format(os.path.join(args.save_dir, 'law_case_processed.json')))
    

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--save_dir', type=str, default='data/case_xml')
    return parser.parse_args()
    
if __name__ == "__main__":
    args = parse_args()
    merge_law_case(args)