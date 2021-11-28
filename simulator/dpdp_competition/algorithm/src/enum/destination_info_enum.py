from enum import Enum


class DestinationInfoEnum(Enum):
    """目的地id"""
    factory_id = 1

    """卸货清单"""
    delivery_item_list = 2

    """装货清单"""
    pickup_item_list = 3

    """到达时刻"""
    arrive_time = 4

    """ 离开时刻"""
    leave_time = 5
