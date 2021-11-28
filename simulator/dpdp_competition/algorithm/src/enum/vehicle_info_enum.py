from enum import Enum


"""
| id                             | id of vehicle, 车牌号                                        | str  |
| operation_time                 | operation time of vehicle(unit: hour), 车辆的运营时长        | int |
| capacity                       | capacity of vehicle (unit: standard pallet, 单位: 标准栈板)  | int |
|dimension                       | 车辆货柜尺寸，长 * 宽 * 高                                     |dict |
|gps_id                          | 车辆当前位置，{"lng": 1.344 "lat": 1.344}                     |dict |
|compatible_item_type_list       | 可载货物类型集合                                              |list |
|cur_gps_id                     | 当前位置的经纬度,list, 如果cur_factory_id不为空，则取[]           |list |
|current_operation_time          | 截止目前，车辆（司机）的运行时长，hours |double    |
|current_mileage                  | 截止目前，车辆（司机）的行驶的里程，km |double      |
|polyline_to_destination          |从当前点到下个目的地点的具体行车路径|[[lng1, lat1], [lng2, lat2], ...]  |
| update_time                    | 车辆当前位置和状态的更新时间 | int   |
| cur_factory_id                 | 车辆当前所在的工厂, 如果当前不在任何工厂则为""。 | str |
| arrive_time_at_current_factory | 车辆到达当前所在工厂的时间 | int               |
| leave_time_at_current_factory  | 车辆离开当前所在工厂的时间 | int               |
| carrying_items                 | 车辆当前载的物料编号列表，顺序为装货顺序 | [str1, str2, ...] |
| destination                    | 当前车辆的目的地, 目的地一旦确定不可更改, 直到车辆到达目的地节点，如果当前车辆处于停车状态，目的地为空 | dict  |
| former_factory_id              | 车辆上一个服务过的工厂, 如果当前不在任何工厂则为""。 | str |
| leave_time_at_former_factory   | 车辆离开上一个服务过的工厂的时间, 如果当前不在任何工厂则为0。 | int |
|
"""


class VehicleInfoEnum(Enum):
    """车辆id"""
    id = 1

    """最大运行时长"""
    operation_time = 2

    """车辆容量"""
    capacity = 3

    """车厢尺寸"""
    dimension = 4

    """当前位置"""
    gps_id = 5

    """兼容的货物类型列表"""
    compatible_item_type_list = 6

    """当前位置的经纬度"""
    cur_gps_id = 5

    """目前运行时长"""
    current_operation_time = 6

    """目前的行驶里程"""
    current_mileage = 7

    """到下一目的地的具体行车轨迹"""
    polyline_to_destination = 8

    """启动调度的时刻"""
    update_time = 9

    """当前所在的工厂"""
    cur_factory_id = 10

    """到达目前所在工厂的时刻"""
    arrive_time_at_current_factory = 11

    """离开目前所在工厂的时刻"""
    leave_time_at_current_factory = 12

    """目前车上所载货物清单"""
    carrying_items = 13

    """下站目的地"""
    destination = 14

    """车辆上一个服务过的工厂"""
    former_factory_id = 15

    """车辆离开上一个服务过的工厂的时间"""
    leave_time_at_former_factory = 16
