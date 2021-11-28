from enum import Enum


class DemandInfoEnum(Enum):
    customer_id = 1
    demand_type = 2
    volume = 3
    brother_customer = 4
    time_window = 5
    process_time = 6
    finish_time = 7
    matchedVehicle = 8
