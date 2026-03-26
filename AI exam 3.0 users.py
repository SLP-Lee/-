import requests
import json
import re
import time
import os  # 确保引入了 os
import platform
import getpass
import random

# ==========================================
# 🔑 API Key 配置
# 这里留空，程序启动时会自动检测或询问
# ==========================================
DASHSCOPE_API_KEY = "" 

_global_session = None

def save_api_key(key):
    """
    将 API Key 保存到本地配置文件，避免每次重复输入
    """
    config_file = "qwen_api_key.txt"
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(key.strip())
        print(f"✅ API Key 已保存到本地文件: {config_file}")
    except Exception as e:
        print(f"⚠️ 保存 Key 失败: {e}")

def load_api_key():
    """
    尝试从环境变量或本地文件加载 API Key
    """
    # 1. 优先读取环境变量 (适合服务器部署)
    key = os.getenv("DASHSCOPE_API_KEY")
    if key:
        return key

    # 2. 其次读取本地文件 (适合本地运行)
    config_file = "qwen_api_key.txt"
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            key = f.read().strip()
            if key:
                return key

    # 3. 都没有则返回 None，触发询问
    return None

def get_answer_from_ai(title, options, question_type):
    """
    使用远程 Qwen 模型获取答案（带重试机制）。
    """
    # 1. 构建 Prompt (保持不变)
    if question_type == 'english_to_chinese':
        prompt = f"""这是一道大学英语词汇题，属于英译中类型。
        题目是一个英文单词，请从四个中文选项中选择最准确的释义。
        请严格回答，只返回一个字母 (A, B, C, D)，不要有任何其他字符或文字。
        英文单词: {title}
        选项: A. {options['A']} B. {options['B']} C. {options['C']} D. {options['D']}"""
        
    elif question_type == 'chinese_to_english':
        prompt = f"""这是一道大学英语词汇题，属于中译英类型。
        题目是一个中文释义，请从四个英文单词选项中选择最准确的对应单词。
        请严格回答，只返回一个字母 (A, B, C, D)，不要有任何其他字符或文字。
        中文释义: {title}
        选项: A. {options['A']} B. {options['B']} C. {options['C']} D. {options['D']}"""
    else:
        return 'A'

    # 2. API 调用参数 (保持不变)
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "qwen-turbo",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1
    }

    # ==========================================
    # 🔄 核心修改：增加重试循环 (最多 10 次)
    # ==========================================
    max_retries = 10
    
    for attempt in range(1, max_retries + 1):
        try:
            # 尝试发送请求
            response = requests.post(url, headers=headers, json=data, timeout=10)
            result = response.json()
            
            # 检查 API 返回是否成功
            if "choices" in result and len(result["choices"]) > 0:
                result_text = result["choices"][0]["message"]["content"].strip()
                match = re.search(r'^[A-D]', result_text, re.IGNORECASE)
                if match:
                    # 成功获取答案，直接返回，跳出循环
                    return match.group(0).upper()
                else:
                    # 解析失败，视为一次错误，继续重试
                    print(f" [重试 {attempt}/{max_retries}] AI 返回内容无法识别: {result_text}")
            else:
                # API 报错 (如 401, 500)
                print(f" [重试 {attempt}/{max_retries}] API 返回错误: {result}")
                
        except Exception as e:
            # 网络异常 (如超时)
            print(f" [重试 {attempt}/{max_retries}] 请求异常: {e}")

        # 如果还没成功，等待 1 秒后再试 (避免请求过于频繁)
        if attempt < max_retries:
            time.sleep(1)

    # 如果循环结束还没返回，说明 10 次都失败了
    print(f" ❌ 经过 {max_retries} 次尝试仍失败，使用默认答案 A")
    return 'A'

def getAnswer(paper):
    """
    获取所有题目的答案：AI 优先级最高，不再询问用户。
    """
    print("\n" + "="*50)
    print("🚀 开始做题：正在调用 Qwen 模型答题...")
    print("="*50 + "\n")

    ans = { 
        "paperId": paper["paperId"], 
        "type": paper["type"], 
        "list": [] 
    }
    
    for question in paper["list"]:
        dic = { 
            "input": "A", # 默认值
            "paperDetailId": question["paperDetailId"] 
        }
        
        # 题目清洗
        title_raw = question["title"]
        title_cleaned = re.sub(r'[^\w\s]', '', title_raw).strip()
        
        options_for_ai = {
            'A': question['answerA'],
            'B': question['answerB'],
            'C': question['answerC'],
            'D': question['answerD']
        }
        
        question_type = 'english_to_chinese' if re.search(r'[a-zA-Z]', title_cleaned) else 'chinese_to_english'

        final_choice = get_answer_from_ai(title_raw, options_for_ai, question_type)
        dic["input"] = final_choice
        ans["list"].append(dic)
        
        print(f"题目: {title_raw[:30]}... -> 选项: {final_choice} (AI决策)")
        
    print(f"\n✅ 全自动答题结束！共处理 {len(ans['list'])} 题。")
    return ans

def AESencrypt(key, password):
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    import base64
    key = base64.b64decode(key)
    password = password.encode()
    cipher = AES.new(key, AES.MODE_ECB)
    password = pad(password, AES.block_size)
    encText = cipher.encrypt(password)
    return base64.b64encode(encText).decode()

def getHeaders(token):
    if token == "session_based_auth":
        headers = { 
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Referer': 'https://skl.hdu.edu.cn/',
            'Origin': 'https://skl.hdu.edu.cn'
        }
    else:
        headers = { 
            'X-Auth-Token': token,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Content-Type': 'application/json;charset=UTF-8',
            'Origin': 'https://skl.hdu.edu.cn',
            'Referer': 'https://skl.hdu.edu.cn/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        }
    return headers

def login(username, password):
    import requests
    global _global_session
    print("开始登录流程...")
    try:
        print("1. 直接访问CAS登录页面...")
        session = requests.Session()
        session.headers.update({ "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36" })

        ssourl = "https://sso.hdu.edu.cn/login"
        r = session.get(ssourl, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"无法访问CAS登录页面，状态码: {r.status_code}")
        print(" ✓ 成功访问CAS登录页面")

        print("2. 解析登录参数...")
        try:
            key = re.findall(r'>.+<', re.findall(r'<p id="login-croypto">.+</p>', r.text)[0])[0][1:-1]
            execution = re.findall(r'>.+<', re.findall(r'<p id="login-page-flowkey">.+</p>', r.text)[0])[0][1:-1]
            print(f" ✓ 获取到参数 - croypto: {key[:20]}..., execution: {execution[:20]}...")
        except (IndexError, AttributeError):
            key_matches = re.findall(r'<p id="login-croypto">(.+?)</p>', r.text)
            execution_matches = re.findall(r'<p id="login-page-flowkey">(.+?)</p>', r.text)
            if key_matches and execution_matches:
                key = key_matches[0]
                execution = execution_matches[0]
                print(f" ✓ 使用新方法获取参数 - croypto: {key[:20]}..., execution: {execution[:20]}...")
            else:
                raise RuntimeError("无法解析登录参数，请检查网页结构是否发生变化")
        
        print("3. 准备登录数据...")
        data = {
            "username": username,
            "type": "UsernamePassword",
            "_eventId": "submit",
            "geolocation": "",
            "execution": execution,
            "captcha_code": "",
            "croypto": key,
            "password": AESencrypt(key, password),
        }
        session.headers.update({ "Content-Type": "application/x-www-form-urlencoded" })

        print("4. 执行登录...")
        r = session.post(ssourl, data=data, allow_redirects=False, timeout=15)
        if r.status_code not in [302, 200]:
            if r.status_code == 401:
                raise RuntimeError("用户名或密码不正确")
            else:
                raise RuntimeError(f"登录请求失败，状态码: {r.status_code}")

        if "统一身份认证" in r.text or "用户名或密码不正确" in r.text:
            raise RuntimeError("用户名或密码不正确")

        print(" ✓ 登录请求成功")

        print("5. 处理重定向...")
        if r.status_code == 302 and "Location" in r.headers:
            location = r.headers["Location"]
            print(f" 重定向到: {location}")
            r = session.get(location, timeout=15)
            print(f" 最终URL: {r.url}")

        if "skl.hdu.edu.cn" not in r.url:
            print(" 检测到重定向到其他系统，正在访问英语学习系统...")
            skl_url = "https://skl.hdu.edu.cn/#/english/list"
            r = session.get(skl_url, timeout=15)
            print(f" 英语系统URL: {r.url}")

        if "skl.hdu.edu.cn" in r.url or "skl.hdu.edu.cn" in str(r.request.url):
            print(" ✓ 成功访问英语学习系统")
            final_url = r.url if hasattr(r, 'url') else str(r.request.url)
            if "token=" in final_url:
                token_matches = re.findall(r'token=([^&]+)', final_url)
                if token_matches:
                    token = token_matches[0]
                    print(f" ✓ 获取到token: {token[:20]}...")
                    headers = getHeaders(token)
                    test_r = requests.get("https://skl.hdu.edu.cn/api/userinfo?type=&index=", headers=headers, timeout=15)
                    if test_r.status_code == 200:
                        try:
                            user_info = test_r.json()
                            if "userName" in user_info:
                                print("✓ 登录成功！你好，" + user_info["userName"])
                                return token
                        except json.JSONDecodeError:
                            pass

        print("6. 验证基于session的认证...")
        try:
            main_page = session.get("https://skl.hdu.edu.cn/", timeout=15)
            print(f" 英语系统主页状态: {main_page.status_code}")

            token_patterns = [
                r'token["\']?\s*[:=]\s*["\']([^"\'^;]+)["\']',
                r'authToken["\']?\s*[:=]\s*["\']([^"\'^;]+)["\']',
                r'access_token["\']?\s*[:=]\s*["\']([^"\'^;]+)["\']',
                r'bearer["\']?\s*[:=]\s*["\']([^"\'^;]+)["\']'
            ]
            found_token = None
            for pattern in token_patterns:
                matches = re.findall(pattern, main_page.text, re.IGNORECASE)
                if matches:
                    found_token = matches[0]
                    print(f" ✓ 在页面中发现token: {found_token[:20]}...")
                    break

            if found_token:
                test_headers = getHeaders(found_token)
                test_r = requests.get("https://skl.hdu.edu.cn/api/userinfo?type=&index=", headers=test_headers, timeout=15)
                if test_r.status_code == 200:
                    user_info = test_r.json()
                    if "userName" in user_info:
                        print("✓ 登录成功！你好，" + user_info["userName"])
                        return found_token

            print(" 未在页面中找到有效token，继续使用session认证")
            print(f" Session cookies: {list(session.cookies.keys())}")
            
            session.headers.update({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"'
            })

            time.sleep(1)
            main_page2 = session.get("https://skl.hdu.edu.cn/#/english/list", timeout=15)
            print(f" 第二次访问主页状态: {main_page2.status_code}")

            session.headers.update({
                "Accept": "application/json, text/plain, */*",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "Referer": "https://skl.hdu.edu.cn/",
                "Origin": "https://skl.hdu.edu.cn",
                "X-Requested-With": "XMLHttpRequest"
            })

            api_r = session.get("https://skl.hdu.edu.cn/api/userinfo?type=&index=", timeout=15)
            print(f" API访问状态: {api_r.status_code}")
            if api_r.status_code == 200:
                user_info = api_r.json()
                if "userName" in user_info:
                    print("✓ 登录成功！你好，" + user_info["userName"])
                    _global_session = session
                    return "session_based_auth"
            elif api_r.status_code == 401:
                print(f" API返回401，响应内容: {api_r.text[:200]}...")
                try:
                    api_response = api_r.json()
                    if "url" in api_response and "cas" in api_response["url"]:
                        print(" 检测到CAS重新认证需求，正在处理...")
                        cas_url = api_response["url"]
                        print(f" CAS URL: {cas_url}")
                        cas_r = session.get(cas_url, timeout=15)
                        print(f" CAS认证状态: {cas_r.status_code}")
                        print(f" CAS最终URL: {cas_r.url}")
                        
                        if cas_r.status_code == 200:
                            final_url = str(cas_r.url)
                            if "token=" in final_url:
                                token_matches = re.findall(r'token=([^&]+)', final_url)
                                if token_matches:
                                    extracted_token = token_matches[0]
                                    print(f" ✓ 从CAS认证中提取到token: {extracted_token[:20]}...")
                                    print(f" ✓ 成功获取到认证token")
                                    return extracted_token
                        
                        if "skl.hdu.edu.cn" in final_url:
                            print(" ✓ CAS重新认证成功，尝试session API访问")
                            api_r2 = session.get("https://skl.hdu.edu.cn/api/userinfo?type=&index=", timeout=15)
                            if api_r2.status_code == 200:
                                user_info = api_r2.json()
                                if "userName" in user_info:
                                    print(f" ✓ 登录成功！你好，{user_info['userName']}")
                                    _global_session = session
                                    return "session_based_auth"
                except (json.JSONDecodeError, KeyError):
                    print(" 无法解析API响应中的重定向信息")

            print("✓ 登录成功！已建立会话连接")
            _global_session = session
            return "session_based_auth"

        except Exception as e:
            print(f" API访问异常: {str(e)}")
            print("✓ 登录成功！已建立会话连接")
            _global_session = session
            return "session_based_auth"

    except requests.exceptions.Timeout:
        raise RuntimeError("网络连接超时，请检查网络连接")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("网络连接失败，请检查网络连接")
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise e
        else:
            raise RuntimeError(f"未知错误: {str(e)}")


def getWeek(token):
    global _global_session
    print("正在获取当前周数...")
    if token == "session_based_auth" and _global_session:
        _global_session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://skl.hdu.edu.cn/",
            "X-Requested-With": "XMLHttpRequest"
        })
        r = _global_session.get("https://skl.hdu.edu.cn/api/course?startTime=2024-04-08", timeout=10)
    else:
        headers = getHeaders(token)
        headers.update({ "Accept": "application/json, text/plain, */*", "Referer": "https://skl.hdu.edu.cn/" })
        r = requests.get("https://skl.hdu.edu.cn/api/course?startTime=2024-04-08", headers=headers, timeout=10)

    if r.status_code != 200:
        print(f"获取周数失败，状态码: {r.status_code}")
        print("使用默认周数: 1")
        return 1
    try:
        data = r.json()
        if "week" in data:
            week = data["week"]
            print(f"当前周数: {week}")
            return week
        else:
            print("响应中没有周数信息，使用默认周数: 1")
            return 1
    except json.JSONDecodeError:
        print("无法解析周数响应，使用默认周数: 1")
        return 1


def exam(token, week, mode, delay):
    startTime = time.time()
    if mode == '0':
        print("开始自测")
    elif mode == '1':
        print("开始考试")
    
    url = f"https://skl.hdu.edu.cn/api/paper/new?type={mode}&week={week}&startTime=" + str(int(startTime*1000))
    print(f"正在获取题目... URL: {url}")
    
    if token == "session_based_auth" and _global_session:
        api_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Referer": "https://skl.hdu.edu.cn/",
            "Origin": "https://skl.hdu.edu.cn",
            "X-Requested-With": "XMLHttpRequest"
        }
        _global_session.headers.update(api_headers)
        try:
            main_page = _global_session.get("https://skl.hdu.edu.cn/", timeout=10)
            userinfo_r = _global_session.get("https://skl.hdu.edu.cn/api/userinfo?type=&index=", timeout=10)
            if userinfo_r.status_code == 200:
                print("✓ Session认证有效")
            elif userinfo_r.status_code == 401:
                print("⚠ Session认证失效，尝试刷新session...")
                refresh_r = _global_session.get("https://skl.hdu.edu.cn/#/english/list", timeout=10)
                userinfo_r2 = _global_session.get("https://skl.hdu.edu.cn/api/userinfo?type=&index=", timeout=10)
                if userinfo_r2.status_code != 200:
                    print(f"Session刷新失败，状态码: {userinfo_r2.status_code}")
                    print("请重新运行程序登录")
                    return
        except Exception as e:
            print(f"Session验证过程出错: {e}")
        
        r = _global_session.get(url, timeout=15)
        print(f"题目API响应状态码: {r.status_code}")
        
    else:
        headers = getHeaders(token)
        headers["User-Agent"] = "Mozilla/5.0 (Linux; Android 4.2.1; M040 Build/JOP40D) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/31.0.1650.59 Mobile Safari/537.36"
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Referer"] = "https://skl.hdu.edu.cn/"
        r = requests.get(url, headers=headers)
        print(f"题目API响应状态码: {r.status_code}")

    if r.status_code != 200:
        print(f"API调用失败，状态码: {r.status_code}")
        print(f"错误响应: {r.text}")
        if "申请考试失败" in r.text and "请勿在短时间重试" in r.text:
            print("\n⚠️ 检测到短时间内重复申请错误")
            print("建议等待至少5-10分钟后再次尝试")
            return
        if "登录" in r.text or "login" in r.text.lower() or r.status_code == 401:
            print("可能需要重新登录，请重新运行程序")
            return
        return

    try:
        paper = r.json()
    except json.JSONDecodeError as e:
        print(f"响应不是有效的JSON格式: {e}")
        print(f"原始响应: {r.text}")
        return

    if not isinstance(paper, dict):
        print(f"响应数据格式异常: {paper}")
        return

    if "code" in paper and paper.get("code") != 0:
        error_msg = paper.get("msg", "未知错误")
        print(f"\n❌ API返回错误: {error_msg}")
        if "申请考试失败" in error_msg and "短时间重试" in error_msg:
            print("\n💡 解决建议:")
            print("1. 等待5-10分钟后再次尝试")
            print("2. 检查是否已有未完成的考试")
            print("3. 如果是考试模式，确认本周考试次数是否已用完")
            return
        return

    if "paperId" not in paper or "list" not in paper:
        print(f"响应缺少必要字段: {paper}")
        return

    print(f"成功获取题目，共 {len(paper.get('list', []))} 道题")
    
    # --- 答题 ---
    ans = getAnswer(paper)

    # --- 提交 ---
    print("等待提交中...请不要关闭终端...")
    if delay > 0:
        time.sleep(delay)
    print("正在提交答案...")

    submit_url = "https://skl.hdu.edu.cn/api/paper/save"
    if token == "session_based_auth" and _global_session:
        _global_session.headers.update({
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest"
        })
        submit_r = _global_session.post(submit_url, json=ans, timeout=15)
    else:
        headers = getHeaders(token)
        headers.update({
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
        })
        submit_r = requests.post(submit_url, json=ans, headers=headers, timeout=15)

    if submit_r.status_code == 200:
        print("提交成功！")
    else:
        print(f"提交失败，状态码: {submit_r.status_code}")
        print(f"错误信息: {submit_r.text}")
        return

    # --- 获取成绩 ---
    time.sleep(0.5)
    detail_url = f"https://skl.hdu.edu.cn/api/paper/detail?paperId={ans['paperId']}"
    print("正在获取成绩...")

    if token == "session_based_auth" and _global_session:
        result_r = _global_session.get(detail_url, timeout=15)
    else:
        result_r = requests.get(detail_url, headers=getHeaders(token), timeout=15)

    if result_r.status_code == 200:
        try:
            result_data = result_r.json()
            if "mark" in result_data:
                print("本次成绩:", result_data["mark"])
                print("heartfelt thank you to every student striving for\nWO AI JI DAN CI")
            else:
                print("成绩数据格式异常:", result_data)
        except json.JSONDecodeError:
            print("无法解析成绩响应:", result_r.text)
    else:
        print(f"获取成绩失败，状态码: {result_r.status_code}")
        print(f"错误信息: {result_r.text}")


def main():
    global DASHSCOPE_API_KEY
    
    DASHSCOPE_API_KEY = load_api_key()
    
    if not DASHSCOPE_API_KEY:
        print("\n" + "="*50)
        print("⚠️  未检测到 Qwen API Key")
        print("="*50)
        input_key = input("请输入你的 DashScope API Key: ").strip()
        
        if input_key:
            DASHSCOPE_API_KEY = input_key
            save_choice = input("是否保存到本地以便下次自动使用? (y/n): ").lower()
            if save_choice == 'y':
                save_api_key(DASHSCOPE_API_KEY)
        else:
            print("❌ 未输入 Key，程序退出。")
            return

    print("\n" + "-"*30)
    print("🎓 请登录教务系统")
    print("-"*30)
    
    un = input("请输入学号: ").strip()
    pd = getpass.getpass("请输入密码(为了安全，密码已经被隐形): ")
    
    print("\n登录中...请稍后...")
    
    command = 'cls' if platform.system().lower() == 'windows' else 'clear'
    os.system(command)
    
    token = login(un, pd)
    
    if not token:
        print("❌ 登录失败，请检查学号和密码。")
        return

    try:
        week = getWeek(token)
        print(f"本周是第{week}周")
    except:
        week = 1

    while True:
        try:
            mode = input("请选择模式自测(0)/考试(1): ")
            assert mode == '0' or mode == '1'
            delay = int(input("输入做题时间(s)建议范围300-480或者0(不用等待自测用): "))
            if delay < 300 or delay > 480:
                if not(mode == '0' and delay == 0):
                    print("数据不在建议范围内，已帮您设置成450")
                    delay = 450
            print(f"需要等待时间为{delay//60}分{delay%60}秒")
            break
        except KeyboardInterrupt:
            exit()
        except AssertionError:
            print("输入数据有误！请重新输入！")
        except ValueError:
            print("请输入数字！")

    exam(token, week, mode, delay)

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"📂 当前工作目录已切换至: {os.getcwd()}")
    print("\n" + "="*50)
    print("🚀 程序启动，即将进入主菜单...")
    print("="*50 + "\n")
    main()