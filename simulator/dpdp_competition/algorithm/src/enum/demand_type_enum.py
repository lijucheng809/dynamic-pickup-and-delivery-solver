from enum import Enum


class DemandTypeEnum(Enum):
    """表示未装车的货物，提货点"""
    pickup = 1
    """表示未装车的货物，送货点"""
    delivery = 2
    """表示已装车的货物，只含有送送点"""
    delivery_only = 3
