from ChangeCoordinate import ChangeCoord
from urllib import request, parse
import requests
import json
import time
import pandas as pd

from simulator.dpdp_competition.algorithm.conf.configs import Configs

coord = ChangeCoord()


def amap_trucks_route(origin, destination, output='json', **kwargs):
    """
    正向地理编码服务，提供将结构化地址数据（如：北京市海淀区上地十街十号）转换为对应坐标点（经纬度）功能。
    :param origin: 起始点经纬度字符串，例如：'121.46452520491748, 31.37182955909548'
    :param destination: 起始点经纬度字符串，例如：'121.46452520491748, 31.37182955909548'
    :param output: 可指定两种输出格式：json 或者 xml。
    :param kwargs: 可选参数有：size、strategy、province 等。
    :return: 参考 https://lbs.amap.com/api/webservice/guide/api/georegeo
    """

    # origin_location = origin.split(",")
    # ToDo bd09体系（百度）转gcj02体系（高德等），看具体传参的经纬度体系
    lng, lat = coord.bd09_to_gcj02(float(origin[0]), float(origin[1]))
    origin = "%s,%s" % (lng, lat)

    # des_location = destination.split(",")
    # ToDo bd09体系（百度）转gcj02体系（高德等），看具体传参的经纬度体系
    des_lng, des_lat = coord.bd09_to_gcj02(float(destination[0]), float(destination[1]))
    destination = "%s,%s" % (des_lng, des_lat)

    key = "f6910ecfd907ce67749bbc23c3bc48ae"
    param_list = [
        ('key', key),  # 开发者密钥
        ('origin', origin),
        ('destination', destination),
        ('output', output)
    ]

    # ToDo 以下参数详细介绍https://lbs.amap.com/api/webservice/guide/api/direction#t9【货车路径规划】
    if 'size' in kwargs:  # 车型大小，1：微型车，2：轻型车（默认值），3：中型车，4：重型车
        param_list.append(('size', kwargs.get('size')))
    if 'strategy' in kwargs:  # 策略
        param_list.append(('strategy', kwargs.get('strategy')))
    if 'height' in kwargs:
        param_list.append(('height', kwargs.get('height')))
    if 'width' in kwargs:
        param_list.append(('width', kwargs.get('width')))
    if 'weight' in kwargs:
        param_list.append(('weight', kwargs.get('weight')))
    if 'province' in kwargs:
        param_list.append(('province', kwargs.get('province')))
    if "nosteps" in kwargs:
        param_list.append(('nosteps', kwargs.get('nosteps')))
    params = parse.urlencode(param_list)
    url = 'https://restapi.amap.com/v4/direction/truck?' + str(params)
    try:
        return request.urlopen(url).read().decode('utf-8')
    except Exception as e:
        print(e)


def get_gaode_locations(address):
    para = {
        'key': "f6910ecfd907ce67749bbc23c3bc48ae",
        'address': address
    }
    url = 'https://restapi.amap.com/v3/geocode/geo?'
    req = requests.get(url, para)
    req = req.json()

    if len(req['geocodes']) == 0:
        location = {}
    else:
        ori_location = req['geocodes'][0]['location']
        lng = float(ori_location.split(',')[0])
        lat = float(ori_location.split(',')[1])
        location = {'lng': lng, 'lat': lat}

    return location


if __name__ == "__main__":
    a = amap_trucks_route([112.895183, 22.877041],
                          [112.9114126, 22.89114543],
                          output="json",
                          size="2",
                          strategy=11,
                          nosteps=0, )
    # factory_df = pd.read_csv(
    #     "/Users/lijucheng/Desktop/dynamic-pickup-and-delivery-solver/simulator/dpdp_competition/benchmark/factory_info.csv")
    # factories = []
    # with open("/Users/lijucheng/Desktop/dynamic-pickup-and-delivery-solver/simulator/dpdp_competition/algorithm/data/route_map/route_cost_map.json", "r") as f:
    #     route_cost_map = json.load(f)
    # for index, row in factory_df.iterrows():
    #     factory_id = str(row['factory_id'])
    #     lng = float(row['longitude'])
    #     lat = float(row['latitude'])
    #     dock_num = int(row['port_num'])
    #     factories.append({"id": factory_id, "lng": lng, "lat": lat})
    # for i in range(len(factories)):
    #     for j in range(len(factories)):
    #         if i != j:
    #             id = factories[i]["id"] + factories[j]["id"]
    #             route_detail = amap_trucks_route([factories[i]["lng"], factories[i]["lat"]],
    #                                              [factories[j]["lng"], factories[j]["lat"]],
    #                                              output="json",
    #                                              size="2",
    #                                              strategy=11,
    #                                              nosteps=0)
    #             route_detail = json.loads(route_detail)
    #             route_cost_map[id]["distance"] = float(route_detail["data"]["route"]["paths"][0]["distance"])
    #             route_cost_map[id]["travel_time"] = float(route_detail["data"]["route"]["paths"][0]["duration"])
    #             nodes = []
    #             for index, step in enumerate(route_detail["data"]["route"]["paths"][0]["steps"]):
    #                 polyline = step["polyline"]
    #                 polyline = polyline.split(";")
    #                 for key, pos in enumerate(polyline):
    #                     pos_coord = pos.split(",")
    #                     if index != len(route_detail["data"]["route"]["paths"][0]["steps"])-1 and key == len(polyline)-1:
    #                         continue
    #                     else:
    #                         nodes.append([float(pos_coord[0]), float(pos_coord[1])])
    #             route_cost_map[id]["polyline"] = nodes
    #
    # with open("test.json", "w") as f:
    #     json.dump(route_cost_map, f, indent=4)
    a = json.loads(a)
    print(a["data"]["route"]["paths"][0]["steps"][0]["polyline"])
    for key in a["data"]["route"]["paths"][0]["steps"]:
        print(key)

