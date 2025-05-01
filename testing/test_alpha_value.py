import requests
import time
import json
from requests.exceptions import RequestException, JSONDecodeError

# --- Configuration ---
QUERIES_FILE = 'queries.txt'
RESULTS_FILE = "results.json"
BASE_URL = 'http://localhost:1234'
LOGIN_ENDPOINT = '/login'
RECOMMENDATION_ENDPOINT = '/recommendation'
LOGIN_CREDENTIALS = {'username': 'prob', 'password': 'prob'}
ALPHA_LIST = [0, 0.1, 0.3, 0.5, 0.7, 0.9, 1]
REQUEST_HEADERS = {'Content-Type': 'application/json'}
# Add a small delay between retries to avoid overwhelming the server
RETRY_DELAY_SECONDS = 2
# Rate limit settings
REQUESTS_BEFORE_SLEEP = 5
SLEEP_DURATION_SECONDS = 60
# --- End Configuration ---

def login(url, credentials, headers):
    """Attempts to log in and returns the session token."""
    try:
        login_response = requests.post(url + LOGIN_ENDPOINT, json=credentials, headers=headers)
        login_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        token = login_response.json().get('token')
        if not token:
            print("Login failed: No token found in response.")
            return None
        print("Login successful.")
        return token
    except RequestException as e:
        print(f"Login failed: {e}")
        return None
    except JSONDecodeError:
        print(f"Login failed: Could not decode JSON response from server.")
        return None

def process_response(response, query, alpha):
    """Processes a successful response, extracting relevant data."""
    try:
        obj = response.json()
        query_results = []
        # Ensure 'results' key exists and is a list
        results_data = obj.get('results', [])
        if not isinstance(results_data, list):
            print(f"Warning: 'results' field is not a list for '{query}' (alpha={alpha}). Skipping.")
            return None

        for result in results_data[:5]:  # Ensure we only take top 5
            # Basic validation for nested structure
            if not isinstance(result, dict): continue
            item = result.get('object')
            metadata = item.get('metadata')
            if not isinstance(item, dict) or not isinstance(metadata, dict): continue
            properties = item.get('properties')
            if not isinstance(properties, dict): continue

            query_results.append({
                "file_name": properties.get('name', 'N/A'),
                "language": properties.get('language', 'N/A'),
                "file_type": properties.get('file_type', 'N/A'),
                "url": properties.get('url', 'N/A'),
                "rerank_score": metadata.get('rerank_score'), # Allow None if missing
                "combined_score": result.get('combined_score'), # Allow None if missing
                "gains": 0
            })

        return {
            "query": query,
            "alpha": alpha,
            "result": query_results
        }
    except JSONDecodeError:
        print(f"Error: Invalid JSON response for '{query}' (alpha={alpha}) - Body: {response.text[:100]}...") # Log part of the body
        return None
    except KeyError as e:
        print(f"Error: Missing expected key {e} in response JSON for '{query}' (alpha={alpha}).")
        return None

# --- Main Execution ---

# Use context manager for reading queries
try:
    with open(QUERIES_FILE, 'r', encoding='utf-8') as f:
        queries = [line.strip() for line in f if line.strip()] # Ignore empty lines
except FileNotFoundError:
    print(f"Error: Queries file not found at '{QUERIES_FILE}'")
    exit()
except Exception as e:
    print(f"Error reading queries file: {e}")
    exit()

if not queries:
    print("Error: No queries found in the file.")
    exit()

# Attempt login
session_token = login(BASE_URL, LOGIN_CREDENTIALS, REQUEST_HEADERS)
if not session_token:
    exit()

request_cookies = {'session_token': session_token}
successful_responses = []
failed_requests_log = [] # Store info about failed requests for retry
request_counter = 0

print("\n--- Starting Initial Recommendation Requests ---")

for alpha in ALPHA_LIST:
    for query in queries:
        payload = {'input': query, 'alpha': alpha}
        request_desc = f"query='{query}', alpha={alpha}" # Description for logging

        try:
            response = requests.post(
                BASE_URL + RECOMMENDATION_ENDPOINT,
                json=payload,
                headers=REQUEST_HEADERS,
                cookies=request_cookies,
                timeout=30 # Add a timeout
            )

            # Check for non-200 status codes (including redirects if allow_redirects=False, but default is True)
            if response.status_code != 200:
                print(f"Request failed ({request_desc}): HTTP {response.status_code} - Response: {response.text[:100]}...")
                failed_requests_log.append({'payload': payload, 'reason': f"HTTP {response.status_code}"})
                continue # Skip processing for this request

            # Process successful response
            processed_data = process_response(response, query, alpha)
            if processed_data:
                print(f"Request successful ({request_desc})")
                successful_responses.append(processed_data)
            else:
                # Error occurred during JSON parsing or processing
                 failed_requests_log.append({'payload': payload, 'reason': "Response Processing Error"})

        except RequestException as e:
            print(f"Request failed ({request_desc}): Network/Request Error - {e}")
            failed_requests_log.append({'payload': payload, 'reason': f"RequestException: {e}"})

        # Rate limiting
        request_counter += 1
        if request_counter % REQUESTS_BEFORE_SLEEP == 0 and (alpha != ALPHA_LIST[-1] or query != queries[-1]): # Avoid sleep after the very last request
             # Check if it's not the very last request before sleeping
            is_last_alpha = (alpha == ALPHA_LIST[-1])
            is_last_query = (query == queries[-1])
            if not (is_last_alpha and is_last_query):
                 print(f"\n--- Processed {request_counter} requests. Sleeping for {SLEEP_DURATION_SECONDS} seconds due to rate limit ---")
                 time.sleep(SLEEP_DURATION_SECONDS)
                 # Re-login after sleep in case session expired
                 print("--- Re-logging in after sleep ---")
                 session_token = login(BASE_URL, LOGIN_CREDENTIALS, REQUEST_HEADERS)
                 if not session_token:
                     print("Error: Failed to re-login after sleep. Stopping.")
                     break # Stop processing this alpha if re-login fails
                 request_cookies = {'session_token': session_token}
                 print("--- Resuming requests ---")
    if not session_token: # Break outer loop if re-login failed
         break


print(f"\n--- Initial run complete. {len(successful_responses)} successful, {len(failed_requests_log)} failed. ---")

# --- Retry Failed Requests ---
if failed_requests_log:
    print(f"\n--- Retrying {len(failed_requests_log)} Failed Requests ---")
    # Re-login before retrying
    session_token = login(BASE_URL, LOGIN_CREDENTIALS, REQUEST_HEADERS)
    if not session_token:
        print("Error: Failed to re-login before retries. Skipping retries.")
    else:
        request_cookies = {'session_token': session_token}
        for i, failure_info in enumerate(failed_requests_log):
            payload = failure_info['payload']
            query = payload['input']
            alpha = payload['alpha']
            request_desc = f"query='{query}', alpha={alpha} (Retry {i+1}/{len(failed_requests_log)})"

            print(f"Retrying request for {request_desc} (Reason: {failure_info['reason']})")
            time.sleep(RETRY_DELAY_SECONDS) # Add delay between retries

            try:
                response = requests.post(
                    BASE_URL + RECOMMENDATION_ENDPOINT,
                    json=payload,
                    headers=REQUEST_HEADERS,
                    cookies=request_cookies,
                    timeout=30
                )

                if response.status_code != 200:
                    print(f"Retry failed ({request_desc}): HTTP {response.status_code} - Response: {response.text[:100]}...")
                    continue # Skip processing

                # Process successful retry response
                processed_data = process_response(response, query, alpha)
                if processed_data:
                    print(f"Retry successful ({request_desc})")
                    successful_responses.append(processed_data)
                # else: Error processing retry response (already logged in process_response)

            except RequestException as e:
                print(f"Retry failed ({request_desc}): Network/Request Error - {e}")

print("\n--- Retries complete. ---")

# --- Write Results ---
print(f"\nWriting {len(successful_responses)} results to {RESULTS_FILE}")
try:
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(successful_responses, f, indent=2, ensure_ascii=False)
    print("Results successfully written.")
except IOError as e:
    print(f"Error writing results to file: {e}")
except Exception as e:
    print(f"An unexpected error occurred during file writing: {e}")

print("\n--- Script Finished ---")