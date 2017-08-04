
"""import redis
import json

# print last input pps for ge-1/0/5 on Chicago

r = redis.StrictRedis(host='10.10.4.252', port=6379, db=0)
keys = r.keys()
for key in keys:
    key = key.decode("utf-8")
    if "latency" in key:
        link_lat = latency_str = r.lrange(key, 0, -1)[0]
        link_lat = json.loads(link_lat)
        print(link_lat)"""

dic1 = {'a':'a','b':'c','c':'d'}
dic2 = {'f':'a','g':'c','c':'d'}
print(dic1.keys() in dic2.keys())
