from copy import deepcopy

from simulator.dpdp_competition.algorithm.src.constrains.constrains_base import ConstrainsBase
from simulator.dpdp_competition.algorithm.src.common.vehicle import Vehicle
from simulator.dpdp_competition.algorithm.src.enum.request_info_enum import RequestInfoEnum


class CompatibleConstrain(ConstrainsBase):
    def isFeasible(self) -> bool:
        pass


class VehicleItemCompatibleConstrain(CompatibleConstrain):
    """
    车辆兼容性约束
    """
    def __init__(self, compatible_type_list, item_type: str):
        self.__compatible_type_list = compatible_type_list
        self.__item_type = item_type

    def isFeasible(self) -> bool:
        if self.__item_type not in self.__compatible_type_list:
            return False
        else:
            return True


class ItemCompatibleConstrain(CompatibleConstrain):
    """
    订单互斥约束
    """
    def __init__(self, vehicle: Vehicle, requests: dict, item_type:str):
        self.__incompatible_item_type_set = deepcopy(vehicle.get_incompatible_item_type_set)
        route = vehicle.getCurrentRoute
        for node in route:
            if node.requestID in requests:
                self.__incompatible_item_type_set = self.__incompatible_item_type_set.union(set(
                    requests[node.requestID][RequestInfoEnum.incompatible_item_type_list.name]
                ))
        self.__item_type = item_type

    def isFeasible(self) -> bool:
        if self.__item_type in self.__incompatible_item_type_set:
            return False
        else:
            return True
