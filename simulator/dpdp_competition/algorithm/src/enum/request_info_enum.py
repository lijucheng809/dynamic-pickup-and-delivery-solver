from enum import Enum


class RequestInfoEnum(Enum):
    """提货点id"""
    pickup_customer_id = 1

    """送货点id"""
    delivery_customer_id = 2

    """提货点时间窗"""
    pickup_timeWindow = 3

    """送货点时间窗"""
    delivery_timeWindow = 4

    """需求(总体积)"""
    demand = 5

    """订单创建时间"""
    creation_time = 6

    """互斥的货物类型列表"""
    incompatible_item_type_list = 7

    """装卸货需要的时间"""
    process_time = 8

    """托盘"""
    pallets = 9

    """包装尺寸清单"""
    bin_dimension = 10

    """提货地信息"""
    pickup_demand_info = 11

    """送货地信息"""
    delivery_demand_info = 12

    """订单完成时间"""
    finish_time = 13

    """订单id"""
    requestID = 14

    """货物类型集合"""
    item_type = 15
