from enum import Enum


class ItemInfoEnum(Enum):
    """物料id"""
    id = 1

    """对应订单的id"""
    order_id = 2

    """包装类型"""  # todo 后面名字要改为 package type
    type = 3

    """体积"""
    demand = 4

    """提货点"""
    pickup_factory_id = 5

    """送货点"""
    delivery_factory_id = 6

    """订单创建时间"""
    creation_time = 7

    """承诺送达时间"""
    committed_completion_time = 8

    """调度算法时刻"""
    update_time = 9

    """装货时长"""
    load_time = 10

    """卸货时长"""
    unload_time = 11

    """订单状态"""
    delivery_state = 12

    """包装尺寸"""
    dimension = 13

    """物料类型"""
    item_type = 14

    """不兼容的货物类型"""
    incompatible_items = 15
