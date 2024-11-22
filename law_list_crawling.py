import argparse
import os
import re
import time
import json
import pandas as pd
from copy import deepcopy

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tqdm import tqdm, trange
from urllib.request import urlopen
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup


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


def parse_article_content(html_content, popup_text):
    """
    Parses the HTML content of articles and extracts article number, title, and content.
    Returns a dictionary with 'articles' as a list.
    """
    if isinstance(html_content, str):
        soup = BeautifulSoup(html_content, 'html.parser')
    else:
        soup = html_content

    article_data = {
        'articles': []
    }

    pty1_p4_tags = soup.find_all('p', class_='pty1_p4')

    for title_label in pty1_p4_tags:
        for sfon in title_label.find_all('span', class_='sfon'):
            sfon.extract()
        
        # 'a' 태그를 "[참조: 텍스트]" 형식으로 대체
        for a_tag in title_label.find_all('a'):
            replacement_text = f"[참조: {a_tag.get_text(strip=True)}]"
            a_tag.string = replacement_text

        bl_span = title_label.find('span', class_='bl')
        if bl_span:
            label = bl_span.get_text(strip=True)
            bl_span.extract()

            article_match = re.match(r'^제\s*(\d+)\s*조\s*(\(([^)]+)\))?', label)
            if article_match:
                article_number = article_match.group(1)
                article_title = article_match.group(3) if article_match.group(3) else ''
                article_full_name = label

                remaining_text = title_label.get_text().replace(label, '').strip()
                paragraph_match = re.match(r'^([①-⑳])\s*(.*)', remaining_text)
                paragraphs = []
                if paragraph_match:
                    paragraph_number = paragraph_match.group(1)
                    paragraph_text = paragraph_match.group(2)
                    current_paragraph = {
                        'paragraph_number': paragraph_number,
                        'paragraph_text': paragraph_text,
                        'items': [],
                        'sub_items': [],
                    }
                    paragraphs.append(current_paragraph)
                else:
                    paragraph_text = remaining_text
                    current_paragraph = {
                        'paragraph_number': None,
                        'paragraph_text': paragraph_text,
                        'items': [],
                        'sub_items': [],
                    }
                    paragraphs.append(current_paragraph)

                article_entry = {
                    'article_number': article_number,
                    'article_title': article_title,
                    'article_full_name': article_full_name,
                    'paragraphs': paragraphs,
                    'items': [],
                    'sub_items': [],
                }
                article_data['articles'].append(article_entry)
            else:
                continue
        else:
            input_tag = title_label.find('input', {'type': 'checkbox'})
            if input_tag:
                value = input_tag.get('value', '')
                value_parts = value.split(':')
                if len(value_parts) >= 3:
                    article_number = value_parts[0]  # '1', '2', etc.
                else:
                    article_number = ''

                input_tag.extract()
                remaining_text = title_label.get_text(strip=True)

                paragraph_number = None
                paragraph_text = remaining_text

                article_title = f'제{article_number}조'
                article_full_name = f'제{article_number}조'

                paragraph = {
                    'paragraph_number': paragraph_number,
                    'paragraph_text': paragraph_text,
                    'items': [],
                    'sub_items': [],
                }
                article_entry = {
                    'article_number': article_number,
                    'article_title': article_title,
                    'article_full_name': article_full_name,
                    'paragraphs': [paragraph],
                    'items': [],
                    'sub_items': [],
                }

                article_data['articles'].append(article_entry)
            else:
                # span class='bl' & input
                continue

    p_tags = [p for p in soup.find_all('p') if 'pty1_p4' not in p.get('class', []) and 'gtit' not in p.get('class', [])]

    for p in p_tags:
        for sfon in p.find_all('span', class_='sfon'):
            sfon.extract()

        content = process_content(p, popup_text)

        paragraph_match = re.match(r'^([①-⑳])\s*(.*)', content)
        if paragraph_match:
            paragraph_number = paragraph_match.group(1)
            paragraph_text = paragraph_match.group(2)

            if article_data['articles']:
                current_article = article_data['articles'][-1]
                current_paragraph = {
                    'paragraph_number': paragraph_number,
                    'paragraph_text': paragraph_text,
                    'items': [],
                    'sub_items': [],
                }
                current_article['paragraphs'].append(current_paragraph)
            continue

        # 항목 매칭 시도 (예: 1. 2. ...)
        item_match = re.match(r'^(\d+)\.\s*(.*)', content)
        if item_match:
            item_number = item_match.group(1)
            item_text = remove_leading_number(content, item_number + '.')

            item_entry = {
                'item_number': item_number,
                'item_text': item_text,
                'sub_items': [],
            }

            if article_data['articles']:
                current_article = article_data['articles'][-1]
                if current_article['paragraphs']:
                    current_paragraph = current_article['paragraphs'][-1]
                    current_paragraph['items'].append(item_entry)
            continue

        # 목 매칭 시도 (예: 가. 나. ...)
        subitem_match = re.match(r'^([가-힣])\.\s*(.*)', content)  # 가. 나. ...
        if subitem_match:
            subitem_number = subitem_match.group(1)
            subitem_text = remove_leading_number(content, subitem_number + '.')

            subitem_entry = {
                'subitem_number': subitem_number,
                'subitem_text': subitem_text,
                'sub_items': [],
            }

            if article_data['articles']:
                current_article = article_data['articles'][-1]
                if current_article['paragraphs']:
                    current_paragraph = current_article['paragraphs'][-1]
                    if current_paragraph['items']:
                        current_item = current_paragraph['items'][-1]
                        current_item['sub_items'].append(subitem_entry)
            continue

        # 하위 항목 매칭 시도 (예: 1) 2) ...)
        subsubitem_match = re.match(r'^(\d+)\)\s*(.*)', content)  # 1) 2) ...
        if subsubitem_match:
            subsubitem_number = subsubitem_match.group(1)
            subsubitem_text = remove_leading_number(content, subsubitem_number + ')')

            subsubitem_entry = {
                'subsubitem_number': subsubitem_number,
                'subsubitem_text': subsubitem_text,
                'sub_items': [],
            }

            if article_data['articles']:
                current_article = article_data['articles'][-1]
                if current_article['paragraphs']:
                    current_paragraph = current_article['paragraphs'][-1]
                    if current_paragraph['items']:
                        current_item = current_paragraph['items'][-1]
                        if current_item['sub_items']:
                            current_subitem = current_item['sub_items'][-1]
                            current_subitem['sub_items'].append(subsubitem_entry)
            continue

        # 그 외의 텍스트 처리: 현재 단락의 텍스트에 추가
        if article_data['articles']:
            current_article = article_data['articles'][-1]
            if current_article['paragraphs']:
                current_paragraph = current_article['paragraphs'][-1]
                if current_paragraph['paragraph_text']:
                    current_paragraph['paragraph_text'] += ' ' + content
                else:
                    current_paragraph['paragraph_text'] = content
            else:
                paragraph = {
                    'paragraph_number': None,
                    'paragraph_text': content,
                    'items': [],
                    'sub_items': [],
                }
                current_article['paragraphs'].append(paragraph)

    return article_data


def process_content(element, popup_text):
    content_str = ''
    for child in element.children:
        if isinstance(child, str):
            text = str(child).strip()
            if text:
                content_str += text
        elif child.name == 'a' and not 'data-popup-id' in child.attrs:
            content_str += ' ' + child.get_text(strip=True)
        else:
            child_content = process_content(child, popup_text)
            if child_content:
                content_str += child_content
    return content_str


def remove_leading_number(content_str, leading_number):
    """
    Removes the leading number (e.g., '①', '1.', '가)') from content_parts.
    """
    content_str = content_str.strip()
    if content_str.startswith(leading_number):
        return content_str[len(leading_number):].strip()
    return content_str


def process_law_detail(html_content, popup_text):
    law_name_div = html_content.find('div', class_='cont_top')
    law_name = law_name_div.h2.get_text(strip=True)
    law_name = law_name.split('(')[0].strip()

    department_div = html_content.find('div', class_='cont_subtit')
    department = department_div.get_text(strip=True)

    law = {
        'law_name': law_name,
        'department': department,
        'articles': []
    }

    pgroup_divs = html_content.find_all('div', class_='pgroup')

    for pgroup in pgroup_divs:
        lawcon = pgroup.find('div', class_='lawcon')
        if not lawcon:
            continue

        article_data = parse_article_content(lawcon, popup_text)

        if article_data:
            law['articles'].append(article_data)

        references = []
        a_tags = lawcon.find_all('a', {'data-popup-id': True})
        for a_tag in a_tags:
            popup_id = a_tag['data-popup-id']
            if popup_id in popup_text:
                ref_article = parse_article_content(popup_text[popup_id], popup_text)
                references.append(ref_article)
        if references:
            article_data['reference'] = references

        if article_data:
            law['articles'].append(article_data)

    return law


def extract_references(element, popup_text):
    references = []
    a_tags = element.find_all('a', {'data-popup-id': True})
    for a_tag in a_tags:
        popup_id = a_tag['data-popup-id']
        if popup_id in popup_text:
            references.append(popup_text[popup_id])
    return references


def close_popup(driver):
    try:
        close_button = driver.find_element(By.CSS_SELECTOR, '.btn22>a')
        close_button.click()
        return True
    except Exception as e:
        return False


def crawl_law_detail(url_link, file_idx):
    options = webdriver.ChromeOptions()
    # options.add_argument('headless')
    driver = webdriver.Chrome(options=options)
    os.makedirs(os.path.join(args.data_dir, 'law_details_raw'), exist_ok=True)
    
    try:
        driver.get(url_link)
        wait = WebDriverWait(driver, 8)
        
        driver.switch_to.frame('lawService')

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#contentBody')))

        html = driver.page_source

        popup_text = {}
        body_html = driver.execute_script("return document.body.innerHTML;")
        soup = BeautifulSoup(body_html, 'html.parser')

        links = soup.select('a.link[title="팝업으로 이동"]')
        for idx, link in enumerate(links):
            link['data-popup-id'] = str(idx)

        modified_body_html = str(soup)
        driver.execute_script("document.body.innerHTML = arguments[0];", modified_body_html)

        links = driver.find_elements(By.CSS_SELECTOR, 'a.link[title="팝업으로 이동"]')
        for idx, link in enumerate(links):
            try:
                if not link.text.strip().endswith(tuple(['조', '항', '호', '목', '령'])):
                    continue
                driver.execute_script("arguments[0].scrollIntoView();", link)
                link.click()

                time.sleep(0.25)
                if close_popup(driver):
                    continue
                
                original_window = driver.current_window_handle
                wait.until(EC.number_of_windows_to_be(2))
                driver.switch_to.window(driver.window_handles[1])

                popup_content = wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'div.pgroup')  # Adjust the selector as needed
                ))
                
                content_html = driver.page_source
                
                with open(os.path.join(args.data_dir, "law_details_raw", f'law_details_{file_idx}_popup_{idx}.html'), 'w', encoding='utf-8') as f:
                    f.write(content_html)
                
                popup_text[str(idx)] = popup_content.get_attribute('innerHTML')

                driver.close()
                driver.switch_to.window(original_window)
                driver.switch_to.default_content()
                wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'lawService')))
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#contentBody')))

            except Exception:
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(original_window)
                    driver.switch_to.default_content()
                    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'lawService')))
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#contentBody')))     

        html = driver.execute_script("return document.body.innerHTML;")
        
        with open(os.path.join(args.data_dir, "law_details_raw", f"law_details_{file_idx}.html"), 'w', encoding='utf-8') as f:
            f.write(html)
        
        soup = BeautifulSoup(html, 'html.parser')
        content_body_div = soup.find('div', id='contentBody')
        processed_law = process_law_detail(content_body_div, popup_text)
        
        with open(os.path.join(args.data_dir, "law_details_raw", f'law_details_{file_idx}_body.html'), 'w', encoding='utf-8') as f:
            f.write(str(content_body_div))
    
    finally:
        driver.quit()

    return processed_law


def update_article_numbers_recursively(obj):
    pattern = re.compile(r'제(\d+)조의(\d+)')
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == 'articles' and isinstance(value, list):
                for article in value:
                    if isinstance(article, dict):
                        full_name = article.get('article_full_name', '')
                        match = pattern.search(full_name)
                        if match:
                            main_number, sub_number = match.groups()
                            article['article_number'] = f"{main_number}_{sub_number}"
                        update_article_numbers_recursively(article)
            else:
                update_article_numbers_recursively(value)
    elif isinstance(obj, list):
        for item in obj:
            update_article_numbers_recursively(item)


def postprocess_law_data(data):
    """
    Recursively inspects the data structure to find 'content' fields that start with
    numbered bullets (e.g., '①') and processes them into 'paragraphs'.
    """
    unique_articles = []
    seen = set()
    
    for item in data.get('articles', []):
        if 'articles' in item:
            item_copy = deepcopy(item)
            
            articles_serialized = json.dumps(item_copy['articles'], sort_keys=True, ensure_ascii=False)
            
            if articles_serialized not in seen:
                seen.add(articles_serialized)
                unique_articles.append(item_copy)
        else:
            unique_articles.append(item)
    
    data['articles'] = unique_articles

    update_article_numbers_recursively(data)

    if isinstance(data, dict):
        if 'content' in data:
            content = data['content']
            match = re.match(r'^([①-⑩])\s*(.*)', content)
            if match:
                paragraph_number = match.group(1)
                paragraph_text = match.group(2).strip()

                paragraph_dict = {
                    "paragraph_number": paragraph_number,
                    "paragraph_text": paragraph_text,
                    "items": [],
                    "sub_items": []
                }

                if 'paragraphs' not in data or data['paragraphs'] is None:
                    data['paragraphs'] = []
                data['paragraphs'].insert(0, paragraph_dict)

                del data['content']
        
        for key, value in list(data.items()):
            if isinstance(value, list) and not value:
                del data[key]
            elif isinstance(value, dict):
                postprocess_law_data(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        postprocess_law_data(item)
        
        # 모든 value를 순회하며 str인 경우 앞뒤 공백 제거
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.strip()

    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Retrieve law information.')
    parser.add_argument('--id', required=True, help='API Key ID')
    parser.add_argument('--base', default='https://www.law.go.kr', help='Base URL')
    parser.add_argument('--data_dir', default='data/jomun', help='Data directory')
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
        # if exception occurs, retry
        max_retries = 5
        retry_count = 0
        while retry_count < max_retries:
            try:
                url_link = args.base + row['법령상세링크']
                os.makedirs(os.path.join(args.data_dir, 'law_detail'), exist_ok=True)
                processed_law = crawl_law_detail(url_link, row['법령ID'])
                processed_law_process = postprocess_law_data(processed_law)
                # save json
                with open(os.path.join(args.data_dir, 'law_detail', f'law_detail_{row["법령ID"]}.json'), 'w', encoding='utf-8') as f:
                    json.dump(processed_law_process, f, ensure_ascii=False, indent=4)
                break
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"Failed after {max_retries} retries: {e}")
                    break
                time.sleep(5)

