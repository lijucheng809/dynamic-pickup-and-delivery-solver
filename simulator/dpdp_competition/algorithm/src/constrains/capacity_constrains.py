from simulator.dpdp_competition.algorithm.src.constrains.constrains_base import ConstrainsBase
from simulator.dpdp_competition.algorithm.src.common.vehicle import Vehicle
from simulator.dpdp_competition.algorithm.src.enum.request_info_enum import RequestInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.demand_info_enum import DemandInfoEnum


class CapacityConstrains(ConstrainsBase):
    def __init__(self, request: dict, vehicle: Vehicle, route_index: int):
        self.__vehicle = vehicle
        self.__request = request
        self.__route_index = route_index

    def isFeasible(self) -> bool:
        request_volume = self.__request[RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.volume.name]
        vehicle_capacity = self.__vehicle.getCapacity
        if request_volume + self.__vehicle.getCurrentVolume(self.__route_index + 1) > vehicle_capacity:
            return False
        return True
