import os
import json
from tqdm import tqdm

def process_law_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    law_name = data.get('법령명_한글', '')
    articles_list = data.get('조문', [])
    original_result = {}
    filtered_result = {}
    for article in articles_list:
        orig, filt = process_article(article, law_name, [], '')
        original_result.update(orig)
        filtered_result.update(filt)
    return original_result, filtered_result

def process_article(article_data, law_name, hierarchy, cumulative_text):
    original = {}
    filtered = {}
    article_number = article_data.get('조문번호', '')
    article_title = article_data.get('조문제목', '')
    article_content = article_data.get('조문내용', '')
    paragraphs = article_data.get('항', [])
    items = article_data.get('호', [])

    # 조문번호가 'Unknown'인 경우(예: 장, 절 제목)은 건너뜀
    if article_number == 'Unknown':
        return original, filtered

    article_num_str = format_article_number(article_number)
    # 계층 업데이트
    if isinstance(article_num_str, list):
        new_hierarchy = hierarchy + [f'제{article_num_str[0]}조의{article_num_str[1]}']
    else:
        new_hierarchy = hierarchy + [f'제{article_num_str}조']
    key = f'{law_name} {" ".join(new_hierarchy)}'

    # 누적 텍스트 업데이트: 조문 제목과 내용 포함
    current_text = ''
    if article_title:
        current_text += f'{article_title} '
    if article_content:
        current_text += f'{article_content} '

    cumulative_text_article = cumulative_text + current_text + '\t'

    # 조문의 내용만 포함
    if current_text.strip():
        original[key] = current_text.strip()
        # 필터링: 조문이 온점으로 끝나는지 확인
        if current_text.strip().endswith('.'):
            filtered[key] = current_text.strip()

    # 항이 있는 경우 처리
    if paragraphs:
        orig_paras, filt_paras = process_paragraphs(paragraphs, law_name, new_hierarchy, cumulative_text_article)
        original.update(orig_paras)
        filtered.update(filt_paras)
    elif items:
        # 항이 없고 호만 있는 경우 처리
        cumulative_text_items = cumulative_text_article
        orig_items, filt_items = process_items(items, law_name, new_hierarchy, cumulative_text_items)
        original.update(orig_items)
        filtered.update(filt_items)

    return original, filtered

def process_paragraphs(paragraphs, law_name, hierarchy, cumulative_text):
    original = {}
    filtered = {}
    for idx, paragraph in enumerate(paragraphs):
        paragraph_number = paragraph.get('항번호')
        paragraph_content = paragraph.get('항내용', '')
        items = paragraph.get('호', [])

        # 계층 업데이트
        if paragraph_number is not None:
            para_num_str = format_paragraph_number(paragraph_number)
            new_hierarchy = hierarchy + [f'제{para_num_str}항']
        else:
            new_hierarchy = hierarchy

        key = f'{law_name} {" ".join(new_hierarchy)}'

        # 필터링: 항 내용이 '삭제'로 시작하는지 확인
        if paragraph_content.strip().startswith('삭제'):
            continue  # 이 항을 결과에 추가하지 않음

        # 누적 텍스트 업데이트: 조문 + 항 내용
        if paragraph_content:
            current_text = cumulative_text + paragraph_content + '\t'
        else:
            current_text = cumulative_text + '\t'

        # 항의 내용만 포함
        if current_text.strip():
            original[key] = current_text.strip()
            filtered[key] = current_text.strip()

        # 호가 있는 경우 호 내용 추가 및 처리
        if items:
            orig_items, filt_items = process_items(items, law_name, new_hierarchy, current_text)
            original.update(orig_items)
            filtered.update(filt_items)

    return original, filtered

def process_items(items, law_name, hierarchy, cumulative_text):
    original = {}
    filtered = {}
    for item in items:
        item_number = item.get('호번호')
        item_content = item.get('호내용', '')
        sub_items = item.get('목', [])

        # 계층 업데이트
        item_num_str = format_item_number(item_number)
        new_hierarchy = hierarchy + [f'제{item_num_str}호']
        key = f'{law_name} {" ".join(new_hierarchy)}'

        # 필터링: 호 내용이 '삭제'로 시작하는지 확인
        if item_content.strip().startswith('삭제'):
            continue  # 이 호를 결과에 추가하지 않음

        # 누적 텍스트 업데이트: 조문 + 항 + 호 내용
        current_text = cumulative_text + item_content + '\t'

        # 항의 내용만 포함
        if current_text.strip():
            # If there are sub-items, append their content
            if sub_items:
                sub_content = process_sub_items_text(sub_items)
                # 필터링: sub_content에 '삭제'로 시작하는 항목이 포함되어 있는지 확인
                # 이미 process_sub_items_text에서 '삭제'로 시작하는 항목은 제외했으므로 추가할 필요 없음
                current_text += sub_content + '\t'

            original[key] = current_text.strip()
            filtered[key] = current_text.strip()

    return original, filtered

def process_sub_items_text(sub_items):
    texts = []
    for sub_item in sub_items:
        sub_item_content = sub_item.get('목내용', '')
        # 필터링: sub-item 내용이 '삭제'로 시작하는지 확인
        if sub_item_content.strip().startswith('삭제'):
            continue  # 이 sub-item을 결과에 추가하지 않음
        texts.append(sub_item_content)
        # If there are further nested sub-items, process them recursively
        nested_sub_items = sub_item.get('목', [])
        if nested_sub_items:
            nested_text = process_sub_items_text(nested_sub_items)
            if nested_text:
                texts.append(nested_text)
    return '\t'.join(texts)

def format_article_number(article_number):
    if '_' in article_number:
        return article_number.split('_')
    return article_number

def format_paragraph_number(paragraph_number):
    # 한글 숫자에서 아라비아 숫자로 변환
    mapping = {
        '①': '1', '②': '2', '③': '3', '④': '4', '⑤': '5',
        '⑥': '6', '⑦': '7', '⑧': '8', '⑨': '9', '⑩': '10',
        '⑪': '11', '⑫': '12', '⑬': '13', '⑭': '14', '⑮': '15',
        '⑯': '16', '⑰': '17', '⑱': '18', '⑲': '19', '⑳': '20',
    }
    return mapping.get(paragraph_number, paragraph_number)

def format_item_number(item_number):
    return item_number

def main():
    # 'law_detail_'로 시작하는 모든 json 파일 가져오기
    law_details_path = os.path.join('data', 'jomun_xml', 'law_details')
    if not os.path.exists(law_details_path):
        print(f"경로가 존재하지 않습니다: {law_details_path}")
        return

    json_files = [
        os.path.join(law_details_path, f)
        for f in os.listdir(law_details_path)
        if f.startswith('law_detail_') and f.endswith('.json')
    ]

    if not json_files:
        print("처리할 JSON 파일이 없습니다.")
        return

    all_results_original = {}
    all_results_filtered = {}
    for json_file in tqdm(json_files, desc="Processing JSON files"):
        try:
            orig, filt = process_law_file(json_file)
            all_results_original.update(orig)
            all_results_filtered.update(filt)
        except Exception as e:
            print(f"파일 처리 중 오류 발생 ({json_file}): {e}")

    for key, item in all_results_original.items():
        # \t 여러 개를 하나로 대체
        all_results_original[key] = item.replace('\t\t', '\t')
    for key, item in all_results_filtered.items():
        # \t 여러 개를 하나로 대체
        all_results_filtered[key] = item.replace('\t\t', '\t')

    # 결과를 파일로 저장
    output_path_original = os.path.join('data', 'law_articles_processed.json')
    output_path_filtered = os.path.join('data', 'law_articles_processed_filtered.json')
    os.makedirs(os.path.dirname(output_path_original), exist_ok=True)
    os.makedirs(os.path.dirname(output_path_filtered), exist_ok=True)
    with open(output_path_original, 'w', encoding='utf-8') as f:
        json.dump(all_results_original, f, ensure_ascii=False, indent=4)
    with open(output_path_filtered, 'w', encoding='utf-8') as f:
        json.dump(all_results_filtered, f, ensure_ascii=False, indent=4)
    print(f"처리 완료. 결과가 저장된 파일:")
    print(f" - 원본: {output_path_original}")
    print(f" - 필터링된 버전: {output_path_filtered}")

if __name__ == '__main__':
    main()