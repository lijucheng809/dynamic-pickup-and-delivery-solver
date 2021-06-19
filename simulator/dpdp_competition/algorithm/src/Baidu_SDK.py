from datetime import datetime, timedelta

import re
import logging as logger
from urllib import request, parse
import json
import math
from math import radians
import json

AK = 'GcB3wqNXz15lvtLgAl2Rh40LQTZ2MnwD'
# AK = 'AIu6oC7a2yKzGuIrSwtkvdeZo41TK9Zk'


HOST = 'http://api.map.baidu.com/'

API_GEO_CODER = 'geocoder/v2/?'
API_DIRECTION_DRIVING = 'direction/v2/driving?'


# 正向
def positive_geocoding(ak, address, output='json', **kwargs):
    """
    正向地理编码服务，提供将结构化地址数据（如：北京市海淀区上地十街十号）转换为对应坐标点（经纬度）功能。每日 300 万配额。

    :param ak: 开发者密钥。
    :param address: 待解析的地址，最多支持 84 个字节，建议传入标准的结构化地址信息，如：北京市海淀区上地十街十号。
    :param output: 可指定两种输出格式：json 或者 xml。
    :param kwargs: 可选参数有：city、ret_coordtype、sn、callback 等。
    :return: 参考 http://lbsyun.baidu.com/index.php?title=webapi/guide/webservice-geocoding
    """
    param_list = [
        ('ak', ak),
        ('address', address),
        ('output', output)
    ]
    if 'city' in kwargs:
        param_list.append(('city', kwargs.get('city')))
    if 'ret_coordtype' in kwargs:
        param_list.append(('ret_coordtype', kwargs.get('ret_coordtype')))
    if 'sn' in kwargs:
        param_list.append(('sn', kwargs.get('sn')))
    if 'callback' in kwargs:
        param_list.append(('callback', kwargs.get('callback')))
    params = parse.urlencode(param_list)
    url = HOST + API_GEO_CODER + str(params)
    try:
        res = json.loads(request.urlopen(url).read().decode('utf-8'))
    except:
        return {}
    # print(res)
    if res:
        # print(res)
        try:
            location = res['result']['location']
        except:
            return {}
    else:
        location = {}
    return location

# a = positive_geocoding(AK,'经济技术开发区科学城金峰园路2号 ')

def positive_geocoding_without_AK(address, output='json', **kwargs):
    """
    正向地理编码服务，提供将结构化地址数据（如：北京市海淀区上地十街十号）转换为对应坐标点（经纬度）功能。每日 300 万配额。

    :param ak: 开发者密钥。
    :param address: 待解析的地址，最多支持 84 个字节，建议传入标准的结构化地址信息，如：北京市海淀区上地十街十号。
    :param output: 可指定两种输出格式：json 或者 xml。
    :param kwargs: 可选参数有：city、ret_coordtype、sn、callback 等。
    :return: 参考 http://lbsyun.baidu.com/index.php?title=webapi/guide/webservice-geocoding
    """
    param_list = [
        ('ak', AK),
        ('address', address),
        ('output', output)
    ]
    if 'city' in kwargs:
        param_list.append(('city', kwargs.get('city')))
    if 'ret_coordtype' in kwargs:
        param_list.append(('ret_coordtype', kwargs.get('ret_coordtype')))
    if 'sn' in kwargs:
        param_list.append(('sn', kwargs.get('sn')))
    if 'callback' in kwargs:
        param_list.append(('callback', kwargs.get('callback')))
    params = parse.urlencode(param_list)
    url = HOST + API_GEO_CODER + str(params)
    res = json.loads(request.urlopen(url).read().decode('utf-8'))
    # print(res)
    if res['status'] != 2:
        # print(res)
        try:
            location = res['result']['location']
        except Exception as e:
            # sleep(10)
            # print("休眠10秒")
            res = json.loads(request.urlopen(url).read().decode('utf-8'))
            print(res, address)
            try:
                if res:
                    location = res['result']['location']
                else:

                    location = {}
            except:
                location = {}
    elif res['status'] ==2:
        location = {}
    else:
        location = {}
    return location

# 逆向
def get_address(lng, lat):
    """
    逆向编码出省市区
    :param lng:东经
    :param lat:北纬
    :return:元组：省、市、区
    """
    url = '{}{}callback=renderReverse&extensions_town=true&location={},{}&output=json&pois=1&latest_admin=1&ak={}'.format(HOST, API_GEO_CODER, lat, lng, AK)
    rp = request.urlopen(url).read().decode('utf-8')
    rp = re.findall(r"\((.*)\)", rp)[0]
    rpjson= json.loads(rp)
    # 省份
    try:
        province = rpjson['result']['addressComponent']['province']
        # 城市
        city = rpjson['result']['addressComponent']['city']
        # 区县
        district = rpjson['result']['addressComponent']['district']
        data = (province, city, district)
    except Exception as e:
        print(rpjson,lng,lat)
        # print(data.txt, rpjson)
        data = ()

    return data


def get_addr(lng, lat):
    """
    逆向编码出地址：'formatted_address' + 'pois'第一个元素
    :param lng:东经
    :param lat:北纬
    :return: 字符串
    """
    url = '{}{}callback=renderReverse&extensions_town=true&location={},{}&output=json&pois=1&latest_admin=1&ak={}'.format(HOST, API_GEO_CODER, lat, lng, AK)
    rp = request.urlopen(url).read().decode('utf-8')
    rp = re.findall(r"\((.*)\)", rp)[0]
    rpjson= json.loads(rp)
    addr1 = rpjson['result']['formatted_address']
    try:
        addr2 = rpjson['result']['pois'][0]['addr']
    except Exception as e:
        addr2 = addr1
    return addr2


def direction(origin, destination, ak=AK, output='json', **kwargs):
    """
    根据起终点坐标检索符合条件的驾车路线规划方案，支持以下功能：

    1. 支持一次请求返回多条路线（备用路线）；
    2. 支持20个以内的途径点；
    3. 支持传入车牌规避限行路段；
    4. 支持传入起点车头方向，辅助判断起点所在正逆向车道，辅助更准确算路；
    5. 支持传入历史出发时间，获取路线历史耗时，用于回溯历史出行耗时和预估未来出行耗时。
    :param ak: 开发者密钥。
    :param origin: 起点经纬度，小数点后不超过 6 位，40.056878,116.30815。
    :param destination: 终点经纬度，小数点后不超过 6 位，40.056878,116.30815。
    :param output: 输出类型，可设置为 xml 或 json，这里默认 Json 格式返回。
    :param kwargs: 可选参数参考：http://lbsyun.baidu.com/index.php?title=webapi/direction-api-v2 驾车路线规划。
    :return: 符合条件的路径规划方案。
    """

    origin = '%s,%s' % (origin[1], origin[0])
    destination = '%s,%s' % (destination[1], destination[0])

    param_list = [
        ('ak', ak),
        ('origin', origin),
        ('destination', destination),
        ('output', output),
    ]
    if 'origin_uid' in kwargs:
        param_list.append(('origin_uid', kwargs.get('origin_uid')))
    if 'destination_uid' in kwargs:
        param_list.append(('destination_uid', kwargs.get('destination_uid')))
    if 'waypoints' in kwargs:
        param_list.append(('waypoints', kwargs.get('waypoints')))
    if 'coord_type' in kwargs:
        param_list.append(('coord_type', kwargs.get('coord_type', 'bd0911')))
    if 'tactics' in kwargs:
        param_list.append(('tactics', kwargs.get('tactics', 0)))
    if 'alternatives' in kwargs:
        param_list.append(('alternatives', str(kwargs.get('alternatives', '0'))))
    if 'plate_number' in kwargs:
        param_list.append(('plate_number', kwargs.get('plate_number')))
    if 'ext_departure_time' in kwargs:
        param_list.append(('ext_departure_time', str(kwargs.get('ext_departure_time'))))
    if 'gps_direction' in kwargs:
        param_list.append(('gps_direction', kwargs.get('gps_direction')))
    if 'radius' in kwargs:
        param_list.append(('radius', kwargs.get('radius')))
    if 'speed' in kwargs:
        param_list.append(('speed', kwargs.get('speed')))
    if 'sn' in kwargs:
        param_list.append(('sn', kwargs.get('sn')))
    if 'timestamp' in kwargs:
        param_list.append(('timestamp', kwargs.get('timestamp')))
    if 'callback' in kwargs:
        param_list.append(('callback', kwargs.get('callback')))
    params = parse.urlencode(param_list)
    url = HOST + API_DIRECTION_DRIVING + str(params)
    # try:
    return request.urlopen(url).read().decode('utf-8')
    # except Exception as e:
        # logger.error(e)

"""
    :param a:三角形a边长
    :param b:三角形b边长
    :param c:三角形c边长
    return:C角的角度
"""
def get_c_arccos(a, b, c):
    return math.degrees(math.acos((a*a+b*b-c*c)/(2*a*b)))

"""
    :param lon1:第一个坐标点的经度（十进制度数）
    :param lat1:第一个坐标点的纬度（十进制度数）
    :param lon2:第二个坐标点的经度（十进制度数）
    :param lat2:第二个坐标点的纬度（十进制度数）
    return:两个坐标点间的直线距离（单位：米）
"""


def geodistance(lon1, lat1, lon2, lat2):
    # 十进制转化为弧度制
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine公式
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    # 地球平均半径，单位为公里
    r = 6378.137
    return c * r * 1000


def deal_md_list(md_list, jiao_c):
    # 保存原列表的长度
    md_list_len = len(md_list)
    # 倒序遍历【不影响前面的元素下标】，遍历到倒数第三个元素
    for md_i in reversed(range(2, md_list_len)):
        # 根据经纬度计算三角形三边长
        a = geodistance(md_list[md_i][0], md_list[md_i][1], md_list[md_i - 1][0], md_list[md_i - 1][1])
        b = geodistance(md_list[md_i - 1][0], md_list[md_i - 1][1], md_list[md_i - 2][0], md_list[md_i - 2][1])
        c = geodistance(md_list[md_i][0], md_list[md_i][1], md_list[md_i - 2][0], md_list[md_i - 2][1])
        if (a == 0) | (b == 0) | (a + b <= c):
            # (1) a或b边为0，即相邻坐标相等直接删除 (2) 两边和不大于第三边直接删除，即∠C=180°
            del md_list[md_i - 1]
        else:
            # 判断C角的大小是否大于参数jiao_c，是则剔除不传到前端展示
            try:
                if get_c_arccos(a, b, c) > jiao_c:
                    del md_list[md_i - 1]
            except Exception as e:
                del md_list[md_i - 1]

    return md_list


def analysisBaiduResult(data):
    data = json.loads(data)
    if data['message'] == '成功':
        result = data['result']
        # 默认取第一个规划方案的数据
        direction_distance = result['routes'][0]['distance']
        direction_duration = result['routes'][0]['duration']
        path_xi = []
        routes = result['routes']
        for route in routes:
            # 默认只返回一条推荐路线
            route_steps = route['steps']

            i = 0
            total_status = 0
            total_path = []  # 总路线
            for step in route_steps:
                step_traffic_condition = eval(str(step['traffic_condition']))
                total_status += step_traffic_condition[0]['status']
                i += 1
                step_path = step['path']
                path_list = str(step_path).split(';')
                total_path.extend(path_list)

            path = []
            for point in total_path:
                p = point.split(',')
                path.append(tuple((float(p[0]), float(p[1]))))


if __name__ == "__main__":
    s = [113.210967, 23.386709]
    e = [113.254754, 23.154134]
    data = eval(direction(s, e))
    if data['message'] == '成功':
        # status = data['status']
        # print(data)
        result = data['result']
        # 默认取第一个规划方案的数据
        direction_distance = result['routes'][0]['distance']
        direction_duration = result['routes'][0]['duration']
        print(direction_duration)
        print(direction_distance)

