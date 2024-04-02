import requests

# Define the URL
url = "http://127.0.0.1:5000/get_recommendations"

# Define the headers, including the ID
headers = {
    'id': 'user_2d3jvU6lHeJc1cSDkB7GVx7QpqB'
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    print(response.text)
else:
    print(f"Failed to get recommendations. Status code: {response.status_code}")
