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


def crawl_law_list(url_link, page_num):
    """
    Crawls the law list and returns a list of law information.
    """
    response = urlopen(url_link).read()
    # save response
    os.makedirs(os.path.join(args.data_dir, 'law_list_raw'), exist_ok=True)
    with open(os.path.join(args.data_dir, 'law_list_raw', f'law_list_{page_num}.xml'), 'wb') as f:
        f.write(response)
    xtree = ET.fromstring(response)
    
    try:
        items = xtree[8:]
    except IndexError:
        raise Exception("No items in the list")
    
    field_names = [
        '법령일련번호', '현행연혁코드', '법령명한글', '법령약칭명', '법령ID',
        '공포일자', '공포번호', '제개정구분명', '소관부처코드', '소관부처명',
        '법령구분명', '공동부령정보', '시행일자', '자법타법여부', '법령상세링크'
    ]
    
    law_list = [
        {field: (node.find(field).text if node.find(field) is not None else None) for field in field_names}
        for node in items
    ]
    
    return law_list


def remove_empty_arrays(data):
    """
    Recursively remove empty lists and dictionaries from the data.
    """
    if isinstance(data, dict):
        return {k: remove_empty_arrays(v) for k, v in data.items() if v is not None and v != []}
    elif isinstance(data, list):
        return [remove_empty_arrays(item) for item in data if item is not None]
    else:
        return data

def parse_jomun_number(jomun_content):
    """
    Parses 조문번호 from '제1조' to '1',
    and from '제1조의2' to '1_2'.
    If it doesn't match the pattern, returns as is.
    """
    if jomun_content is None:
        return None
    match = re.match(r"제(\d+)조(?:의(\d+))?", jomun_content)
    if match:
        main_num = match.group(1)
        sub_num = match.group(2)
        if sub_num:
            return f"{main_num}_{sub_num}"
        else:
            return main_num
    return None  # Return None if it doesn't match the pattern

def clean_jomun_content(content):
    """
    Replaces '\\n\\t' with space and removes duplicate spaces.
    """
    if content is None:
        return None
    # Replace \n\t with space
    content = content.replace('\n\t', ' ')
    # Remove duplicate spaces using regex
    content = re.sub(r'\s+', ' ', content)
    # Strip leading and trailing spaces
    return content.strip()

def extract_jomun_number_from_content(content):
    """
    Extracts 조문번호 from 조문내용.
    """
    if content is None:
        return None
    match = re.match(r"제(\d+)조(?:의(\d+))?", content)
    if match:
        main_num = match.group(1)
        sub_num = match.group(2)
        if sub_num:
            return f"{main_num}_{sub_num}"
        else:
            return main_num
    return None


def process_jo(content):
    # 정규식으로 "제숫자(내용)" 패턴 추출 및 제거
    pattern = r"제\d+(조의?\d*|조)?\(.*?\)"  # "제숫자조의[숫자](내용)" 형태
    # extracted = re.findall(pattern, content)  # 추출
    modified_text = re.sub(pattern, '', content).strip()  # 제거 후 텍스트 정리

    return modified_text


def crawl_law_detail(url_link, info, args):
    """
    Crawls the law detail page and returns a dictionary of law information.
    """
    # law_details_raw 경로에 이미 있는지 확인
    if os.path.exists(os.path.join(args.data_dir, 'law_details_raw', f'law_text_{info["법령ID"]}.xml')):
        with open(os.path.join(args.data_dir, 'law_details_raw', f'law_text_{info["법령ID"]}.xml'), 'rb') as f:
            response = f.read()
    else:
        response = urlopen(url_link).read()
    xtree = ET.fromstring(response)

    os.makedirs(os.path.join(args.data_dir, 'law_details_raw'), exist_ok=True)
    with open(os.path.join(args.data_dir, 'law_details_raw', f'law_text_{info["법령ID"]}.xml'), 'wb') as f:
        f.write(response)

    law_data = {}

    # 기본 정보
    for field in ["법령ID", "공포일자", "공포번호", "언어", "법종구분", "법종구분코드",
                  "법령명_한글", "법령명_한자", "법령명약칭", "제명변경여부", "한글법령여부",
                  "편장절관", "소관부처코드", "소관부처", "전화번호", "시행일자", "제개정구분",
                  "별표편집여부", "공포법령여부", "공동부령정보"]:
        try:
            element = xtree.find("기본정보").find(field)
            if element is not None:
                law_data[field] = element.text
        except Exception as e:
            print(f"Error parsing 기본정보 field '{field}': {e}")

    # 조문단위, 항, 호 처리
    law_data['조문'] = []
    조문단위 = xtree.find("조문").findall("조문단위")
    for jomun in 조문단위:
        # 먼저 조문내용에서 조문번호 추출
        jomun_content_raw = jomun.find("조문내용").text if jomun.find("조문내용") is not None else None
        jomun_number = extract_jomun_number_from_content(jomun_content_raw)

        # Fallback: If extraction fails, use 조문번호 필드
        if not jomun_number:
            jomun_number_raw = jomun.find("조문번호").text if jomun.find("조문번호") is not None else None
            jomun_number = parse_jomun_number(jomun_number_raw)

        # If still not found, set as None or handle accordingly
        if not jomun_number:
            jomun_number = "Unknown"

        jomun_data = {
            "조문번호": jomun_number,
            "조문여부": jomun.find("조문여부").text if jomun.find("조문여부") is not None else None,
            "조문제목": jomun.find("조문제목").text if jomun.find("조문제목") is not None else None,
            "조문시행일자": jomun.find("조문시행일자").text if jomun.find("조문시행일자") is not None else None,
            "조문변경여부": jomun.find("조문변경여부").text if jomun.find("조문변경여부") is not None else None,
            "조문내용": process_jo(clean_jomun_content(jomun_content_raw)) if clean_jomun_content(jomun_content_raw) else None
        }

        # 조문제개정유형, 조문이동이전, 조문이동이후 등 추가 필드 처리
        for field in ["조문제개정유형", "조문이동이전", "조문이동이후"]:
            jomun_data[field] = jomun.find(field).text if jomun.find(field) is not None else None

        # 항 처리
        jomun_data['항'] = []
        for hang in jomun.findall("항"):
            hang_content_raw = hang.find("항내용").text if hang.find("항내용") is not None else None
            hang_data = {
                "항번호": hang.find("항번호").text if hang.find("항번호") is not None else None,
                "항제개정유형": hang.find("항제개정유형").text if hang.find("항제개정유형") is not None else None,
                "항내용": clean_jomun_content(hang_content_raw).strip(hang.find("항번호").text+" " if hang.find("항번호") is not None else " ")
                    if clean_jomun_content(hang_content_raw) else None
            }

            # 호 처리
            hang_data['호'] = []
            for ho in hang.findall("호"):
                ho_content_raw = ho.find("호내용").text if ho.find("호내용") is not None else None
                ho_data = {
                    "호번호": ho.find("호번호").text.rstrip(".") if ho.find("호번호") is not None else None,
                    "호내용": clean_jomun_content(ho_content_raw).strip(ho.find("호번호").text+" " if ho.find("호번호") is not None else " ")
                        if clean_jomun_content(ho_content_raw) else None
                }

                # 목 처리
                ho_data['목'] = []
                for mok in ho.findall("목"):
                    mok_content_raw = mok.find("목내용").text if mok.find("목내용") is not None else None
                    mok_data = {
                        "목번호": mok.find("목번호").text.rstrip(".") if mok.find("목번호") is not None else None,
                        "목내용": clean_jomun_content(mok_content_raw).strip(mok.find("목번호").text+" " if mok.find("목번호") is not None else " ")
                            if clean_jomun_content(mok_content_raw) else None
                    }
                    ho_data['목'].append(mok_data)

                hang_data['호'].append(ho_data)

            jomun_data['항'].append(hang_data)

        law_data['조문'].append(jomun_data)

    # 부칙 정보
    law_data['부칙'] = []
    try:
        for appendix in xtree.find("부칙").findall("부칙단위"):
            appendix_data = {
                field: appendix.find(field).text if appendix.find(field) is not None else None
                for field in ["부칙공포일자", "부칙공포번호", "부칙내용"]
            }
            # Clean 부칙내용
            appendix_data['부칙내용'] = clean_jomun_content(appendix_data.get('부칙내용'))
            law_data['부칙'].append(appendix_data)
    except Exception as e:
        print(f"Error parsing 부칙: {e}")

    # 개정문 내용
    try:
        개정문내용 = xtree.find("개정문").find("개정문내용").text
        law_data['개정문'] = clean_jomun_content(개정문내용)
    except Exception as e:
        print(f"Error parsing 개정문: {e}")

    # 개정이유 내용
    try:
        개정이유내용 = xtree.find("제개정이유").find("제개정이유내용").text
        law_data['제개정이유'] = clean_jomun_content(개정이유내용)
    except Exception as e:
        print(f"Error parsing 제개정이유: {e}")

    law_data = remove_empty_arrays(law_data)

    return law_data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Retrieve law information.')
    parser.add_argument('--id', required=True, help='API Key ID')
    parser.add_argument('--base', default='https://www.law.go.kr', help='Base URL')
    parser.add_argument('--data_dir', default='data/jomun_xml', help='Data directory')
    args = parser.parse_args()

    total_count = check_total_count(f"{args.base}/DRF/lawSearch.do?OC={args.id}&target=law&type=XML&display=100&page=1")

    # check if law_list.csv exists
    try:
        law_list_df = pd.read_csv(os.path.join(args.data_dir, 'law_list.csv'))
        print("Loaded law_list.csv")
    except FileNotFoundError:
        law_list = []
        for page in trange(1, total_count // 100 + 2):
            url_link = f"{args.base}/DRF/lawSearch.do?OC={args.id}&target=law&type=XML&display=100&page={page}"
            law_list.extend(crawl_law_list(url_link, page))
        # save law_list
        law_list_df = pd.DataFrame(law_list)
        law_list_df.to_csv(os.path.join(args.data_dir, 'law_list.csv'), index=False)
    
    # check if law_detail.json exists
    for idx, row in tqdm(law_list_df.iterrows(), total=law_list_df.shape[0]):
        max_retries = 5
        retry_count = 0
        while retry_count < max_retries:
            try:
                xml_url = f"{args.base}{row['법령상세링크'].replace('HTML', 'XML')}"
                processed_law_detail = crawl_law_detail(xml_url, row, args)
                # save law_detail
                os.makedirs(os.path.join(args.data_dir, 'law_details'), exist_ok=True)
                with open(os.path.join(args.data_dir, 'law_details', f'law_detail_{row["법령ID"]}.json'), 'w') as f:
                    json.dump(processed_law_detail, f, ensure_ascii=False, indent=4)
                break
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"Failed after {max_retries} retries: {e}")
                    break
                time.sleep(5)

