import argparse
import os
import re
import json
import time
import pandas as pd

from tqdm import tqdm, trange
from urllib.request import urlopen
import xml.etree.ElementTree as ET


def check_total_count(url_link):
    """
    Checks the total number of law list.
    """
    response = urlopen(url_link).read()
    xtree = ET.fromstring(response)

    return int(xtree.find('totalCnt').text)


def crawl_case_list(url_link, page_num):
    """
    Crawls the law list and returns a list of law information.
    """
    response = urlopen(url_link).read()
    # save response
    os.makedirs(os.path.join(args.data_dir, 'case_list_raw'), exist_ok=True)
    with open(os.path.join(args.data_dir, 'case_list_raw', f'case_list_{page_num}.xml'), 'wb') as f:
        f.write(response)
    xtree = ET.fromstring(response)
    
    try:
        items = xtree[8:]
    except IndexError:
        raise Exception("No items in the list")
    
    field_names = [
        '판례일련번호', '사건명', '사건번호', '선고일자', '법원명',
        '사건종류명', '사건종류코드', '판결유형', '선고', '판례상세링크'
    ]
    
    law_list = [
        {field: (node.find(field).text if node.find(field) is not None else None) for field in field_names}
        for node in items
    ]
    
    return law_list


def split_numbered_items(text):
    """
    번호가 매겨진 항목을 분리하여 리스트로 반환합니다.
    누락된 번호가 있는 경우 해당 위치에 None을 삽입합니다.
    
    예시:
        입력: "[1] 항목1 [3] 항목3"
        출력: ["항목1", None, "항목3"]
    """
    if not text:
        return []
    
    # 번호와 내용을 추출하는 정규 표현식
    pattern = re.compile(r'\[(\d+)\]\s*(.*?)(?=\[\d+\]|$)', re.DOTALL)
    matches = pattern.findall(text)
    
    if not matches:
        return [text.strip()] if text.strip() else []
    
    # 최대 번호 찾기
    max_num = max(int(num) for num, _ in matches)
    items = [""] * max_num  # 초기 리스트 생성
    
    for num, content in matches:
        index = int(num) - 1  # 리스트는 0부터 인덱스 시작
        items[index] = content.strip() if content.strip() else None
    
    return items


def crawl_case_detail(url_link, info, args):
    # 판례 상세 raw 데이터 경로 설정
    raw_dir = os.path.join(args.data_dir, 'case_details_raw')
    os.makedirs(raw_dir, exist_ok=True)
    raw_file_path = os.path.join(raw_dir, f'case_text_{info["판례일련번호"]}.xml')
    
    if os.path.exists(raw_file_path):
        with open(raw_file_path, 'rb') as f:
            response = f.read()
    else:
        try:
            response = urlopen(url_link).read()
            with open(raw_file_path, 'wb') as f:
                f.write(response)
        except Exception as e:
            print(f"Error downloading URL '{url_link}': {e}")
            return {}
    
    try:
        xtree = ET.fromstring(response)
    except ET.ParseError as e:
        print(f"Error parsing XML for '{url_link}': {e}")
        return {}
    
    panre_data = {}
    
    # 기본 정보 추출
    fields = ['판례정보일련번호', '사건명', '사건번호', '선고일자', '선고',
              '법원명', '법원종류코드', '사건종류명', '사건종류코드',
              '판결유형', '판시사항', '판결요지', '참조조문', '참조판례', '판례내용']
    
    for field in fields:
        try:
            element = xtree.find(field)
            if element is not None and element.text is not None:
                panre_data[field] = element.text
            else:
                panre_data[field] = None
        except Exception as e:
            print(f"Error parsing field '{field}': {e}")
            panre_data[field] = None
    
    for field in ['판시사항', '판결요지', '참조조문', '참조판례']:
        if field in panre_data:
            panre_data[field] = split_numbered_items(panre_data[field])
            # 배열 후처리
            panre_data[field] = [item.replace('<br/>', '\n').replace('<br>', '\n').replace('<br />', '\n').replace("\n", "").strip(" \n/")
                                    for item in panre_data[field] if item is not None]
    for field in ['판례내용']:
        # 먼저 <br/> 태그를 줄바꿈 문자로 대체
        text = panre_data[field].replace('<br/>', '\n').replace('<br>', '\n').replace('<br />', '\n')

        # 정규 표현식을 사용하여 【키】와 그에 해당하는 값을 추출
        pattern = re.compile(r'【(.*?)】\s*(.*?)(?=【|$)', re.DOTALL)
        matches = pattern.findall(text)

        case_data = {}
        for key, value in matches:
            key = key.strip().replace(' ', '')
            value = value.strip()
            case_data[key] = value
        
        panre_data[field] = case_data
    
    return panre_data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Retrieve case information.')
    parser.add_argument('--id', required=True, help='API Key ID')
    parser.add_argument('--base', default='https://www.law.go.kr', help='Base URL')
    parser.add_argument('--data_dir', default='data/case_xml', help='Data directory')
    args = parser.parse_args()

    total_count = check_total_count(f"{args.base}/DRF/lawSearch.do?OC={args.id}&target=prec&type=XML&display=100&page=1")

    # check if law_list.csv exists
    try:
        case_list_df = pd.read_csv(os.path.join(args.data_dir, 'case_list.csv'))
        print("Loaded law_list.csv")
    except FileNotFoundError:
        law_list = []
        for page in trange(1, total_count // 100 + 2):
            url_link = f"{args.base}/DRF/lawSearch.do?OC={args.id}&target=prec&type=XML&display=100&page={page}"
            law_list.extend(crawl_case_list(url_link, page))
        # save law_list
        case_list_df = pd.DataFrame(law_list)
        case_list_df.to_csv(os.path.join(args.data_dir, 'case_list.csv'), index=False)
    
    # check if law_detail.json exists
    for idx, row in tqdm(case_list_df.iterrows(), total=case_list_df.shape[0]):
        max_retries = 5
        retry_count = 0
        while retry_count < max_retries:
            try:
                xml_url = f"{args.base}{row['판례상세링크'].replace('HTML', 'XML')}"
                processed_case_detail = crawl_case_detail(xml_url, row, args)
                # save law_detail
                os.makedirs(os.path.join(args.data_dir, 'case_details'), exist_ok=True)
                with open(os.path.join(args.data_dir, 'case_details', f'case_detail_{row["판례일련번호"]}.json'), 'w') as f:
                    json.dump(processed_case_detail, f, ensure_ascii=False, indent=4)
                break
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"Failed after {max_retries} retries: {e}")
                    break
                time.sleep(5)