import numpy as np

from simulator.dpdp_competition.algorithm.src.constrains.constrains_base import ConstrainsBase
from simulator.dpdp_competition.algorithm.src.common.vehicle import Vehicle
from simulator.dpdp_competition.algorithm.src.enum.demand_type_enum import DemandTypeEnum


class LIFOConstrains(ConstrainsBase):
    def __init__(self, vehicle: Vehicle, pickup_route_index: int, delivery_route_index: int):
        self.__vehicle = vehicle
        self.__pickup_route_index = pickup_route_index
        self.__delivery_route_index = delivery_route_index

    def isFeasible(self) -> bool:
        route = self.__vehicle.getCurrentRoute
        min_insert_index = np.infty
        for k in range(1, self.__pickup_route_index):
            if route[k].demandType == DemandTypeEnum.pickup.name:
                min_insert_index = min(min_insert_index, route.index(route[k].brotherNode))
        if self.__delivery_route_index > min_insert_index and self.__pickup_route_index != len(route) - 1:
            return False

        max_insert_index = -np.infty
        min_delivery_only_insert = np.infty
        for k in range(self.__pickup_route_index + 1, len(route)):
            if route[k].demandType == DemandTypeEnum.pickup.name:
                max_insert_index = max(max_insert_index, route.index(route[k].brotherNode))
            elif (not route[k].brotherNode and route[k].demandType == DemandTypeEnum.delivery.name) or \
                    route[k].demandType == DemandTypeEnum.delivery_only.name:
                min_delivery_only_insert = min(min_delivery_only_insert, k)
        if self.__delivery_route_index > min_delivery_only_insert:
            return False
        if self.__delivery_route_index <= max_insert_index:
            return False
        if max_insert_index == -np.infty and min_insert_index == np.infty \
                and self.__delivery_route_index != self.__pickup_route_index + 1:
            return False
        return True
