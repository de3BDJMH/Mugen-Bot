import json,requests

def get_rating(qq):
    url=f"https://www.diving-fish.com/api/maimaidxprober/query/player"
    response = requests.post(url, json={"qq": qq, "b50": "1"})
    print(response.json())
    if response.status_code == 200:
        data=response.json()
        return data["rating"]
    else:
        return None

print(get_rating(2404164262))