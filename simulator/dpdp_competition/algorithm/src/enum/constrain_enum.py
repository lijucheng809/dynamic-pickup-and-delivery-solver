from enum import Enum


class ConstrainEnum(Enum):
    bin_packing = 1
    time_window = 2
    capacity = 3
    lifo = 4
    port_resource = 5
    incompatible_items = 6  # 货物兼容性约束
    incompatible_item_vehicle = 7  # 货物-车辆兼容性约束





