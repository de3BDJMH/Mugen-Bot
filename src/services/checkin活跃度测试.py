from . import checkin
from ..storage import checkin as checkin_storage

users=checkin_storage.get_all_user_data()

acr=[]
for user in users:
    rating=checkin.get_user_rating(user["user_id"])
    if rating:
        acr.append(rating)

acr.sort(key=lambda x:x["rating"],reverse=True)
for i,user in enumerate(acr[:30]):
    user["rank"]=i+1
    print(f"{i+1}. {user['nickname']} : {user['rating']:.2f} = {user['tmp'][0]:.2f}+{user['tmp'][1]:.2f}+{user['tmp'][2]:.2f}")
    print(f"活跃天数: {user['tmp_data'][0]}, 主动行为: {user['tmp_data'][1]}, Data: {user['tmp_data'][2]}, B10: {[round(x,2) for x in user['tmp_data'][3]]}")