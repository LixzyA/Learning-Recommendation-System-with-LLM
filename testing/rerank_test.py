import requests
import time
queries = open('queries.txt', 'r', encoding='utf-8').readlines()
url = 'http://localhost:1234'

# Try with headers and JSON data
headers = {'Content-Type': 'application/json'}
login_data = {'username': 'string', 'password': 'string'}
counter = 0
try:
    response = requests.post(url+'/login', json=login_data, headers=headers)
    if response.status_code == 200:
        token = eval(response.text).get("token")
        cookies = {'session_token': token}
        if token != None:
            try:
                for query in queries:
                    query = query.strip()
                    response = requests.post(url+'/recommendation', json={'input': query}, headers=headers, cookies=cookies)
                    print(f"Request for {query}, status_code = {response.status_code}")
                    counter += 1
                    if counter % 5 == 0:  # After every 5 requests
                        print("Sleep for 1 minute")
                        time.sleep(60) # cohere reranker rate limit
                requests.get(url+"/save", headers=headers, cookies=cookies)
            except requests.exceptions.RequestException as e:
                print(f"Request failed: {e}")
except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
